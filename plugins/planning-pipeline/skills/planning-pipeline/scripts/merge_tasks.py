#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge determinista de la derivacion por feature: esqueleto + parciales -> tasks.json

La derivacion de tareas corre en dos fases: una pasada global de `task-derivation`
escribe `.dev/plan/.derivation-context/skeleton.json` (features, aristas
cross-feature, tareas-contrato) y N pasadas en paralelo (una por feature) escriben
`.dev/plan/.derivation-context/tasks.FG-xx.json`. Este script los consolida en
`.dev/plan/tasks.json` sin tokens de modelo:

  - asigna ids globales `T-nnn` (contratos del esqueleto primero, despues las
    features en orden) a los ids locales `K-nnn` (contratos) y `L-nnn` (parciales),
    y reescribe toda referencia (depends_on, task_ids, related_task_ids,
    adjusts_task_id, traceability_links);
  - resuelve las dependencias cross-feature expresadas a nivel requisito
    (`{"feature_id": "FG-02", "requirement_id": "RF-005", "kind": "hard"}`) hacia
    las tareas de la feature productora que citan ese requisito;
  - recalcula `summary`, `features[].task_ids`, `version` y `metadata`.

En replanificacion (--replan) parte del `tasks.json` existente: las features no
afectadas quedan byte a byte, los ids `T-nnn` de los parciales se conservan (tareas
reescritas), los `L-nnn` continuan la numeracion, y una tarea previa de una feature
afectada que el parcial no menciona es ERROR (nunca se pierde una tarea: se cancela
explicitamente con status cancelled).

Solo stdlib, Python 3.8+.

Uso:
  python merge_tasks.py [raiz] [--pipeline-version X.Y.Z] [--ahora ISO]
  python merge_tasks.py [raiz] --replan --features FG-02 FG-05 [--delta INC-002] [--deferred CR-003]
  python merge_tasks.py --self-test

Exit 0 con tasks.json escrito; exit 1 ante parciales faltantes, ids duplicados,
referencias irresolubles o tareas previas perdidas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CONTEXT_DIR = ".derivation-context"
LOCAL_ID = re.compile(r"^[KL]-\d+$")
GLOBAL_ID = re.compile(r"^T-\d+$")


def fail(msg):
    print("ERROR: %s" % msg)
    sys.exit(1)


