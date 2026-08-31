#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transiciones de `.dev/plan/progress.json` por script, con validacion de schema.

El orquestador del build no edita `progress.json` a mano (Read + Edit sobre un JSON
con semantica delicada, decenas de veces por lote): invoca este script en cada
transicion. Valida ids, estados y forma; anota `updated_at`; no toca `plan_ref`
(es de /planificar y /replanificar).

Semantica (de la skill de planning-pipeline):
  feature.status: pending | in_progress | done          (done = mergeada)
  task.status:    pending | in_progress | done | blocked | cancelled

Uso:
  python progress_update.py <raiz> --feature FG-05 [--status in_progress] [--branch feature/x]
                            [--task T-001=done --task T-002=blocked] [--note "PR #14"]
                            [--task-note T-002="motivo"] [--replace-note] [--pipeline-version X]
  python progress_update.py <raiz> --init [--pipeline-version X]
      inicializa desde execution-plan.json + tasks.json con todo en pending (si no existe)
  python progress_update.py <raiz> --estado [FG-05]
      imprime el estado (una linea por feature, o el detalle de una)
  python progress_update.py --self-test

`--note` agrega al final de `notes` (separado por " | "); con `--replace-note` lo
reemplaza. Exit 0 ok; 1 transicion invalida o id inexistente; 2 error de uso/IO.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

FEATURE_STATES = ("pending", "in_progress", "done")
TASK_STATES = ("pending", "in_progress", "done", "blocked", "cancelled")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError:
        return None
    except ValueError as exc:
        raise SystemExit("error: %s no parsea: %s" % (path, exc))


def save(path, data):
    data["updated_at"] = now()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init(plan_dir, pipeline_version):
    plan = load(plan_dir / "execution-plan.json")
    tasks = load(plan_dir / "tasks.json")
    if plan is None or tasks is None:
        return None, "faltan execution-plan.json o tasks.json en %s" % plan_dir
    features = []
    seen = set()
    for batch in plan.get("batches") or []:
        for f in batch.get("features") or []:
            fid = f.get("feature_id")
            if fid and fid not in seen:
                seen.add(fid)
                features.append({"feature_id": fid, "status": "pending", "branch": "", "notes": ""})
    for f in tasks.get("features") or []:
        fid = f.get("id")
        if fid and fid not in seen:
            seen.add(fid)
            features.append({"feature_id": fid, "status": "pending", "branch": "", "notes": ""})
    task_entries = [
        {"task_id": t["id"], "feature_id": t.get("feature_group") or t.get("feature_id") or "", "status": "pending", "notes": ""}
        for t in tasks.get("tasks") or [] if t.get("id")
    ]
    return {
        "version": 1,
        "pipeline_version": pipeline_version,
        "updated_at": now(),
        "plan_ref": {"tasks_version": str(tasks.get("version", "")),
                     "applied_changelog_ids": list((tasks.get("metadata") or {}).get("applied_changelog_ids") or [])},
        "features": features,
        "tasks": task_entries,
    }, None


def append_note(entry, note, replace):
    if replace or not entry.get("notes"):
        entry["notes"] = note
    else:
        entry["notes"] = entry["notes"] + " | " + note


def apply(data, feature, status, branch, task_changes, note, task_notes, replace):
    errors = []
    changes = []
    feats = {f.get("feature_id"): f for f in data.get("features") or []}
    tasks = {t.get("task_id"): t for t in data.get("tasks") or []}
    fe = feats.get(feature)
    if fe is None:
        return ["feature %s no existe en progress.json" % feature], []
    if status:
        if status not in FEATURE_STATES:
            errors.append("estado de feature invalido: %s" % status)
        elif fe.get("status") == "done" and status != "done":
            errors.append("feature %s ya esta done (mergeada): no se retrocede; las tareas de ajuste se rastrean a nivel tarea" % feature)
        else:
            if status == "in_progress" and not (branch or fe.get("branch")):
                errors.append("in_progress requiere --branch (la rama de la feature)")
            else:
                changes.append("%s: %s -> %s" % (feature, fe.get("status"), status))
                fe["status"] = status
    if branch:
        fe["branch"] = branch
        changes.append("%s: branch=%s" % (feature, branch))
    if note:
        append_note(fe, note, replace)
        changes.append("%s: nota agregada" % feature)
    for tid, tstatus in task_changes:
        t = tasks.get(tid)
        if t is None:
            errors.append("tarea %s no existe" % tid)
            continue
        if t.get("feature_id") and t.get("feature_id") != feature:
            errors.append("tarea %s pertenece a %s, no a %s" % (tid, t.get("feature_id"), feature))
            continue
        if tstatus not in TASK_STATES:
            errors.append("estado de tarea invalido: %s" % tstatus)
            continue
        changes.append("%s: %s -> %s" % (tid, t.get("status"), tstatus))
        t["status"] = tstatus
    for tid, tnote in task_notes:
        t = tasks.get(tid)
        if t is None:
            errors.append("tarea %s no existe" % tid)
            continue
        append_note(t, tnote, replace)
        changes.append("%s: nota agregada" % tid)
    return errors, changes


def show(data, feature):
    tasks = data.get("tasks") or []
    for f in data.get("features") or []:
        if feature and f.get("feature_id") != feature:
            continue
        ft = [t for t in tasks if t.get("feature_id") == f.get("feature_id")]
        counts = {}
        for t in ft:
            counts[t.get("status")] = counts.get(t.get("status"), 0) + 1
        print("%s %s branch=%s tareas=%s%s" % (
            f.get("feature_id"), f.get("status"), f.get("branch") or "-",
            ",".join("%s:%d" % kv for kv in sorted(counts.items())) or "0",
            (" notas: " + f.get("notes")) if f.get("notes") else ""))
        if feature:
            for t in ft:
                print("  %s %s%s" % (t.get("task_id"), t.get("status"), (" (" + t["notes"] + ")") if t.get("notes") else ""))


