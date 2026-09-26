#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proyeccion determinista de una tarjeta al formato de derivacion del plan.

Camino rapido: la tarjeta (.dev/cards/FG-xx-<slug>.json) ya trae la intencion, las
reglas, los criterios y el corte en tareas que en el camino formal produciria
`task-derivation` a partir de requisitos. Este script la proyecta, sin tokens de
modelo, a los dos archivos que `merge_tasks.py` consume:

  .dev/plan/.derivation-context/skeleton.json
  .dev/plan/.derivation-context/tasks.FG-xx.json

Los `requirement_ids` de las tareas son los ids PROVISIONALES de las reglas de la
tarjeta (`RF-FT07#1`). Eso es deliberado: con ellos la tarea no queda huerfana
(PLAN-CHECK-002) y el dia de la promocion `apply_delta.py` los renumera a la
secuencia global de una sola pasada.

Modo: si ya existe `.dev/plan/tasks.json`, la proyeccion es para REPLANIFICACION
(el skeleton no toca `requirements_version_ref` ni `active_requirement_ids`, para no
pisar la linea de base que ya absorbio el plan). Si no existe, es una derivacion
fresca. El script detecta el modo, lo informa, e imprime los comandos siguientes con
las banderas que corresponden: correr `merge_tasks.py` sin `--replan` sobre un plan
existente rompe (`compute_execution_plan.py` falla si hay build en curso).

Solo stdlib, Python 3.8+. No toca tasks.json ni la tarjeta.

Uso:
  python card_to_partial.py [raiz] --card FG-07 [--cards DIR] [--replan|--fresco]
  python card_to_partial.py --self-test

  raiz     raiz del repo (default: .). Escribe bajo <raiz>/.dev/plan/
  --cards  carpeta de tarjetas (default: <raiz>/.dev/cards)

Salida: los archivos escritos, el modo detectado y los comandos siguientes.
Exit 0 si proyecto; 1 si la tarjeta no existe, no parsea o no pasa validate_card.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from validate_card import find_card, load, validate
except ImportError:  # pragma: no cover - solo si alguien mueve los scripts
    print("ERROR: validate_card.py tiene que estar junto a este script")
    sys.exit(1)

CONTEXT_DIR = ".derivation-context"


def fail(msg):
    print("ERROR: %s" % msg)
    sys.exit(1)


def feature_block(card):
    intent = card.get("intent") or {}
    name = str(card.get("slug") or card.get("id")).replace("-", " ").strip()
    description = " ".join(x for x in (intent.get("problem"), intent.get("value")) if x)
    return {
        "id": card["id"],
        "name": name,
        "description": description or name,
        "requirement_ids": [r["id"] for r in card.get("rules") or []],
        "synthetic": False,
    }


def project_tasks(card):
    """Tareas de la tarjeta -> tareas del parcial de derivacion."""
    criteria = {c.get("id"): c for c in card.get("acceptance") or []}
    out = []
    for t in card.get("tasks") or []:
        acs = []
        for cid in t.get("criteria") or []:
            c = criteria.get(cid) or {}
            acs.append({"id": cid, "given": c.get("given", ""), "when": c.get("when", ""),
                        "then": c.get("then", "")})
        out.append({
            "id": t["id"],
            "feature_group": card["id"],
            "title": t.get("title", ""),
            "description": t.get("description") or t.get("title", ""),
            "type": t.get("type") or "feature",
            "priority": t.get("priority") or "medium",
            "complexity": t.get("complexity"),
            "depends_on": [{"task_id": d, "kind": "hard"} for d in t.get("depends_on") or []],
            "requirement_ids": list(t.get("covers") or []),
            "module_ids": [],
            "entity_ids": [],
            "acceptance_criteria": acs,
            "status": "pending",
            "evidence_refs": list(t.get("covers") or []),
        })
    return out


