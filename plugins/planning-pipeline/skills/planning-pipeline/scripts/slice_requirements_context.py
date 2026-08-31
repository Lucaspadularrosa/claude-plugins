#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-cortador de contexto para la derivacion de tareas: una tajada por feature.

Generaliza a `slice_brief_context.py` para la etapa 1 del pipeline. La derivacion se
hace en dos fases y este script alimenta a las dos:

  --mapa      escribe `.dev/plan/.derivation-context/mapa.json`: la proyeccion compacta
              de la linea de base que necesita la pasada global de `task-derivation`
              (features, requisitos en una linea con sus depends_on, contratos de API,
              modulos, changelog aplicado). Nada de criterios ni prosa larga.
  (default)   escribe una tajada `.dev/plan/.derivation-context/FG-xx.json` por feature
              con TODO lo que la derivacion de esa feature necesita: sus requisitos
              completos (criterios incluidos), reglas de negocio, diseno relevante,
              entidades, y del esqueleto (`skeleton.json`, lo escribe la pasada global)
              las aristas cross-feature y las tareas-contrato que la tocan. En
              replanificacion (--replan) suma las tareas previas de la feature, su
              estado en progress.json y las entradas del changelog del delta.

Los agentes `task-derivation` por feature corren en paralelo leyendo cada uno su
tajada; `merge_tasks.py` consolida los parciales en `tasks.json`.

Solo stdlib, Python 3.8+. No modifica los artefactos canonicos.

Uso:
  python slice_requirements_context.py [raiz] --mapa [--pipeline-version X.Y.Z]
  python slice_requirements_context.py [raiz] [--features FG-01 FG-02] [--pipeline-version X.Y.Z]
                                       [--replan --delta INC-002 CR-001]
  python slice_requirements_context.py [raiz] --limpiar
  python slice_requirements_context.py --self-test

Exit 0 con las tajadas escritas; exit 1 si falta requirements.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

CONTEXT_DIR = ".derivation-context"
SKELETON = "skeleton.json"


