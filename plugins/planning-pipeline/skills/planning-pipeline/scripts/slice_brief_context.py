#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-cortador de contexto para los briefs de feature: una tajada JSON por feature.

Los agentes de `feature-brief` corren en paralelo (uno por feature) y cada uno
necesita solo la porcion de los artefactos que toca su feature. Este script extrae
esa tajada de forma determinista, cruzando por ids (requirement_ids, module_ids,
entity_ids, lel_symbol_ids), y la escribe en `.dev/plan/.brief-context/FG-xx.json`.
Asi cada agente lee un archivo chico en vez de releer la linea de base completa:
el paralelismo no multiplica el input.

Que incluye cada tajada:
  - la feature y sus tareas completas (con estado), y su task_order del execution-plan
  - sus requisitos completos (criterios de aceptacion incluidos) y las reglas de
    negocio que sus requisitos hacen cumplir
  - su lote (con que features corre en paralelo, waits_for, rationale)
  - los contratos que produce y los que consume (con su feature productora)
  - el diseno relevante: modulos, contratos de API, pantallas, ADRs y stack
  - sus entidades del modelo de datos
  - los simbolos del LEL que sus requisitos citan (nombre + nociones)
  - las preguntas abiertas del plan que la afectan

Los artefactos de requisitos ausentes se saltean con aviso (tajada mas pobre, no
error): el brief degrada igual que degradaba el agente monolitico. La carpeta
`.brief-context/` es temporal: se borra en el cierre de la corrida con --limpiar.

Solo stdlib, Python 3.8+. No modifica los artefactos canonicos.

Uso:
  python slice_brief_context.py [raiz] [--features FG-01 FG-02] [--pipeline-version X.Y.Z]
  python slice_brief_context.py [raiz] --limpiar
  python slice_brief_context.py --self-test

Exit 0 con las tajadas escritas; exit 1 si falta tasks.json o execution-plan.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

CONTEXT_DIR = ".brief-context"


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


def batch_of(plan_doc, fid):
    for b in plan_doc.get("batches") or []:
        for e in b.get("features") or []:
            if e.get("feature_id") == fid:
                peers = [x.get("feature_id") for x in b.get("features") or [] if x.get("feature_id") != fid]
                return {
                    "batch_id": b.get("id"),
                    "unlocks_after": b.get("unlocks_after") or [],
                    "rationale": b.get("rationale"),
                    "parallel_feature_ids": peers,
                    "adjustment": bool(e.get("adjustment")),
                    "groupable": bool(e.get("groupable")),
                    "task_order": e.get("task_order") or [],
                    "waits_for": e.get("waits_for") or [],
                }
    return None


