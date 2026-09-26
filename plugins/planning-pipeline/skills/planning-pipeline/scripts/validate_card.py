#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validacion mecanica de una tarjeta de feature (.dev/cards/FG-xx-<slug>.json).

La tarjeta es la semilla del camino rapido: reemplaza al ciclo formal de requisitos
para UNA feature urgente y acotada, y es lo que despues permite promoverla a linea de
base sin leer el codigo. Este script no juzga contenido (eso es del usuario en la
pausa unica): verifica que la tarjeta cumpla el contrato que consumen
`card_to_partial.py`, el build y `/promover`.

La regla central es la de los ids: rules, acceptance y sus referencias usan la forma
PROVISIONAL `PREFIJO-<tag>#<n>` (`RF-FT07#1`, `AC-FT07#3`) que `apply_delta.py` sabe
renumerar a la secuencia global el dia de la promocion. Un id global (`RF-007`) en una
tarjeta es un error: pertenece al flujo formal y no se renumera.

Checks (todos `high` salvo donde se aclara):
  CARD-CHECK-001  campos obligatorios presentes y no vacios
  CARD-CHECK-002  ids con forma provisional y tag coherente con el id de la feature
  CARD-CHECK-003  sin ids globales (RF-nnn, AC-nnn, SCN-nnn): son del flujo formal
  CARD-CHECK-004  toda regla cubierta por >=1 criterio; todo `covers` existe
  CARD-CHECK-005  tareas: toda regla en >=1 tarea, toda tarea con regla y criterio,
                  complexity/priority validas, depends_on resoluble y sin ciclos
  CARD-CHECK-006  enums cerrados (status, kind, security_surface) y unicidad de ids
  CARD-CHECK-007  `medium`: intent.done_when medible
  CARD-CHECK-008  preguntas abiertas con contrato: id, texto, `default_assumption`
                  (con que sigue el build), `impact` y `blocks` resoluble. Las de
                  impacto en modelo o seguridad salen `medium`: son contraindicacion

Solo stdlib, Python 3.8+. No escribe nada.

Uso:
  python validate_card.py <ruta-a-la-tarjeta.json> [--json]
  python validate_card.py .dev/cards --card FG-07 [--json]
  python validate_card.py --self-test

Salida: una linea por defecto (check, severidad, ubicacion, mensaje) o el JSON con
--json. Exit 0 si no hay defectos `high`, 1 si los hay, 2 ante error de IO o parseo.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROVISIONAL = re.compile(r"^([A-Z]+)-([A-Za-z0-9]+)#(\d+)$")
GLOBAL_ID = re.compile(r"^(RF|RNF|AC|SCN|RN)-\d+$")
LOCAL_TASK = re.compile(r"^L-\d+$")
FEATURE_ID = re.compile(r"^FG-\d+$")
OWASP = re.compile(r"^A\d{2}$")

STATUSES = {"drafted", "built", "promoted"}
RULE_KINDS = {"functional", "business_rule", "nfr"}
VOCAB_KINDS = {"objeto", "sujeto", "verbo", "estado"}
COMPLEXITIES = {"low", "medium", "high"}
PRIORITIES = {"high", "medium", "low"}
SOURCE_KINDS = {"document", "prompt"}
QUESTION_IMPACTS = {"alcance", "modelo", "seguridad", "ux"}


def die(msg):
    print("ERROR: %s" % msg)
    sys.exit(2)


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        die("%s ilegible: %s" % (path, exc))


def find_card(folder, feature):
    # solo archivos sueltos de la carpeta: las inspecciones viven en inspections/
    hits = sorted(p for p in Path(folder).glob("%s-*.json" % feature) if p.parent.name != "inspections")
    if not hits:
        die("no hay tarjeta de %s en %s" % (feature, folder))
    if len(hits) > 1:
        die("hay %d tarjetas de %s en %s: %s" % (len(hits), feature, folder, ", ".join(p.name for p in hits)))
    return hits[0]


def tag_of(feature_id):
    """FG-07 -> FT07: el tag que llevan los ids provisionales de esa tarjeta."""
    return "FT%s" % str(feature_id).split("-")[-1]