# ------------------------------------------------------------------ self-test

def self_test():
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="progress-"))
    failures = 0
    try:
        plan = tmp / ".dev" / "plan"
        plan.mkdir(parents=True)
        (plan / "tasks.json").write_text(json.dumps({
            "version": 3, "metadata": {"applied_changelog_ids": ["INC-001"]},
            "features": [{"id": "FG-01"}],
            "tasks": [{"id": "T-001", "feature_group": "FG-01"}, {"id": "T-002", "feature_group": "FG-01"}],
        }), encoding="utf-8")
        (plan / "execution-plan.json").write_text(json.dumps({
            "batches": [{"id": "BATCH-1", "features": [{"feature_id": "FG-01"}]}],
        }), encoding="utf-8")
        data, err = init(plan, "9.9.9")
        if err or data["plan_ref"]["tasks_version"] != "3" or len(data["tasks"]) != 2:
            print("SELF-TEST FALLO (init): %s" % (err or data))
            return 1
        errors, changes = apply(data, "FG-01", "in_progress", "feature/x", [("T-001", "done")], "arranque", [], False)
        if errors or data["features"][0]["status"] != "in_progress" or data["tasks"][0]["status"] != "done":
            print("SELF-TEST FALLO (transicion valida): %s" % errors)
            failures += 1
        else:
            print("self-test ok (transicion valida): %d cambio(s)" % len(changes))
        errors, _ = apply(data, "FG-01", "volando", None, [("T-999", "done")], None, [], False)
        if len(errors) != 2:
            print("SELF-TEST FALLO (transicion invalida): %s" % errors)
            failures += 1
        else:
            print("self-test ok (transicion invalida rechazada)")
        errors, _ = apply(data, "FG-02", None, None, [], None, [], False)
        if not errors:
            print("SELF-TEST FALLO (feature inexistente aceptada)")
            failures += 1
        else:
            print("self-test ok (feature inexistente rechazada)")
        apply(data, "FG-01", "done", None, [], None, [], False)
        errors, _ = apply(data, "FG-01", "pending", None, [], None, [], False)
        if not errors:
            print("SELF-TEST FALLO (retroceso desde done aceptado)")
            failures += 1
        else:
            print("self-test ok (done no retrocede)")
        save(plan / "progress.json", data)
        back = json.loads((plan / "progress.json").read_text(encoding="utf-8"))
        if back["features"][0]["notes"] != "arranque":
            print("SELF-TEST FALLO (persistencia)")
            failures += 1
        else:
            print("self-test ok (persistencia)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


# ------------------------------------------------------------------------ main

def parse(argv):
    opts = {"root": None, "feature": None, "status": None, "branch": None, "tasks": [], "note": None,
            "task_notes": [], "replace": False, "init": False, "estado": None, "pipeline_version": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a == "--feature":
            opts["feature"] = nxt; i += 1
        elif a == "--status":
            opts["status"] = nxt; i += 1
        elif a == "--branch":
            opts["branch"] = nxt; i += 1
        elif a == "--task":
            if not nxt or "=" not in nxt:
                raise SystemExit("error: --task espera T-xxx=estado")
            tid, st = nxt.split("=", 1)
            opts["tasks"].append((tid.strip(), st.strip())); i += 1
        elif a == "--task-note":
            if not nxt or "=" not in nxt:
                raise SystemExit("error: --task-note espera T-xxx=texto")
            tid, tn = nxt.split("=", 1)
            opts["task_notes"].append((tid.strip(), tn.strip())); i += 1
        elif a == "--note":
            opts["note"] = nxt; i += 1
        elif a == "--replace-note":
            opts["replace"] = True
        elif a == "--init":
            opts["init"] = True
        elif a == "--estado":
            opts["estado"] = nxt if nxt and not nxt.startswith("--") else ""
            if opts["estado"]:
                i += 1
        elif a == "--pipeline-version":
            opts["pipeline_version"] = nxt; i += 1
        elif a.startswith("--"):
            raise SystemExit("error: opcion desconocida %s" % a)
        else:
            opts["root"] = a
        i += 1
    return opts


def main(argv):
    if "--self-test" in argv:
        return self_test()
    try:
        o = parse(argv)
    except SystemExit as exc:
        print(exc)
        return 2
    if not o["root"]:
        print(__doc__)
        return 2
    plan_dir = Path(o["root"]) / ".dev" / "plan"
    path = plan_dir / "progress.json"
    if o["init"]:
        if path.is_file():
            print("progress.json ya existe: no se reinicializa")
            return 0
        data, err = init(plan_dir, o["pipeline_version"])
        if err:
            print("error: %s" % err)
            return 2
        save(path, data)
        print("inicializado %s: %d features, %d tareas en pending" % (path, len(data["features"]), len(data["tasks"])))
        return 0
    data = load(path)
    if data is None:
        print("error: no existe %s (usa --init)" % path)
        return 2
    if o["estado"] is not None:
        show(data, o["estado"] or None)
        return 0
    if not o["feature"]:
        print("error: falta --feature")
        return 2
    errors, changes = apply(data, o["feature"], o["status"], o["branch"], o["tasks"], o["note"],
                            o["task_notes"], o["replace"])
    for e in errors:
        print("rechazado: %s" % e)
    if errors:
        return 1
    if o["pipeline_version"]:
        data["pipeline_version"] = o["pipeline_version"]
    save(path, data)
    for c in changes:
        print(c)
    if not changes:
        print("sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