def slice_feature(fid, tasks_doc, plan_doc, reqs_doc, design_doc, data_doc, lel_doc, pipeline_version):
    feature = next((f for f in tasks_doc.get("features") or [] if f.get("id") == fid), None)
    ftasks = [t for t in tasks_doc.get("tasks") or [] if t.get("feature_group") == fid]
    ftask_ids = {t.get("id") for t in ftasks}
    all_tasks = {t.get("id"): t for t in tasks_doc.get("tasks") or []}

    # requisitos propios de la feature (filtran diseno y entidades) vs. los que
    # ademas citan sus tareas-contrato (trazan la costura: van en la lista, no filtran)
    own_req_ids = set(feature.get("requirement_ids") or []) if feature else set()
    req_ids = set(own_req_ids)
    for t in ftasks:
        cited = set(t.get("requirement_ids") or [])
        req_ids |= cited
        if t.get("type") != "contract":
            own_req_ids |= cited

    reqs = []
    lel_ids = set()
    if reqs_doc is not None:
        for r in (reqs_doc.get("functional_requirements") or []) + (reqs_doc.get("non_functional_requirements") or []):
            if r.get("id") in req_ids or r.get("feature_group") == fid:
                reqs.append(r)
                req_ids.add(r.get("id"))
                if r.get("feature_group") == fid:
                    own_req_ids.add(r.get("id"))
                    lel_ids |= set(r.get("lel_symbol_ids") or [])
    rules = []
    if reqs_doc is not None:
        for br in reqs_doc.get("business_rules") or []:
            if any(ref.split("/", 1)[0] in req_ids for ref in br.get("enforced_by") or []):
                rules.append(br)

    module_ids = set()
    entity_ids = set()
    for t in ftasks:
        module_ids |= set(t.get("module_ids") or [])
        entity_ids |= set(t.get("entity_ids") or [])

    design = {}
    if design_doc is not None:
        design = {
            "stack": design_doc.get("stack") or [],
            "modules": [m for m in design_doc.get("modules") or []
                        if m.get("id") in module_ids or m.get("feature_group") == fid
                        or intersects(m.get("requirement_ids"), own_req_ids)],
            "api_contracts": [a for a in design_doc.get("api_contracts") or []
                              if intersects(a.get("requirement_ids"), own_req_ids)],
            "screens": [s for s in design_doc.get("screens") or []
                        if intersects(s.get("requirement_ids"), own_req_ids)],
            "decisions": [d for d in design_doc.get("decisions") or []
                          if intersects(d.get("requirement_ids"), own_req_ids)],
        }

    entities = []
    if data_doc is not None:
        entities = [e for e in data_doc.get("entities") or []
                    if e.get("id") in entity_ids or intersects(e.get("source_requirement_ids"), own_req_ids)]

    symbols = []
    if lel_doc is not None:
        for s in lel_doc.get("symbols") or []:
            if s.get("id") in lel_ids:
                symbols.append({
                    "id": s.get("id"),
                    "canonical_name": s.get("canonical_name"),
                    "type": s.get("type"),
                    "notions": [n.get("statement") for n in s.get("notions") or []],
                    "aliases": s.get("aliases") or [],
                })

    produces = [t for t in ftasks if t.get("type") == "contract"]
    consumed_ids = set()
    for t in ftasks:
        for dep in t.get("depends_on") or []:
            if isinstance(dep, dict) and dep.get("kind") == "contract" and dep.get("task_id") not in ftask_ids:
                consumed_ids.add(dep.get("task_id"))
    consumes = [{"task": all_tasks[i], "producer_feature_id": all_tasks[i].get("feature_group")}
                for i in sorted(consumed_ids) if i in all_tasks]

    questions = [q for q in tasks_doc.get("open_questions") or []
                 if intersects(q.get("related_task_ids"), ftask_ids)]

    return {
        "generated_by": "slice_brief_context.py",
        "pipeline_version": pipeline_version,
        "source_versions": {
            "tasks": tasks_doc.get("version"),
            "execution_plan": plan_doc.get("version"),
            "requirements": reqs_doc.get("version") if reqs_doc else None,
            "technical_design": design_doc.get("version") if design_doc else None,
            "data_model": data_doc.get("version") if data_doc else None,
            "lel": lel_doc.get("version") if lel_doc else None,
        },
        "project": tasks_doc.get("project") or {},
        "feature": feature,
        "tasks": ftasks,
        "batch": batch_of(plan_doc, fid),
        "contract_round": plan_doc.get("contract_round"),
        "requirements": reqs,
        "business_rules": rules,
        "design": design,
        "entities": entities,
        "lel_symbols": symbols,
        "contracts": {"produces": produces, "consumes": consumes},
        "open_questions": questions,
    }


# ------------------------------------------------------------------ self-test