def _has_cycle(tasks):
    graph = {t.get("id"): list(t.get("depends_on") or []) for t in tasks}
    state = {}

    def walk(node):
        if state.get(node) == "done":
            return False
        if state.get(node) == "open":
            return True
        state[node] = "open"
        for nxt in graph.get(node) or []:
            if nxt in graph and walk(nxt):
                return True
        state[node] = "done"
        return False

    return any(walk(n) for n in list(graph))


def validate(card):
    """Devuelve la lista de defectos [{check, severity, where, message}]."""
    defects = []

    def defect(check, severity, where, message):
        defects.append({"check": check, "severity": severity, "where": where, "message": message})

    # --------------------------------------------- 001 campos obligatorios
    fid = card.get("id")
    if not isinstance(fid, str) or not FEATURE_ID.match(fid or ""):
        defect("CARD-CHECK-001", "high", "id", "id de feature invalido %r: se espera FG-nn" % fid)
        fid = fid if isinstance(fid, str) else "FG-00"
    for key in ("slug", "version", "status", "source", "intent", "rules", "acceptance", "tasks"):
        if not card.get(key):
            defect("CARD-CHECK-001", "high", key, "campo obligatorio vacio o ausente")
    intent = card.get("intent") or {}
    for key in ("problem", "who", "value", "done_when"):
        if not str(intent.get(key) or "").strip():
            defect("CARD-CHECK-001", "high", "intent.%s" % key,
                   "sin esto la tarjeta no alcanza para construir ni para promover")
    source = card.get("source") or {}
    if source and not str(source.get("path") or "").strip():
        defect("CARD-CHECK-001", "high", "source.path",
               "la fuente tiene que quedar archivada: es la trazabilidad del atajo")

    # ----------------------------------------------------- 006 enums cerrados
    if card.get("status") and card.get("status") not in STATUSES:
        defect("CARD-CHECK-006", "high", "status",
               "status invalido %r: %s" % (card.get("status"), "|".join(sorted(STATUSES))))
    if source.get("kind") and source.get("kind") not in SOURCE_KINDS:
        defect("CARD-CHECK-006", "high", "source.kind", "kind invalido %r" % source.get("kind"))
    for a in card.get("security_surface") or []:
        if not OWASP.match(str(a)):
            defect("CARD-CHECK-006", "high", "security_surface",
                   "categoria OWASP invalida %r: se espera Ann (A01, A03)" % a)
    for v in card.get("vocabulary") or []:
        if v.get("kind") and v["kind"] not in VOCAB_KINDS:
            defect("CARD-CHECK-006", "high", "vocabulary[%s]" % v.get("term"), "kind invalido %r" % v["kind"])
        if not str(v.get("gloss") or "").strip():
            defect("CARD-CHECK-006", "high", "vocabulary[%s]" % v.get("term"),
                   "simbolo sin glosa: no sirve para sembrar el LEL")

    # ------------------------------------------------- 002/003 forma de ids
    tag = tag_of(fid)
    seen = {}

    def check_id(value, where, prefix):
        if not isinstance(value, str) or not value.strip():
            defect("CARD-CHECK-002", "high", where, "id ausente")
            return
        if GLOBAL_ID.match(value):
            defect("CARD-CHECK-003", "high", where,
                   "id global %s: la tarjeta usa ids provisionales (%s-%s#n), que se renumeran al promover"
                   % (value, prefix, tag))
            return
        m = PROVISIONAL.match(value)
        if not m:
            defect("CARD-CHECK-002", "high", where,
                   "id %r no tiene la forma provisional %s-%s#n" % (value, prefix, tag))
            return
        if m.group(1) != prefix:
            defect("CARD-CHECK-002", "high", where, "id %r deberia empezar con %s-" % (value, prefix))
        if m.group(2) != tag:
            defect("CARD-CHECK-002", "high", where,
                   "id %r usa el tag %s; esta tarjeta es %s (tag %s)" % (value, m.group(2), fid, tag))
        if value in seen:
            defect("CARD-CHECK-006", "high", where, "id repetido %s (ya usado en %s)" % (value, seen[value]))
        seen[value] = where

    for v in card.get("vocabulary") or []:
        check_id(v.get("id"), "vocabulary[%s]" % v.get("term"), "LEL")

    rules = card.get("rules") or []
    for r in rules:
        check_id(r.get("id"), "rules[%s]" % r.get("id"), "RF")
        if not str(r.get("text") or "").strip():
            defect("CARD-CHECK-001", "high", "rules[%s]" % r.get("id"), "regla sin texto")
        if r.get("kind") and r["kind"] not in RULE_KINDS:
            defect("CARD-CHECK-006", "high", "rules[%s]" % r.get("id"), "kind invalido %r" % r["kind"])
    criteria = card.get("acceptance") or []
    for c in criteria:
        check_id(c.get("id"), "acceptance[%s]" % c.get("id"), "AC")
        for part in ("given", "when", "then"):
            if not str(c.get(part) or "").strip():
                defect("CARD-CHECK-001", "high", "acceptance[%s].%s" % (c.get("id"), part),
                       "criterio incompleto: sin %s no es verificable" % part)

    rule_ids = {r.get("id") for r in rules if r.get("id")}
    crit_ids = {c.get("id") for c in criteria if c.get("id")}

    # ------------------------------------------------------- 004 cobertura
    covered = set()
    for c in criteria:
        refs = c.get("covers") or []
        if not refs:
            defect("CARD-CHECK-004", "high", "acceptance[%s]" % c.get("id"),
                   "criterio que no cubre ninguna regla")
        for rid in refs:
            if rid not in rule_ids:
                defect("CARD-CHECK-004", "high", "acceptance[%s]" % c.get("id"),
                       "covers apunta a una regla inexistente: %s" % rid)
            else:
                covered.add(rid)
    for rid in sorted(rule_ids - covered):
        defect("CARD-CHECK-004", "high", "rules[%s]" % rid,
               "regla sin ningun criterio de aceptacion: el build no puede demostrarla")

    # ---------------------------------------------------------- 005 tareas
    tasks = card.get("tasks") or []
    task_ids = []
    in_tasks = set()
    for t in tasks:
        tid = t.get("id")
        if not isinstance(tid, str) or not LOCAL_TASK.match(tid or ""):
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid,
                   "id de tarea invalido %r: se espera L-nnn" % tid)
        elif tid in task_ids:
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid, "id de tarea repetido")
        task_ids.append(tid)
        if not str(t.get("title") or "").strip():
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid, "tarea sin titulo")
        if t.get("complexity") not in COMPLEXITIES:
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid, "complexity invalida %r" % t.get("complexity"))
        if t.get("priority") and t["priority"] not in PRIORITIES:
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid, "priority invalida %r" % t["priority"])
        refs = t.get("covers") or []
        if not refs:
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid,
                   "tarea sin reglas: quedaria huerfana en el plan (PLAN-CHECK-002)")
        for rid in refs:
            if rid not in rule_ids:
                defect("CARD-CHECK-005", "high", "tasks[%s]" % tid,
                       "covers apunta a una regla inexistente: %s" % rid)
            else:
                in_tasks.add(rid)
        crits = t.get("criteria") or []
        if not crits:
            defect("CARD-CHECK-005", "high", "tasks[%s]" % tid,
                   "tarea sin criterios: un agente de build no puede verificarla (PLAN-CHECK-006)")
        for cid in crits:
            if cid not in crit_ids:
                defect("CARD-CHECK-005", "high", "tasks[%s]" % tid,
                       "criteria apunta a un criterio inexistente: %s" % cid)
    for rid in sorted(rule_ids - in_tasks):
        defect("CARD-CHECK-005", "high", "rules[%s]" % rid, "regla que ninguna tarea construye")
    known = set(task_ids)
    for t in tasks:
        for dep in t.get("depends_on") or []:
            if dep == t.get("id"):
                defect("CARD-CHECK-005", "high", "tasks[%s]" % t.get("id"), "tarea que depende de si misma")
            elif dep not in known:
                defect("CARD-CHECK-005", "high", "tasks[%s]" % t.get("id"),
                       "depends_on apunta a una tarea inexistente: %s" % dep)
    if _has_cycle(tasks):
        defect("CARD-CHECK-005", "high", "tasks", "ciclo en depends_on")

    # ------------------------------------------------- 007 avisos de redaccion
    done_when = str(intent.get("done_when") or "")
    if done_when and len(done_when.split()) < 4:
        defect("CARD-CHECK-007", "medium", "intent.done_when",
               "done_when demasiado corto para ser verificable: %r" % done_when)

    # -------------------------------------------- 008 contrato de las preguntas
    # Una pregunta abierta sin supuesto por defecto no es una pregunta: es un
    # silencio. El build igual va a tener que decidir, y la decision queda
    # implicita en el codigo en vez de escrita en la tarjeta.
    task_ids_set = set(task_ids)
    for q in card.get("open_questions") or []:
        if isinstance(q, str):
            defect("CARD-CHECK-008", "high", "open_questions",
                   "pregunta en texto plano (%r): se espera "
                   "{id, question, default_assumption, blocks, impact}" % q[:60])
            continue
        where = "open_questions[%s]" % q.get("id")
        check_id(q.get("id"), where, "Q")
        if not str(q.get("question") or "").strip():
            defect("CARD-CHECK-008", "high", where, "pregunta sin texto")
        if not str(q.get("default_assumption") or "").strip():
            defect("CARD-CHECK-008", "high", where,
                   "sin default_assumption: con que sigue el build mientras no haya respuesta")
        impact = q.get("impact")
        if impact not in QUESTION_IMPACTS:
            defect("CARD-CHECK-008", "high", where,
                   "impact invalido %r: %s" % (impact, "|".join(sorted(QUESTION_IMPACTS))))
        for ref in q.get("blocks") or []:
            if ref not in rule_ids and ref not in crit_ids and ref not in task_ids_set:
                defect("CARD-CHECK-008", "high", where,
                       "blocks apunta a algo que no existe en la tarjeta: %s" % ref)
        if impact in ("modelo", "seguridad"):
            defect("CARD-CHECK-008", "medium", where,
                   "pregunta de impacto %s sin responder: es contraindicacion del camino "
                   "rapido, mostrasela al usuario en la pausa" % impact)
    return defects