def load(path, required=False):
    if not path.is_file():
        if required:
            print("ERROR: no existe %s" % path)
            sys.exit(1)
        print("aviso: no existe %s — la tajada sale sin esa fuente" % path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        if required:
            print("ERROR: %s ilegible: %s" % (path, exc))
            sys.exit(1)
        print("aviso: %s ilegible (%s) — la tajada sale sin esa fuente" % (path, exc))
        return None


def intersects(a, b):
    return bool(set(a or []) & set(b or []))


def all_reqs(reqs_doc):
    return (reqs_doc.get("functional_requirements") or []) + (reqs_doc.get("non_functional_requirements") or [])


def applied_changelog(changelog_doc):
    return [e for e in (changelog_doc or {}).get("entries") or [] if e.get("status") == "applied"]


def build_mapa(reqs_doc, design_doc, changelog_doc, pipeline_version):
    reqs = []
    for r in all_reqs(reqs_doc):
        reqs.append({
            "id": r.get("id"), "title": r.get("title"), "feature_group": r.get("feature_group"),
            "status": r.get("status"), "priority": r.get("priority"), "estimated_effort": r.get("estimated_effort"),
            "category": r.get("category"), "depends_on": r.get("depends_on") or [],
            "statement": (r.get("statement") or "")[:200],
            "acceptance_criteria_count": len(r.get("acceptance_criteria") or []),
        })
    design = {}
    if design_doc is not None:
        design = {
            "stack": design_doc.get("stack") or [],
            "modules": [{"id": m.get("id"), "name": m.get("name"), "requirement_ids": m.get("requirement_ids") or [],
                         "feature_group": m.get("feature_group")} for m in design_doc.get("modules") or []],
            "api_contracts": [{"id": a.get("id"), "name": a.get("name"), "method": a.get("method"), "path": a.get("path"),
                               "requirement_ids": a.get("requirement_ids") or []} for a in design_doc.get("api_contracts") or []],
        }
    return {
        "generated_by": "slice_requirements_context.py --mapa",
        "pipeline_version": pipeline_version,
        "source_versions": {"requirements": reqs_doc.get("version"),
                            "technical_design": design_doc.get("version") if design_doc else None},
        "project": reqs_doc.get("project") or {},
        "feature_groups": reqs_doc.get("feature_groups") or [],
        "requirements": reqs,
        "design": design,
        "applied_changelog_ids": [e.get("id") for e in applied_changelog(changelog_doc)],
    }


def slice_feature(fid, reqs_doc, design_doc, data_doc, skeleton, tasks_doc, progress_doc, changelog_doc, delta, pipeline_version):
    fg = next((f for f in reqs_doc.get("feature_groups") or [] if f.get("id") == fid), None)
    reqs = [r for r in all_reqs(reqs_doc) if r.get("feature_group") == fid]
    req_ids = {r.get("id") for r in reqs}
    # requisitos de otras features de los que dependen los propios (solo proyeccion)
    dep_ids = {d if isinstance(d, str) else d.get("requirement_id") for r in reqs for d in r.get("depends_on") or []} - req_ids
    external = [{"id": r.get("id"), "title": r.get("title"), "feature_group": r.get("feature_group"), "statement": (r.get("statement") or "")[:200]}
                for r in all_reqs(reqs_doc) if r.get("id") in dep_ids]
    rules = [br for br in reqs_doc.get("business_rules") or []
             if any(ref.split("/", 1)[0] in req_ids for ref in br.get("enforced_by") or [])]
    design = {}
    if design_doc is not None:
        design = {
            "stack": design_doc.get("stack") or [],
            "modules": [m for m in design_doc.get("modules") or []
                        if m.get("feature_group") == fid or intersects(m.get("requirement_ids"), req_ids)],
            "api_contracts": [a for a in design_doc.get("api_contracts") or [] if intersects(a.get("requirement_ids"), req_ids)],
            "screens": [s for s in design_doc.get("screens") or [] if intersects(s.get("requirement_ids"), req_ids)],
            "decisions": [d for d in design_doc.get("decisions") or [] if intersects(d.get("requirement_ids"), req_ids)],
        }
    entities = []
    if data_doc is not None:
        entities = [e for e in data_doc.get("entities") or [] if intersects(e.get("source_requirement_ids"), req_ids)]

    sk = {}
    if skeleton is not None:
        sk = {
            "features": skeleton.get("features") or [],
            "cross_feature_edges": [e for e in skeleton.get("cross_feature_edges") or []
                                    if fid in (e.get("consumer_feature_id"), e.get("producer_feature_id"))],
            "contract_tasks": [t for t in skeleton.get("contract_tasks") or []
                               if t.get("feature_group") == fid or fid in (t.get("consumer_feature_ids") or [])],
        }

    replan = None
    if tasks_doc is not None:
        prev_tasks = [t for t in tasks_doc.get("tasks") or [] if t.get("feature_group") == fid]
        prev_ids = {t.get("id") for t in prev_tasks}
        prog = {}
        for e in (progress_doc or {}).get("tasks") or []:
            if e.get("task_id") in prev_ids:
                prog[e["task_id"]] = e.get("status", "pending")
        fprog = next((e for e in (progress_doc or {}).get("features") or [] if e.get("feature_id") == fid), None)
        entries = [e for e in applied_changelog(changelog_doc)
                   if (not delta or e.get("id") in delta) and (fid in (e.get("feature_ids") or [])
                   or intersects([v.get("requirement_id") for v in e.get("verdicts") or []], req_ids))]
        replan = {
            "feature_status": (fprog or {}).get("status", "pending"),
            "previous_tasks": prev_tasks,
            "task_status": prog,
            "changelog_entries": entries,
            "next_task_number_hint": max([int(t.get("id", "T-0").split("-")[-1]) for t in tasks_doc.get("tasks") or []] or [0]) + 1,
        }

    return {
        "generated_by": "slice_requirements_context.py",
        "pipeline_version": pipeline_version,
        "source_versions": {
            "requirements": reqs_doc.get("version"),
            "technical_design": design_doc.get("version") if design_doc else None,
            "data_model": data_doc.get("version") if data_doc else None,
            "tasks": tasks_doc.get("version") if tasks_doc else None,
        },
        "project": reqs_doc.get("project") or {},
        "feature": fg or {"id": fid},
        "requirements": reqs,
        "external_requirements": external,
        "business_rules": rules,
        "design": design,
        "entities": entities,
        "skeleton": sk,
        "replan": replan,
    }


def run(root, only, mapa, replan, delta, pipeline_version):
    req_dir = root / ".dev" / "requirements"
    plan_dir = root / ".dev" / "plan"
    reqs_doc = load(req_dir / "requirements.json", required=True)
    design_doc = load(req_dir / "technical-design.json")
    changelog_doc = load(req_dir / "changelog.json") if (req_dir / "changelog.json").is_file() else None
    ctx_dir = plan_dir / CONTEXT_DIR
    ctx_dir.mkdir(parents=True, exist_ok=True)

    if mapa:
        data = build_mapa(reqs_doc, design_doc, changelog_doc, pipeline_version)
        dest = ctx_dir / "mapa.json"
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("mapa: %s (%d features, %d requisitos)" % (dest, len(data["feature_groups"]), len(data["requirements"])))
        return 0

    data_doc = load(req_dir / "data-model.json")
    skeleton = load(ctx_dir / SKELETON) if (ctx_dir / SKELETON).is_file() else None
    if skeleton is None:
        print("aviso: no hay %s — las tajadas salen sin aristas cross-feature ni contratos (corre antes la pasada global)" % SKELETON)
    tasks_doc = progress_doc = None
    if replan:
        tasks_doc = load(plan_dir / "tasks.json", required=True)
        progress_doc = load(plan_dir / "progress.json")

    fids = [f.get("id") for f in reqs_doc.get("feature_groups") or []]
    if skeleton is not None:
        for f in skeleton.get("features") or []:
            if f.get("id") not in fids:
                fids.append(f.get("id"))   # FG-00 sintetica
    targets = only or fids
    unknown = [f for f in targets if f not in fids]
    if unknown:
        print("ERROR: features desconocidas: %s" % ", ".join(unknown))
        return 1
    for fid in targets:
        data = slice_feature(fid, reqs_doc, design_doc, data_doc, skeleton, tasks_doc, progress_doc, changelog_doc, delta, pipeline_version)
        dest = ctx_dir / ("%s.json" % fid)
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("tajada: %s (%d requisitos)" % (dest, len(data["requirements"])))
    print("Listo: %d tajada(s) en %s — carpeta temporal, borrar con --limpiar en el cierre." % (len(targets), ctx_dir))
    return 0


def clean(root):
    ctx_dir = root / ".dev" / "plan" / CONTEXT_DIR
    if ctx_dir.exists():
        shutil.rmtree(ctx_dir)
        print("borrado: %s" % ctx_dir)
    else:
        print("nada que borrar: %s no existe" % ctx_dir)
    return 0


def self_test():
    import tempfile
    failures = 0

    def check(cond, label):
        nonlocal failures
        print(("self-test ok: %s" if cond else "SELF-TEST FALLO: %s") % label)
        if not cond:
            failures += 1

    tmp = Path(tempfile.mkdtemp(prefix="slice-req-"))
    try:
        req = tmp / ".dev" / "requirements"
        plan = tmp / ".dev" / "plan"
        req.mkdir(parents=True)
        plan.mkdir(parents=True)
        (req / "requirements.json").write_text(json.dumps({
            "version": 3, "project": {"name": "demo"},
            "feature_groups": [{"id": "FG-01", "name": "A", "requirement_ids": ["RF-001"]},
                               {"id": "FG-02", "name": "B", "requirement_ids": ["RF-002"]}],
            "functional_requirements": [
                {"id": "RF-001", "title": "a", "feature_group": "FG-01", "status": "active", "depends_on": [],
                 "acceptance_criteria": [{"id": "AC-001", "given": "g", "when": "w", "then": "t"}]},
                {"id": "RF-002", "title": "b", "feature_group": "FG-02", "status": "active", "depends_on": ["RF-001"],
                 "acceptance_criteria": []}],
            "non_functional_requirements": [],
            "business_rules": [{"id": "BR-001", "statement": "s", "enforced_by": ["RF-001/AC-001"]}],
        }), encoding="utf-8")
        (req / "technical-design.json").write_text(json.dumps({
            "version": 1, "modules": [{"id": "MOD-001", "requirement_ids": ["RF-001"]}, {"id": "MOD-002", "requirement_ids": ["RF-002"]}],
            "api_contracts": [], "screens": [], "decisions": []}), encoding="utf-8")
        (req / "changelog.json").write_text(json.dumps({"entries": [
            {"id": "INC-002", "status": "applied", "feature_ids": ["FG-02"], "verdicts": []}]}), encoding="utf-8")

        check(run(tmp, None, True, False, None, "1.0.0") == 0, "--mapa corre")
        mapa = json.loads((plan / CONTEXT_DIR / "mapa.json").read_text(encoding="utf-8"))
        check(len(mapa["requirements"]) == 2 and "acceptance_criteria" not in mapa["requirements"][0], "mapa: proyeccion sin criterios")
        check(mapa["applied_changelog_ids"] == ["INC-002"], "mapa: changelog aplicado")

        (plan / CONTEXT_DIR / SKELETON).write_text(json.dumps({
            "features": [{"id": "FG-01"}, {"id": "FG-02"}],
            "cross_feature_edges": [{"consumer_feature_id": "FG-02", "producer_feature_id": "FG-01", "requirement_id": "RF-001", "kind": "contract"}],
            "contract_tasks": [{"id": "K-001", "feature_group": "FG-01", "type": "contract", "consumer_feature_ids": ["FG-02"]}],
        }), encoding="utf-8")
        check(run(tmp, None, False, False, None, "1.0.0") == 0, "tajadas por feature")
        s1 = json.loads((plan / CONTEXT_DIR / "FG-01.json").read_text(encoding="utf-8"))
        s2 = json.loads((plan / CONTEXT_DIR / "FG-02.json").read_text(encoding="utf-8"))
        check([r["id"] for r in s1["requirements"]] == ["RF-001"], "FG-01: solo sus requisitos")
        check([m["id"] for m in s2["design"]["modules"]] == ["MOD-002"], "FG-02: solo su modulo")
        check(s2["external_requirements"][0]["id"] == "RF-001", "FG-02: requisito externo del que depende, proyectado")
        check(s2["skeleton"]["contract_tasks"][0]["id"] == "K-001" and s2["skeleton"]["cross_feature_edges"], "FG-02: contrato y arista del esqueleto")
        check(s1["business_rules"][0]["id"] == "BR-001" and not s2["business_rules"], "reglas de negocio por feature")

        (plan / "tasks.json").write_text(json.dumps({"version": 2, "tasks": [
            {"id": "T-001", "feature_group": "FG-01"}, {"id": "T-007", "feature_group": "FG-02"}]}), encoding="utf-8")
        (plan / "progress.json").write_text(json.dumps({"features": [{"feature_id": "FG-02", "status": "in_progress"}],
                                                        "tasks": [{"task_id": "T-007", "status": "in_progress"}]}), encoding="utf-8")
        check(run(tmp, ["FG-02"], False, True, ["INC-002"], None) == 0, "--replan acotado")
        s2 = json.loads((plan / CONTEXT_DIR / "FG-02.json").read_text(encoding="utf-8"))
        rp = s2["replan"]
        check(rp["feature_status"] == "in_progress" and rp["task_status"] == {"T-007": "in_progress"}, "replan: estado del build")
        check([t["id"] for t in rp["previous_tasks"]] == ["T-007"] and rp["next_task_number_hint"] == 8, "replan: tareas previas y siguiente id")
        check([e["id"] for e in rp["changelog_entries"]] == ["INC-002"], "replan: entradas del delta que tocan la feature")
        check(clean(tmp) == 0 and not (plan / CONTEXT_DIR).exists(), "--limpiar")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--features", nargs="+", default=None)
    ap.add_argument("--mapa", action="store_true", help="proyeccion compacta para la pasada global")
    ap.add_argument("--replan", action="store_true", help="incluir tareas previas, progress y delta del changelog")
    ap.add_argument("--delta", nargs="+", default=None, help="ids del changelog del delta (con --replan)")
    ap.add_argument("--pipeline-version", default=None)
    ap.add_argument("--limpiar", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.raiz).resolve()
    if args.limpiar:
        return clean(root)
    return run(root, args.features, args.mapa, args.replan, args.delta, args.pipeline_version)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