def load(path, required=True):
    if not path.is_file():
        if required:
            fail("no existe %s" % path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        fail("%s ilegible: %s" % (path, exc))


def tnum(tid):
    return int(str(tid).split("-")[-1])


def fnum(fid):
    return int(str(fid).split("-")[-1]) if str(fid).split("-")[-1].isdigit() else 999


def merge(skeleton, partials, previous, replan, affected, delta, deferred, pipeline_version, now):
    """partials: {fid: doc}. Devuelve el tasks.json consolidado."""
    prev_tasks = list((previous or {}).get("tasks") or []) if replan else []
    prev_by_feature = {}
    for t in prev_tasks:
        prev_by_feature.setdefault(t.get("feature_group"), []).append(t)
    kept = [t for t in prev_tasks if t.get("feature_group") not in affected] if replan else []
    next_num = max([tnum(t["id"]) for t in prev_tasks] or [0]) + 1

    # mapa de ids: (ambito, id_local) -> T-nnn ; ambito "K" para contratos, fid para parciales
    idmap = {}
    warnings = list(skeleton.get("warnings") or [])
    merged = []

    def assign(scope, local):
        nonlocal next_num
        key = (scope, local)
        if key in idmap:
            return idmap[key]
        if GLOBAL_ID.match(local):
            idmap[key] = local
            return local
        if not LOCAL_ID.match(local):
            fail("id invalido %r en %s: se esperaba K-nnn, L-nnn o T-nnn" % (local, scope))
        idmap[key] = "T-%03d" % next_num
        next_num += 1
        return idmap[key]

    # 1) contratos del esqueleto
    for t in skeleton.get("contract_tasks") or []:
        t = dict(t)
        t["id"] = assign("K", t["id"])
        t.setdefault("type", "contract")
        t.setdefault("status", "pending")
        t.pop("consumer_feature_ids", None)
        merged.append(t)
    # 2) parciales, en orden de feature
    for fid in sorted(partials, key=fnum):
        seen = set()
        for t in partials[fid].get("tasks") or []:
            t = dict(t)
            if t.get("feature_group") not in (None, fid):
                fail("%s: la tarea %s declara feature_group %s" % (fid, t.get("id"), t.get("feature_group")))
            t["feature_group"] = fid
            t["id"] = assign(fid, t["id"])
            if t["id"] in seen:
                fail("%s: id repetido %s" % (fid, t["id"]))
            seen.add(t["id"])
            t.setdefault("status", "pending")
            merged.append(t)
        if replan:
            missing = [p["id"] for p in prev_by_feature.get(fid, []) if p["id"] not in seen]
            if missing:
                fail("%s: el parcial no menciona las tareas previas %s (cancelalas explicitamente, no las omitas)" % (fid, ", ".join(missing)))

    all_tasks = kept + merged
    by_id = {t["id"]: t for t in all_tasks}
    if len(by_id) != len(all_tasks):
        fail("ids duplicados tras el merge")
    by_feature = {}
    for t in all_tasks:
        by_feature.setdefault(t.get("feature_group"), []).append(t)

    # 3) reescribir referencias
    def resolve_ref(scope, ref):
        if isinstance(ref, dict) and ref.get("requirement_id") and ref.get("feature_id"):
            prods = [t["id"] for t in by_feature.get(ref["feature_id"], [])
                     if ref["requirement_id"] in (t.get("requirement_ids") or []) and t.get("type") != "contract"
                     and t.get("status", "pending") != "cancelled"]
            if not prods:
                prods = [t["id"] for t in by_feature.get(ref["feature_id"], []) if t.get("status", "pending") != "cancelled"]
                warnings.append("dependencia de %s sobre %s/%s: ninguna tarea de la productora cita ese requisito; se apunta a todas sus tareas"
                                % (scope, ref["feature_id"], ref["requirement_id"]))
            if not prods:
                fail("%s: dependencia sobre %s/%s irresoluble (la feature no tiene tareas)" % (scope, ref["feature_id"], ref["requirement_id"]))
            return [{"task_id": p, "kind": ref.get("kind", "hard")} for p in sorted(prods, key=tnum)]
        local = ref.get("task_id") if isinstance(ref, dict) else ref
        if local.startswith("K-"):
            target = idmap.get(("K", local))
        elif local.startswith("L-"):
            target = idmap.get((scope, local))
        else:
            target = local if local in by_id else None
        if target is None:
            fail("%s: referencia irresoluble %r" % (scope, local))
        return [{"task_id": target, "kind": ref.get("kind", "hard")}] if isinstance(ref, dict) else [target]

    def rewrite_list(scope, seq):
        out = []
        for ref in seq or []:
            for r in resolve_ref(scope, ref):
                if r not in out:
                    out.append(r)
        return out

    for t in merged:
        scope = t["feature_group"] if t["feature_group"] in partials else "K"
        t["depends_on"] = rewrite_list(scope, t.get("depends_on"))
        if t.get("adjusts_task_id"):
            t["adjusts_task_id"] = resolve_ref(scope, t["adjusts_task_id"])[0]

    # 4) features, preguntas, trazabilidad
    features = []
    sk_feats = {f.get("id"): f for f in skeleton.get("features") or []}
    prev_feats = {f.get("id"): f for f in (previous or {}).get("features") or []} if replan else {}
    for fid in sorted(set(by_feature) | set(sk_feats) | set(prev_feats), key=fnum):
        base = dict(prev_feats.get(fid) or sk_feats.get(fid) or {"id": fid})
        if fid in partials and partials[fid].get("feature"):
            base.update({k: v for k, v in partials[fid]["feature"].items() if k != "task_ids"})
        base["id"] = fid
        base["task_ids"] = [t["id"] for t in sorted(by_feature.get(fid, []), key=lambda t: tnum(t["id"]))]
        base.setdefault("synthetic", False)
        features.append(base)

    questions = list((previous or {}).get("open_questions") or []) if replan else []
    questions = [q for q in questions if not any(rt in {p["id"] for f in affected for p in prev_by_feature.get(f, [])} for rt in q.get("related_task_ids") or [])]
    links = list((previous or {}).get("traceability_links") or []) if replan else []
    assumptions = list(skeleton.get("assumptions") or [])
    qnum = max([int(q["id"].split("-")[-1]) for q in questions if q.get("id")] or [0]) + 1
    for src in [skeleton] + [partials[f] for f in sorted(partials, key=fnum)]:
        scope = "K" if src is skeleton else (src.get("feature") or {}).get("id") or next(f for f in partials if partials[f] is src)
        for q in src.get("open_questions") or []:
            q = dict(q)
            q["related_task_ids"] = rewrite_list(scope, q.get("related_task_ids"))
            q["id"] = "Q-%03d" % qnum
            qnum += 1
            questions.append(q)
        for l in src.get("traceability_links") or []:
            l = json.loads(json.dumps(l))
            for end in ("source", "target"):
                if l.get(end, {}).get("kind") == "task":
                    l[end]["id"] = resolve_ref(scope, l[end]["id"])[0]
            links.append(l)
        assumptions += src.get("assumptions") or [] if src is not skeleton else []
        warnings += src.get("warnings") or [] if src is not skeleton else []

    # 5) summary y metadata
    active = [t for t in all_tasks if t.get("status", "pending") != "cancelled"]
    covered = sorted({r for t in active for r in t.get("requirement_ids") or []})
    active_reqs = skeleton.get("active_requirement_ids") or (previous or {}).get("summary", {}).get("covered_requirement_ids") or []
    uncovered = sorted(set(active_reqs) - set(covered))
    cx = {"low": 0, "medium": 0, "high": 0}
    for t in active:
        cx[t.get("complexity")] = cx.get(t.get("complexity"), 0) + 1
    meta_prev = (previous or {}).get("metadata") or {}
    meta_sk = skeleton.get("metadata") or {}
    applied = list(meta_prev.get("applied_changelog_ids") or []) if replan else list(meta_sk.get("applied_changelog_ids") or [])
    deferred_ids = [d for d in (meta_prev.get("deferred_changelog_ids") or []) if d not in (delta or [])] if replan else []
    for d in delta or []:
        if d not in applied:
            applied.append(d)
    for d in deferred or []:
        if d not in deferred_ids and d not in applied:
            deferred_ids.append(d)
    if not replan:
        deferred_ids = list(meta_sk.get("deferred_changelog_ids") or []) + [d for d in deferred or []]
    all_sorted = sorted(all_tasks, key=lambda t: tnum(t["id"]))
    return {
        "version": int((previous or {}).get("version", 0)) + 1,
        "project": skeleton.get("project") or (previous or {}).get("project") or {},
        "metadata": {
            "created_at": meta_prev.get("created_at") or now,
            "updated_at": now,
            "requirements_version_ref": meta_sk.get("requirements_version_ref") or meta_prev.get("requirements_version_ref"),
            "technical_design_version_ref": meta_sk.get("technical_design_version_ref") or meta_prev.get("technical_design_version_ref"),
            "applied_changelog_ids": applied,
            "deferred_changelog_ids": deferred_ids,
            "pipeline_version": pipeline_version,
            "generated_by": "merge_tasks.py",
        },
        "summary": {
            "feature_count": len([f for f in features if f["task_ids"]]),
            "task_count": len(all_sorted),
            "covered_requirement_ids": covered,
            "uncovered_requirement_ids": uncovered,
            "complexity_breakdown": cx,
        },
        "features": features,
        "tasks": all_sorted,
        "open_questions": questions,
        "traceability_links": links,
        "assumptions": assumptions,
        "warnings": warnings,
    }


def run(root, replan, affected, delta, deferred, pipeline_version, now):
    plan_dir = root / ".dev" / "plan"
    ctx = plan_dir / CONTEXT_DIR
    skeleton = load(ctx / "skeleton.json")
    partials = {}
    for p in sorted(ctx.glob("tasks.FG-*.json")):
        fid = p.name[len("tasks."):-len(".json")]
        partials[fid] = load(p)
    if not partials:
        fail("no hay parciales tasks.FG-xx.json en %s" % ctx)
    previous = None
    if replan:
        previous = load(plan_dir / "tasks.json")
        affected = affected or sorted(partials)
        missing = [f for f in affected if f not in partials]
        if missing:
            fail("features afectadas sin parcial: %s" % ", ".join(missing))
        extra = [f for f in partials if f not in affected]
        if extra:
            fail("parciales de features no afectadas: %s" % ", ".join(extra))
    elif (plan_dir / "tasks.json").is_file():
        print("aviso: tasks.json existe y no es --replan: se regenera completo (ids nuevos)")
    doc = merge(skeleton, partials, previous, replan, set(affected or []), delta, deferred, pipeline_version, now)
    (plan_dir / "tasks.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = doc["summary"]
    print("escrito: %s (version %s) — %d features, %d tareas, sin cubrir: %s"
          % (plan_dir / "tasks.json", doc["version"], s["feature_count"], s["task_count"], ", ".join(s["uncovered_requirement_ids"]) or "ninguno"))
    for w in doc["warnings"]:
        print("aviso: %s" % w)
    return 0


def self_test():
    import shutil
    import tempfile
    failures = 0

    def check(cond, label):
        nonlocal failures
        print(("self-test ok: %s" if cond else "SELF-TEST FALLO: %s") % label)
        if not cond:
            failures += 1

    tmp = Path(tempfile.mkdtemp(prefix="merge-tasks-"))
    try:
        ctx = tmp / ".dev" / "plan" / CONTEXT_DIR
        ctx.mkdir(parents=True)
        (ctx / "skeleton.json").write_text(json.dumps({
            "project": {"name": "demo"},
            "features": [{"id": "FG-01", "name": "A", "requirement_ids": ["RF-001"]}, {"id": "FG-02", "name": "B", "requirement_ids": ["RF-002"]}],
            "cross_feature_edges": [{"consumer_feature_id": "FG-02", "producer_feature_id": "FG-01", "requirement_id": "RF-001", "kind": "contract"}],
            "contract_tasks": [{"id": "K-001", "title": "firma", "feature_group": "FG-01", "type": "contract", "complexity": "low",
                                "priority": "high", "depends_on": [], "requirement_ids": ["RF-001", "RF-002"], "consumer_feature_ids": ["FG-02"]}],
            "active_requirement_ids": ["RF-001", "RF-002", "RF-003"],
            "metadata": {"requirements_version_ref": "3", "technical_design_version_ref": "1", "applied_changelog_ids": ["INC-001"]},
        }), encoding="utf-8")
        (ctx / "tasks.FG-01.json").write_text(json.dumps({
            "feature": {"id": "FG-01", "description": "desc A"},
            "tasks": [{"id": "L-001", "title": "a1", "complexity": "medium", "priority": "high", "depends_on": [{"task_id": "K-001", "kind": "contract"}], "requirement_ids": ["RF-001"]},
                      {"id": "L-002", "title": "a2", "complexity": "low", "priority": "high", "depends_on": [{"task_id": "L-001", "kind": "hard"}], "requirement_ids": ["RF-001"]}],
            "open_questions": [{"id": "Q-001", "question": "q", "related_task_ids": ["L-002"]}],
            "traceability_links": [{"source": {"kind": "task", "id": "L-001"}, "target": {"kind": "requirement", "id": "RF-001"}, "relationship": "covers"}],
        }), encoding="utf-8")
        (ctx / "tasks.FG-02.json").write_text(json.dumps({
            "tasks": [{"id": "L-001", "title": "b1", "complexity": "low", "priority": "medium",
                       "depends_on": [{"task_id": "K-001", "kind": "contract"}, {"feature_id": "FG-01", "requirement_id": "RF-001", "kind": "hard"}],
                       "requirement_ids": ["RF-002"]}],
        }), encoding="utf-8")
        check(run(tmp, False, None, None, None, "9.9.9", "2026-01-01T00:00:00+00:00") == 0, "merge inicial")
        doc = json.loads((tmp / ".dev" / "plan" / "tasks.json").read_text(encoding="utf-8"))
        ids_ = [t["id"] for t in doc["tasks"]]
        check(ids_ == ["T-001", "T-002", "T-003", "T-004"], "ids globales contiguos (%s)" % ids_)
        a2 = next(t for t in doc["tasks"] if t["title"] == "a2")
        b1 = next(t for t in doc["tasks"] if t["title"] == "b1")
        check(a2["depends_on"] == [{"task_id": "T-002", "kind": "hard"}], "L-nnn local reescrito por feature")
        check({"task_id": "T-001", "kind": "contract"} in b1["depends_on"], "K-nnn reescrito")
        check({"task_id": "T-002", "kind": "hard"} in b1["depends_on"] and {"task_id": "T-003", "kind": "hard"} in b1["depends_on"],
              "dependencia a nivel requisito resuelta a las tareas productoras")
        check(doc["summary"]["uncovered_requirement_ids"] == ["RF-003"] and doc["summary"]["task_count"] == 4, "summary recalculado")
        check(doc["open_questions"][0]["related_task_ids"] == ["T-003"] and doc["traceability_links"][0]["source"]["id"] == "T-002", "preguntas y trazabilidad reescritas")
        check(doc["features"][0]["task_ids"] == ["T-001", "T-002", "T-003"] and doc["features"][0]["description"] == "desc A", "features con task_ids y datos del parcial")
        check(doc["metadata"]["applied_changelog_ids"] == ["INC-001"] and doc["version"] == 1, "metadata inicial")

        # replanificacion: solo FG-02, conserva T-004 reescrita y agrega una nueva
        for p in ctx.glob("tasks.FG-*.json"):
            p.unlink()
        (ctx / "skeleton.json").write_text(json.dumps({"features": [], "contract_tasks": [], "metadata": {}}), encoding="utf-8")
        (ctx / "tasks.FG-02.json").write_text(json.dumps({"tasks": [
            {"id": "T-004", "title": "b1 v2", "complexity": "low", "priority": "medium", "depends_on": [{"task_id": "T-001", "kind": "contract"}], "requirement_ids": ["RF-002"]},
            {"id": "L-001", "title": "b2", "complexity": "low", "priority": "low", "depends_on": [{"task_id": "T-004", "kind": "hard"}], "requirement_ids": ["RF-002"], "adjusts_task_id": "T-004"}]}), encoding="utf-8")
        check(run(tmp, True, ["FG-02"], ["INC-002"], ["CR-009"], "9.9.9", "2026-01-02T00:00:00+00:00") == 0, "replan corre")
        doc2 = json.loads((tmp / ".dev" / "plan" / "tasks.json").read_text(encoding="utf-8"))
        check([t["id"] for t in doc2["tasks"]] == ["T-001", "T-002", "T-003", "T-004", "T-005"], "replan: ids continuan")
        check(next(t for t in doc2["tasks"] if t["id"] == "T-002")["title"] == "a1" and doc2["version"] == 2, "replan: FG-01 intacta, version +1")
        check(next(t for t in doc2["tasks"] if t["id"] == "T-005")["adjusts_task_id"] == "T-004", "replan: adjusts_task_id resuelto")
        check(doc2["metadata"]["applied_changelog_ids"] == ["INC-001", "INC-002"] and doc2["metadata"]["deferred_changelog_ids"] == ["CR-009"], "replan: changelog aplicado y postergado")
        # tarea previa omitida -> error
        (ctx / "tasks.FG-02.json").write_text(json.dumps({"tasks": [{"id": "L-001", "title": "x", "complexity": "low", "depends_on": [], "requirement_ids": ["RF-002"]}]}), encoding="utf-8")
        try:
            run(tmp, True, ["FG-02"], None, None, None, None)
            check(False, "replan: tarea previa omitida debe fallar")
        except SystemExit as e:
            check(e.code == 1, "replan: tarea previa omitida falla con exit 1")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--replan", action="store_true")
    ap.add_argument("--features", nargs="+", default=None, help="features afectadas (con --replan)")
    ap.add_argument("--delta", nargs="+", default=None, help="ids del changelog absorbidos")
    ap.add_argument("--deferred", nargs="+", default=None, help="ids del changelog postergados")
    ap.add_argument("--pipeline-version", default=None)
    ap.add_argument("--ahora", default=None)
    args = ap.parse_args(argv)
    now = args.ahora or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return run(Path(args.raiz).resolve(), args.replan, args.features, args.delta, args.deferred, args.pipeline_version, now)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