def report(card_path, defects, as_json):
    highs = [d for d in defects if d["severity"] == "high"]
    if as_json:
        print(json.dumps({"card": str(card_path), "passed": not highs, "defects": defects},
                         ensure_ascii=False, indent=2))
    else:
        if not defects:
            print("tarjeta %s: sin defectos" % card_path)
        for d in defects:
            print("%s %s %s: %s" % (d["check"], d["severity"], d["where"], d["message"]))
        if highs:
            print("%d defecto(s) high: la tarjeta no puede proyectarse al plan" % len(highs))
    return 1 if highs else 0


def self_test():
    failures = 0

    def check(cond, label):
        nonlocal failures
        if not cond:
            failures += 1
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))

    base = {
        "id": "FG-07", "slug": "alta-proveedores", "version": 1, "status": "drafted",
        "source": {"path": ".dev/cards/sources/pedido.txt", "kind": "document"},
        "intent": {"problem": "no hay alta de proveedores", "who": "compras",
                   "value": "cargar sin pasar por sistemas",
                   "done_when": "compras da de alta un proveedor sin pedir ayuda"},
        "vocabulary": [{"id": "LEL-FT07#1", "term": "Proveedor",
                        "gloss": "quien provee insumos", "kind": "objeto"}],
        "rules": [{"id": "RF-FT07#1", "text": "alta con CUIT unico", "kind": "functional"}],
        "acceptance": [{"id": "AC-FT07#1", "given": "un CUIT libre", "when": "se da de alta",
                        "then": "el proveedor queda activo", "covers": ["RF-FT07#1"]}],
        "tasks": [{"id": "L-001", "title": "alta de proveedor", "complexity": "low",
                   "priority": "high", "covers": ["RF-FT07#1"], "criteria": ["AC-FT07#1"],
                   "depends_on": []}],
        "security_surface": ["A01"],
        "open_questions": [{"id": "Q-FT07#1", "question": "Se puede reusar el CUIT de un proveedor dado de baja?",
                            "default_assumption": "no se reusa: el CUIT queda ocupado para siempre",
                            "blocks": ["RF-FT07#1"], "impact": "alcance"}],
    }
    check(validate(base) == [], "tarjeta minima valida no tiene defectos")

    bad = json.loads(json.dumps(base))
    bad["open_questions"] = ["y si el CUIT se repite?"]
    check(any(d["check"] == "CARD-CHECK-008" and d["severity"] == "high" for d in validate(bad)),
          "pregunta en texto plano: rechazada")

    bad = json.loads(json.dumps(base))
    bad["open_questions"][0]["default_assumption"] = ""
    check(any("default_assumption" in d["message"] for d in validate(bad)),
          "pregunta sin supuesto por defecto: es un silencio, no una pregunta")

    bad = json.loads(json.dumps(base))
    bad["open_questions"][0]["blocks"] = ["RF-FT07#9"]
    check(any("blocks apunta" in d["message"] for d in validate(bad)),
          "blocks colgado se reporta")

    bad = json.loads(json.dumps(base))
    bad["open_questions"][0]["impact"] = "seguridad"
    ds = [d for d in validate(bad) if d["check"] == "CARD-CHECK-008"]
    check(ds and ds[0]["severity"] == "medium" and "contraindicacion" in ds[0]["message"],
          "pregunta de seguridad sin responder avisa contraindicacion, sin bloquear")

    bad = json.loads(json.dumps(base))
    del bad["vocabulary"][0]["id"]
    check(any(d["check"] == "CARD-CHECK-002" for d in validate(bad)),
          "vocabulario sin id: los agentes de la promocion tendrian que adivinarlo")

    bad = json.loads(json.dumps(base))
    bad["rules"][0]["id"] = "RF-007"
    bad["acceptance"][0]["covers"] = ["RF-007"]
    bad["tasks"][0]["covers"] = ["RF-007"]
    check("CARD-CHECK-003" in {d["check"] for d in validate(bad)}, "id global rechazado")

    bad = json.loads(json.dumps(base))
    bad["rules"].append({"id": "RF-FT07#2", "text": "baja logica", "kind": "functional"})
    ds = validate(bad)
    check(any(d["check"] == "CARD-CHECK-004" for d in ds), "regla sin criterio se reporta")
    check(any(d["check"] == "CARD-CHECK-005" for d in ds), "regla sin tarea se reporta")

    bad = json.loads(json.dumps(base))
    bad["rules"][0]["id"] = "RF-FT03#1"
    check(any("tag" in d["message"] for d in validate(bad)),
          "tag que no coincide con la feature se reporta")

    bad = json.loads(json.dumps(base))
    bad["tasks"][0]["criteria"] = []
    check(any("PLAN-CHECK-006" in d["message"] for d in validate(bad)),
          "tarea sin criterios avisa el impacto en el plan")

    bad = json.loads(json.dumps(base))
    bad["tasks"].append({"id": "L-002", "title": "x", "complexity": "low",
                         "covers": ["RF-FT07#1"], "criteria": ["AC-FT07#1"], "depends_on": ["L-001"]})
    bad["tasks"][0]["depends_on"] = ["L-002"]
    check(any("ciclo" in d["message"] for d in validate(bad)), "ciclo en depends_on detectado")

    bad = json.loads(json.dumps(base))
    bad["intent"]["done_when"] = "listo"
    ds = validate(bad)
    check(ds and all(d["severity"] == "medium" for d in ds),
          "done_when corto es medium y no bloquea")

    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ruta", help="tarjeta .json, o la carpeta .dev/cards con --card")
    ap.add_argument("--card", default=None, help="id de feature (FG-07) cuando `ruta` es una carpeta")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)
    path = Path(args.ruta)
    if path.is_dir():
        if not args.card:
            die("%s es una carpeta: indica --card FG-xx" % path)
        path = find_card(path, args.card)
    elif not path.is_file():
        die("no existe %s" % path)
    return report(path, validate(load(path)), args.as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