def card_questions(card, tasks):
    """Preguntas abiertas de la tarjeta -> preguntas del plan, apuntadas y con supuesto.

    Dos cosas que el brief necesita y que se pierden si no se hacen aca:

    - **A que tarea apuntan.** El brief filtra las preguntas por tarea relacionada: una
      pregunta sin relacionar se escribe y se descarta en silencio. Si la pregunta
      declara `blocks` (reglas, criterios o tareas), se resuelve a las tareas que
      cubren eso; si no declara nada, afecta a toda la feature.
    - **El supuesto por defecto.** Es con lo que sigue el build mientras no haya
      respuesta. Va pegado al texto porque el brief no renderiza otro campo, y sin el
      la decision queda implicita en el codigo en vez de escrita.
    """
    fid = card["id"]
    by_rule = {}
    for t in tasks:
        for rid in t["requirement_ids"]:
            by_rule.setdefault(rid, []).append(t["id"])
        for ac in t["acceptance_criteria"]:
            by_rule.setdefault(ac["id"], []).append(t["id"])
    todas = [t["id"] for t in tasks]
    out = []
    for q in card.get("open_questions") or []:
        if isinstance(q, str):  # tarjeta vieja, sin contrato
            q = {"question": q}
        destinos = []
        for ref in q.get("blocks") or []:
            for tid in by_rule.get(ref, [ref] if ref in todas else []):
                if tid not in destinos:
                    destinos.append(tid)
        supuesto = str(q.get("default_assumption") or "").strip()
        texto = str(q.get("question") or "")
        if supuesto:
            texto = "%s — mientras no haya respuesta: %s" % (texto, supuesto)
        out.append({
            "question": texto,
            "blocking": False,
            "target_role": "stakeholder",
            "reason": "pregunta abierta de la tarjeta %s (impacto: %s); no bloquea el build, "
                      "se resuelve al promover" % (fid, q.get("impact") or "sin declarar"),
            "related_task_ids": destinos or todas,
        })
    return out


def build(card, replan):
    """Devuelve (skeleton, partial) listos para escribir."""
    fid = card["id"]
    rules = card.get("rules") or []
    tasks = project_tasks(card)
    skeleton = {
        "features": [feature_block(card)],
        "contract_tasks": [],
        "assumptions": ["%s viene de una tarjeta (camino rapido): sus requisitos son "
                        "provisionales hasta /promover %s" % (fid, fid)],
        "warnings": [],
        "metadata": {},
    }
    if not replan:
        skeleton["active_requirement_ids"] = [r["id"] for r in rules]
    partial = {
        "feature": feature_block(card),
        "tasks": tasks,
        "open_questions": card_questions(card, tasks),
        "traceability_links": [
            {"source": {"kind": "task", "id": t["id"]},
             "target": {"kind": "requirement", "id": rid},
             "relationship": "covers"}
            for t in tasks for rid in t["requirement_ids"]
        ],
        "assumptions": list(card.get("assumptions") or []),
        "warnings": ["requisitos provisionales de la tarjeta %s: pendientes de /promover" % fid],
    }
    return skeleton, partial


def write(plan_dir, fid, skeleton, partial):
    ctx = plan_dir / CONTEXT_DIR
    ctx.mkdir(parents=True, exist_ok=True)
    # `.derivation-context/` es temporal y una corrida cerrada no la deja atras. Si
    # quedaron parciales de otras features (derivacion interrumpida), `merge_tasks.py`
    # los toma como parte de esta corrida y frena: "parciales de features no
    # afectadas". La tarjeta proyecta UNA feature, asi que barremos el resto.
    stale = [p for p in sorted(ctx.glob("tasks.FG-*.json")) if p.name != "tasks.%s.json" % fid]
    for p in stale:
        p.unlink()
    if stale:
        print("limpiados %d parcial(es) de una derivacion anterior: %s"
              % (len(stale), ", ".join(p.name for p in stale)))
    paths = []
    for name, doc in (("skeleton.json", skeleton), ("tasks.%s.json" % fid, partial)):
        path = ctx / name
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def aviso_inspeccion(cards_dir, feature):
    """Avisa si la tarjeta se proyecta sin inspeccion, o con defectos altos abiertos.

    No bloquea: el usuario puede aceptar defectos anotados en la pausa, como en el
    resto de la suite. Pero saltear la inspeccion tiene que verse, porque en el camino
    rapido es el unico juicio entre la fuente y el codigo.
    """
    path = cards_dir / "inspections" / ("%s.json" % feature)
    if not path.is_file():
        print("aviso: no hay %s — se proyecta sin la inspeccion de la tarjeta, "
              "que es el unico control entre la fuente y el codigo" % path.name)
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        print("aviso: %s ilegible (%s): se proyecta sin veredicto" % (path.name, exc))
        return
    highs = [d for d in doc.get("defects") or [] if d.get("severity") == "high"]
    if highs:
        print("aviso: la inspeccion dejo %d defecto(s) high sin resolver (%s): "
              "se proyectan igual, pero quedan construidos asi"
              % (len(highs), ", ".join(str(d.get("check_id")) for d in highs[:3])))