def self_test():
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="slice-brief-"))
    failures = 0

    def check(cond, label):
        nonlocal failures
        if cond:
            print("self-test ok: %s" % label)
        else:
            failures += 1
            print("SELF-TEST FALLO: %s" % label)

    try:
        plan = tmp / ".dev" / "plan"
        req = tmp / ".dev" / "requirements"
        plan.mkdir(parents=True)
        req.mkdir(parents=True)
        (plan / "tasks.json").write_text(json.dumps({
            "version": 2, "project": {"name": "demo"},
            "features": [
                {"id": "FG-01", "name": "A", "requirement_ids": ["RF-001"], "task_ids": ["T-001", "T-002"]},
                {"id": "FG-02", "name": "B", "requirement_ids": ["RF-002"], "task_ids": ["T-003"]},
            ],
            "tasks": [
                {"id": "T-001", "feature_group": "FG-01", "type": "contract", "status": "pending",
                 "depends_on": [], "requirement_ids": ["RF-001", "RF-002"]},
                {"id": "T-002", "feature_group": "FG-01", "type": "feature", "status": "pending",
                 "depends_on": [], "requirement_ids": ["RF-001"], "module_ids": ["MOD-001"],
                 "entity_ids": ["ENT-001"]},
                {"id": "T-003", "feature_group": "FG-02", "type": "feature", "status": "pending",
                 "depends_on": [{"task_id": "T-001", "kind": "contract"}], "requirement_ids": ["RF-002"]},
            ],
            "open_questions": [{"id": "Q-001", "question": "q", "related_task_ids": ["T-003"]}],
        }), encoding="utf-8")
        (plan / "execution-plan.json").write_text(json.dumps({
            "version": 1,
            "contract_round": {"id": "BATCH-0", "task_ids": ["T-001"]},
            "batches": [{"id": "BATCH-1", "unlocks_after": ["BATCH-0"], "rationale": "r",
                         "features": [
                             {"feature_id": "FG-01", "task_ids": ["T-002"], "task_order": ["T-002"], "waits_for": []},
                             {"feature_id": "FG-02", "task_ids": ["T-003"], "task_order": ["T-003"], "waits_for": []},
                         ]}],
        }), encoding="utf-8")
        (req / "requirements.json").write_text(json.dumps({
            "version": 5,
            "functional_requirements": [
                {"id": "RF-001", "feature_group": "FG-01", "status": "active", "lel_symbol_ids": ["LEL-001"],
                 "acceptance_criteria": [{"id": "AC-001", "given": "g", "when": "w", "then": "t"}]},
                {"id": "RF-002", "feature_group": "FG-02", "status": "active", "lel_symbol_ids": [],
                 "acceptance_criteria": [{"id": "AC-001", "given": "g", "when": "w", "then": "t"}]},
            ],
            "non_functional_requirements": [],
            "business_rules": [
                {"id": "BR-001", "statement": "s", "enforced_by": ["RF-001/AC-001"]},
                {"id": "BR-002", "statement": "s", "enforced_by": ["RF-002/AC-001"]},
            ],
        }), encoding="utf-8")
        (req / "technical-design.json").write_text(json.dumps({
            "version": 3, "stack": [{"layer": "web", "technology": "x"}],
            "modules": [{"id": "MOD-001", "feature_group": "FG-01", "requirement_ids": ["RF-001"]},
                        {"id": "MOD-002", "feature_group": "FG-02", "requirement_ids": ["RF-002"]}],
            "api_contracts": [{"id": "API-001", "requirement_ids": ["RF-001"], "auth_required": True}],
            "screens": [], "decisions": [],
        }), encoding="utf-8")
        (req / "data-model.json").write_text(json.dumps({
            "version": 4,
            "entities": [{"id": "ENT-001", "name": "e", "source_requirement_ids": ["RF-001"]},
                         {"id": "ENT-002", "name": "f", "source_requirement_ids": ["RF-002"]}],
        }), encoding="utf-8")
        (req / "lel.json").write_text(json.dumps({
            "version": 6,
            "symbols": [{"id": "LEL-001", "canonical_name": "turno", "type": "objeto",
                         "notions": [{"id": "NOT-001", "statement": "n"}]},
                        {"id": "LEL-002", "canonical_name": "otro", "type": "objeto", "notions": []}],
        }), encoding="utf-8")

        code = run(tmp, None, "9.9.9")
        check(code == 0, "corrida sobre fixture (exit 0)")
        ctx_dir = plan / CONTEXT_DIR
        s1 = json.loads((ctx_dir / "FG-01.json").read_text(encoding="utf-8"))
        s2 = json.loads((ctx_dir / "FG-02.json").read_text(encoding="utf-8"))
        check({t["id"] for t in s1["tasks"]} == {"T-001", "T-002"}, "FG-01: sus tareas y solo las suyas")
        check([r["id"] for r in s1["requirements"]] == ["RF-001", "RF-002"],
              "FG-01: sus requisitos (RF-002 entra por la tarea-contrato)")
        check([r["id"] for r in s2["requirements"]] == ["RF-002"], "FG-02: solo su requisito")
        check([m["id"] for m in s2["design"]["modules"]] == ["MOD-002"], "FG-02: solo su modulo")
        check([e["id"] for e in s1["entities"]] == ["ENT-001"], "FG-01: solo su entidad")
        check([s["id"] for s in s1["lel_symbols"]] == ["LEL-001"], "FG-01: solo su simbolo del LEL")
        check([b["id"] for b in s2["business_rules"]] == ["BR-002"], "FG-02: solo su regla de negocio")
        check(s2["contracts"]["consumes"][0]["task"]["id"] == "T-001"
              and s2["contracts"]["consumes"][0]["producer_feature_id"] == "FG-01",
              "FG-02: consume el contrato T-001 de FG-01")
        check(s1["contracts"]["produces"][0]["id"] == "T-001", "FG-01: produce el contrato T-001")
        check(s2["open_questions"] and s2["open_questions"][0]["id"] == "Q-001", "FG-02: su pregunta abierta")
        check(s1["batch"]["parallel_feature_ids"] == ["FG-02"], "FG-01: sabe con quien corre en paralelo")
        check(s1["pipeline_version"] == "9.9.9", "pipeline_version estampada")

        code = run(tmp, ["FG-02"], None)
        check(code == 0, "corrida acotada con --features")

        code = clean(tmp)
        check(code == 0 and not ctx_dir.exists(), "--limpiar borra la carpeta temporal")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