def run(root, feature, cards_dir, forced_mode):
    root = Path(root).resolve()
    cards = Path(cards_dir) if cards_dir else root / ".dev" / "cards"
    if not cards.is_dir():
        fail("no existe la carpeta de tarjetas %s" % cards)
    card_path = find_card(cards, feature)
    card = load(card_path)
    if card.get("id") != feature:
        fail("%s declara id %r pero se pidio %s" % (card_path, card.get("id"), feature))
    defects = [d for d in validate(card) if d["severity"] == "high"]
    if defects:
        print("ERROR: la tarjeta tiene %d defecto(s) high; corrilos con validate_card.py antes de proyectar:"
              % len(defects))
        for d in defects[:5]:
            print("  %s %s: %s" % (d["check"], d["where"], d["message"]))
        return 1

    aviso_inspeccion(cards, feature)

    plan_dir = root / ".dev" / "plan"
    existing = (plan_dir / "tasks.json").is_file()
    replan = existing if forced_mode is None else forced_mode
    if forced_mode is not None and forced_mode != existing:
        print("aviso: modo forzado a %s y tasks.json %s" %
              ("replan" if forced_mode else "fresco", "existe" if existing else "no existe"))

    skeleton, partial = build(card, replan)
    paths = write(plan_dir, feature, skeleton, partial)
    for p in paths:
        print("escrito %s" % p)
    print("modo: %s (%s)" % ("replanificacion" if replan else "derivacion fresca",
                             "ya hay tasks.json" if existing else "plan nuevo"))
    print("tareas proyectadas: %d; reglas provisionales: %d"
          % (len(partial["tasks"]), len(card.get("rules") or [])))
    flags = " --replan --features %s" % feature if replan else ""
    print("siguiente:")
    print("  merge_tasks.py .%s --pipeline-version <X.Y.Z>" % flags)
    print("  compute_execution_plan.py .dev/plan%s" % (" --replan" if replan else ""))
    return 0


def self_test():
    import shutil
    import tempfile

    failures = 0

    def check(cond, label):
        nonlocal failures
        if not cond:
            failures += 1
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))

    card = {
        "id": "FG-07", "slug": "alta-proveedores", "version": 1, "status": "drafted",
        "source": {"path": ".dev/cards/sources/pedido.txt", "kind": "document"},
        "intent": {"problem": "no hay alta", "who": "compras", "value": "cargar sin sistemas",
                   "done_when": "compras da de alta un proveedor solo"},
        "rules": [{"id": "RF-FT07#1", "text": "alta con CUIT unico", "kind": "functional"},
                  {"id": "RF-FT07#2", "text": "baja logica", "kind": "business_rule"}],
        "acceptance": [{"id": "AC-FT07#1", "given": "un CUIT libre", "when": "se da de alta",
                        "then": "queda activo", "covers": ["RF-FT07#1"]},
                       {"id": "AC-FT07#2", "given": "un proveedor activo", "when": "se da de baja",
                        "then": "queda inactivo y no se borra", "covers": ["RF-FT07#2"]}],
        "tasks": [{"id": "L-001", "title": "alta", "complexity": "low", "priority": "high",
                   "covers": ["RF-FT07#1"], "criteria": ["AC-FT07#1"], "depends_on": []},
                  {"id": "L-002", "title": "baja", "complexity": "low", "priority": "medium",
                   "covers": ["RF-FT07#2"], "criteria": ["AC-FT07#2"], "depends_on": ["L-001"]}],
        "open_questions": [
            {"id": "Q-FT07#1", "question": "quien aprueba el alta?",
             "default_assumption": "cualquiera del sector puede dar de alta sin aprobacion",
             "blocks": ["RF-FT07#1"], "impact": "seguridad"},
            {"id": "Q-FT07#2", "question": "se reusa el CUIT de un proveedor dado de baja?",
             "default_assumption": "no se reusa", "blocks": [], "impact": "modelo"}],
        "assumptions": ["el CUIT se valida contra AFIP en otra feature"],
    }

    skeleton, partial = build(card, replan=False)
    check(skeleton["active_requirement_ids"] == ["RF-FT07#1", "RF-FT07#2"],
          "modo fresco declara los requisitos activos")
    check("active_requirement_ids" not in build(card, replan=True)[0],
          "modo replan no pisa los requisitos activos previos")
    check(all(t["requirement_ids"] for t in partial["tasks"]),
          "ninguna tarea queda huerfana (PLAN-CHECK-002)")
    check(all(t["acceptance_criteria"] for t in partial["tasks"]),
          "toda tarea lleva criterios (PLAN-CHECK-006)")
    check(partial["tasks"][1]["depends_on"] == [{"task_id": "L-001", "kind": "hard"}],
          "depends_on local en el formato del merge")
    check(partial["tasks"][0]["acceptance_criteria"][0]["then"] == "queda activo",
          "el Gherkin del criterio viaja completo")
    check(len(partial["traceability_links"]) == 2, "trazabilidad tarea -> requisito")
    check(partial["open_questions"][0]["blocking"] is False,
          "las preguntas abiertas de la tarjeta no bloquean el build")
    check(partial["open_questions"][0]["related_task_ids"] == ["L-001"],
          "la pregunta apunta a la tarea que construye la regla que bloquea (%s)"
          % partial["open_questions"][0]["related_task_ids"])
    check(partial["open_questions"][1]["related_task_ids"] == ["L-001", "L-002"],
          "sin blocks, la pregunta afecta a toda la feature")
    check("mientras no haya respuesta: no se reusa" in partial["open_questions"][1]["question"],
          "el supuesto por defecto viaja al brief pegado a la pregunta")

    tmp = Path(tempfile.mkdtemp())
    try:
        cards = tmp / ".dev" / "cards"
        cards.mkdir(parents=True)
        (cards / "FG-07-alta-proveedores.json").write_text(json.dumps(card), encoding="utf-8")
        check(run(tmp, "FG-07", None, None) == 0, "corrida completa sobre una tarjeta valida")
        (cards / "inspections").mkdir(exist_ok=True)
        (cards / "inspections" / "FG-07.json").write_text(json.dumps({
            "version": 1, "card": "FG-07", "passed": False,
            "defects": [{"check_id": "CARD-INSP-001", "severity": "high",
                         "target_id": "RF-FT07#1", "description": "la fuente no lo dice"}]}),
            encoding="utf-8")
        check(run(tmp, "FG-07", None, None) == 0,
              "una inspeccion con defectos high avisa pero no bloquea (la decision es del usuario)")
        ctx = tmp / ".dev" / "plan" / CONTEXT_DIR
        check((ctx / "skeleton.json").is_file() and (ctx / "tasks.FG-07.json").is_file(),
              "escribe skeleton y parcial donde merge_tasks los busca")
        roto = json.loads(json.dumps(card))
        roto["tasks"][0]["covers"] = []
        (cards / "FG-07-alta-proveedores.json").write_text(json.dumps(roto), encoding="utf-8")
        check(run(tmp, "FG-07", None, None) == 1, "tarjeta con defectos high no se proyecta")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failures += _integration_test(card, check)
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def _run_script(name, *args):
    """Corre un script hermano y devuelve (exit_code, stdout+stderr)."""
    import subprocess

    proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / name)] + [str(a) for a in args],
                          capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _validate_plan(root):
    code, out = _run_script("validate_plan.py", root, "--json")
    try:
        doc = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except ValueError:
        return code, {"defects": [], "raw": out}
    return code, doc