# ----------------------------------------------------------------------- main


def run(root, only_features, pipeline_version):
    plan_dir = root / ".dev" / "plan"
    req_dir = root / ".dev" / "requirements"
    tasks_doc = load(plan_dir / "tasks.json", required=True)
    plan_doc = load(plan_dir / "execution-plan.json", required=True)
    reqs_doc = load(req_dir / "requirements.json")
    design_doc = load(req_dir / "technical-design.json")
    data_doc = load(req_dir / "data-model.json")
    lel_doc = load(req_dir / "lel.json")

    with_tasks = sorted({t.get("feature_group") for t in tasks_doc.get("tasks") or []
                         if t.get("status", "pending") != "cancelled"})
    targets = only_features or with_tasks
    unknown = [f for f in targets if f not in with_tasks]
    if unknown:
        print("ERROR: features sin tareas activas en el plan: %s" % ", ".join(unknown))
        return 1

    ctx_dir = plan_dir / CONTEXT_DIR
    ctx_dir.mkdir(parents=True, exist_ok=True)
    for fid in targets:
        data = slice_feature(fid, tasks_doc, plan_doc, reqs_doc, design_doc, data_doc, lel_doc, pipeline_version)
        dest = ctx_dir / ("%s.json" % fid)
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("tajada: %s (%d tareas, %d requisitos)" % (dest, len(data["tasks"]), len(data["requirements"])))
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


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--features", nargs="+", default=None, help="acotar a estas features (default: todas con tareas)")
    ap.add_argument("--pipeline-version", default=None)
    ap.add_argument("--limpiar", action="store_true", help="borrar .brief-context/ y salir")
    args = ap.parse_args(argv)
    root = Path(args.raiz).resolve()
    if args.limpiar:
        return clean(root)
    return run(root, args.features, args.pipeline_version)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