def _integration_test(card, check):
    """Round-trip real: tarjeta -> parcial -> merge -> lotes -> validacion del plan.

    Las dos variantes son los dos escenarios que el camino rapido promete. La segunda
    es la que importa: con linea de base presente, PLAN-CHECK-002 marcaba `high` todo
    id provisional (no existe como requisito), y eso dejaba el atajo inservible en
    cualquier proyecto que ya hubiera corrido la suite.
    """
    import shutil
    import tempfile

    failures = 0

    def sub(cond, label):
        nonlocal failures
        if not cond:
            failures += 1
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))

    def write(path, doc):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    # --------------------------------------------- variante A: sin linea de base
    tmp = Path(tempfile.mkdtemp(prefix="card-fresh-"))
    try:
        write(tmp / ".dev" / "cards" / "FG-07-alta-proveedores.json", card)
        sub(run(tmp, "FG-07", None, None) == 0, "A: proyeccion sobre proyecto sin plan")
        code, out = _run_script("merge_tasks.py", tmp, "--pipeline-version", "9.9.9")
        sub(code == 0, "A: merge_tasks acepta el parcial de la tarjeta")
        code, out = _run_script("compute_execution_plan.py", tmp / ".dev" / "plan",
                                "--pipeline-version", "9.9.9")
        sub(code == 0, "A: compute_execution_plan arma los lotes")
        _run_script("render_plan_docs.py", tmp / ".dev" / "plan")
        code, doc = _validate_plan(tmp)
        bloqueantes = [d for d in doc.get("defects") or [] if d.get("severity") in ("high", "medium")]
        pendientes = [d for d in doc.get("defects") or []
                      if d.get("check_id") == "PLAN-CHECK-002" and d.get("severity") == "low"]
        sub(code == 0 and not bloqueantes, "A: plan valido sin defectos bloqueantes (%s)" % bloqueantes)
        sub(len(pendientes) == 1, "A: sin linea de base la deuda tambien se reporta como low")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------- variante B: linea de base y un build ya en curso
    tmp = Path(tempfile.mkdtemp(prefix="card-baseline-"))
    try:
        write(tmp / ".dev" / "requirements" / "requirements.json", {
            "version": 2,
            "feature_groups": [{"id": "FG-01", "requirement_ids": ["RF-001"]}],
            "functional_requirements": [{
                "id": "RF-001", "feature_group": "FG-01", "status": "active",
                "estimated_effort": "m",
                "acceptance_criteria": [{"id": "AC-001", "given": "g", "when": "w", "then": "t"}]}],
            "non_functional_requirements": [],
        })
        ctx = tmp / ".dev" / "plan" / CONTEXT_DIR
        write(ctx / "skeleton.json", {
            "features": [{"id": "FG-01", "name": "base", "description": "base",
                          "requirement_ids": ["RF-001"], "synthetic": False}],
            "contract_tasks": [], "metadata": {"requirements_version_ref": "2"},
            "active_requirement_ids": ["RF-001"]})
        write(ctx / "tasks.FG-01.json", {"tasks": [{
            "id": "L-001", "feature_group": "FG-01", "title": "base", "type": "feature",
            "priority": "high", "complexity": "low", "depends_on": [],
            "requirement_ids": ["RF-001"], "module_ids": [], "entity_ids": [],
            "acceptance_criteria": [{"id": "AC-001", "given": "g", "when": "w", "then": "t"}],
            "status": "pending"}]})
        _run_script("merge_tasks.py", tmp, "--pipeline-version", "9.9.9")
        _run_script("compute_execution_plan.py", tmp / ".dev" / "plan", "--pipeline-version", "9.9.9")
        # el build ya arranco sobre la feature previa: este es el caso real en el que
        # entra un pedido urgente
        write(tmp / ".dev" / "plan" / "progress.json", {
            "plan_ref": {"tasks_version": 1},
            "features": [{"feature_id": "FG-01", "status": "in_progress", "branch": "feature/base", "notes": ""}],
            "tasks": [{"task_id": "T-001", "feature_id": "FG-01", "status": "in_progress", "notes": ""}]})

        write(tmp / ".dev" / "cards" / "FG-07-alta-proveedores.json", card)
        sub(run(tmp, "FG-07", None, None) == 0, "B: proyeccion detecta replanificacion")
        code, out = _run_script("compute_execution_plan.py", tmp / ".dev" / "plan")
        sub(code != 0, "B: sin --replan con build en curso, compute_execution_plan frena")
        code, out = _run_script("merge_tasks.py", tmp, "--replan", "--features", "FG-07",
                                "--pipeline-version", "9.9.9")
        sub(code == 0, "B: merge en modo replan (%s)" % out.strip().splitlines()[-1:])
        code, out = _run_script("compute_execution_plan.py", tmp / ".dev" / "plan", "--replan",
                                "--pipeline-version", "9.9.9")
        sub(code == 0, "B: lotes recalculados con la feature nueva")
        _run_script("render_plan_docs.py", tmp / ".dev" / "plan")
        code, doc = _validate_plan(tmp)
        bloqueantes = [d for d in doc.get("defects") or [] if d.get("severity") in ("high", "medium")]
        pendientes = [d for d in doc.get("defects") or []
                      if d.get("check_id") == "PLAN-CHECK-002" and d.get("severity") == "low"]
        sub(code == 0 and not bloqueantes,
            "B: ids provisionales con linea de base NO son high (%s)" % bloqueantes)
        sub(len(pendientes) == 1 and "FG-07" in json.dumps(pendientes),
            "B: la deuda de promocion queda como low informativo")
        tasks_doc = json.loads((tmp / ".dev" / "plan" / "tasks.json").read_text(encoding="utf-8"))
        base = next(t for t in tasks_doc["tasks"] if t["feature_group"] == "FG-01")
        sub(base["requirement_ids"] == ["RF-001"] and base["id"] == "T-001",
            "B: la feature en curso queda intacta")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return failures


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--card", required=True, help="id de la feature (FG-07)")
    ap.add_argument("--cards", default=None, help="carpeta de tarjetas (default: <raiz>/.dev/cards)")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--replan", action="store_true", help="forzar modo replanificacion")
    modo.add_argument("--fresco", action="store_true", help="forzar modo derivacion fresca")
    args = ap.parse_args(argv)
    forced = True if args.replan else (False if args.fresco else None)
    return run(args.raiz, args.card, args.cards, forced)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
