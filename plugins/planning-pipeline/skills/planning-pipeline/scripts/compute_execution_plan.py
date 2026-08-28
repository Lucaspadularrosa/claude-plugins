#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calculo determinista del plan de ejecucion: tasks.json -> execution-plan.json.

Reemplaza a la etapa `execution-planning` en la planificacion INICIAL: el armado de
lotes es teoria de grafos pura (niveles topologicos sobre las dependencias hard entre
features), no requiere juicio de modelo. Mismo input -> mismo output, sin tokens,
sin red, sin dependencias. La REPLANIFICACION sigue siendo del subagente
`execution-planning` (conservar lotes en curso y resolver conflictos si requiere
juicio); este script se niega a correr si detecta build en progreso.

Que calcula (mismo contrato de salida que el subagente):
  - ronda de contratos (tareas type=contract) previa al primer lote
  - grafo hard entre features, niveles topologicos -> lotes BATCH-1..N
  - ciclos hard entre features: comparten lote + warning que recomienda contrato
  - task_order topologico por feature y waits_for con aristas concretas
  - metricas (max_parallel_degree, critical_path_length, truly_serial_batches, ...)
  - warnings accionables de extraccion de contratos (serializacion por arista unica)

Politica fail-fast: ante un tasks.json que no cumple el contrato (ids invalidos,
depends_on en formato viejo, ciclos entre tareas, kind desconocido) el script corta
con error explicito y NO adivina. El defecto rebota a `task-derivation`; degradar en
silencio seria peor que fallar.

Solo stdlib, Python 3.8+. No modifica tasks.json.

Uso:
  python compute_execution_plan.py [carpeta] [--pipeline-version X.Y.Z] [--ahora ISO]
  python compute_execution_plan.py --self-test

  carpeta             por defecto .dev/plan (donde vive tasks.json)
  --pipeline-version  version del plugin a estampar en metadata (default: null)
  --ahora             timestamp a estampar (default: ahora UTC; util para tests)

Exit 0 con el plan escrito; exit 1 ante contrato roto o replanificacion detectada.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ID_T = re.compile(r"^T-\d+$")
ID_FG = re.compile(r"^FG-\d+$")
TASK_TYPES = {"feature", "data", "integration", "infra", "spike", "contract"}
TASK_STATUSES = {"pending", "cancelled"}
DEP_KINDS = {"hard", "contract"}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

CONTRACT_ROUND_RATIONALE = (
    "Contratos que desbloquean el paralelismo; se mergean antes del primer lote."
)


def fail(msg):
    print("ERROR: %s" % msg)
    print("El contrato de tasks.json no se cumple: rebota a task-derivation en modo correccion.")
    sys.exit(1)


def tnum(tid):
    """Orden numerico estable para ids T-xxx / FG-xx."""
    return int(tid.rsplit("-", 1)[1])


# ------------------------------------------------------- validacion fail-fast


def validate_tasks(doc):
    """Valida lo que el calculo necesita. Corta ante lo desconocido, no adivina."""
    if not isinstance(doc, dict):
        fail("tasks.json no es un objeto JSON")
    features = doc.get("features")
    tasks = doc.get("tasks")
    if not isinstance(features, list) or not features:
        fail("tasks.json sin features[]")
    if not isinstance(tasks, list) or not tasks:
        fail("tasks.json sin tasks[]")

    fids = set()
    for f in features:
        fid = f.get("id")
        if not isinstance(fid, str) or not ID_FG.match(fid):
            fail("feature con id invalido: %r" % (fid,))
        if fid in fids:
            fail("feature duplicada: %s" % fid)
        fids.add(fid)

    tids = set()
    for t in tasks:
        tid = t.get("id")
        if not isinstance(tid, str) or not ID_T.match(tid):
            fail("tarea con id invalido: %r" % (tid,))
        if tid in tids:
            fail("tarea duplicada: %s" % tid)
        tids.add(tid)

    by_id = {t["id"]: t for t in tasks}
    for t in tasks:
        tid = t["id"]
        if t.get("feature_group") not in fids:
            fail("%s: feature_group %r no existe en features[]" % (tid, t.get("feature_group")))
        if t.get("status", "pending") not in TASK_STATUSES:
            fail("%s: status invalido %r (esperado pending|cancelled)" % (tid, t.get("status")))
        if t.get("type") not in TASK_TYPES:
            fail("%s: type invalido %r" % (tid, t.get("type")))
        for dep in t.get("depends_on") or []:
            if not isinstance(dep, dict):
                fail("%s: depends_on en formato viejo (%r); el contrato exige objetos {task_id, kind}" % (tid, dep))
            did, kind = dep.get("task_id"), dep.get("kind")
            if did not in tids:
                fail("%s: depende de %r que no existe" % (tid, did))
            if kind not in DEP_KINDS:
                fail("%s: kind invalido %r en dependencia a %s" % (tid, kind, did))
            if kind == "contract" and by_id[did].get("type") != "contract":
                fail("%s: dependencia kind=contract apunta a %s que no es type=contract" % (tid, did))
    return by_id


def guard_replan(plan_dir):
    """Si hay build en progreso, la replanificacion es del subagente, no del script."""
    progress_path = plan_dir / "progress.json"
    if not progress_path.is_file():
        return
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        fail("progress.json existe pero no parsea: estado del build desconocido")
    moved = [
        e.get("feature_id") or e.get("task_id")
        for e in (progress.get("features") or []) + (progress.get("tasks") or [])
        if e.get("status") not in (None, "pending")
    ]
    if moved:
        fail(
            "progress.json registra trabajo fuera de pending (%s): esto es una "
            "replanificacion; usa el subagente execution-planning, no este script"
            % ", ".join(sorted(set(str(m) for m in moved))[:5])
        )


# ------------------------------------------------------------------- calculo


def topo_order(task_ids, by_id):
    """Orden topologico estable (Kahn) de las tareas de una feature, por sus
    dependencias internas (hard y contract). Ciclo entre tareas = contrato roto."""
    ids = set(task_ids)
    indeg = {t: 0 for t in ids}
    consumers = {t: [] for t in ids}
    for t in ids:
        for dep in by_id[t].get("depends_on") or []:
            if dep["task_id"] in ids:
                indeg[t] += 1
                consumers[dep["task_id"]].append(t)
    ready = sorted([t for t in ids if indeg[t] == 0], key=tnum)
    order = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        changed = False
        for nxt in consumers[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
                changed = True
        if changed:
            ready.sort(key=tnum)
    if len(order) != len(ids):
        fail("ciclo de dependencias entre tareas de una misma feature: %s" % ", ".join(sorted(ids - set(order), key=tnum)))
    return order


def sccs(nodes, edges):
    """Componentes fuertemente conexas (Tarjan iterativo) del grafo de features.
    edges: dict nodo -> set de nodos de los que depende (aristas salientes)."""
    index = {}
    low = {}
    on_stack = set()
    stack = []
    result = []
    counter = [0]

    for root in sorted(nodes):
        if root in index:
            continue
        work = [(root, iter(sorted(edges.get(root, ()))))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(edges.get(nxt, ())))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if not advanced:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == node:
                            break
                    result.append(sorted(comp))
    return result


def compute(doc, pipeline_version, now, prev):
    by_id = validate_tasks(doc)
    tasks = doc["tasks"]
    warnings = []

    active = [t for t in tasks if t.get("status", "pending") != "cancelled"]
    contract_ids = []
    for t in active:
        if t.get("type") == "contract":
            hard_deps = [d for d in t.get("depends_on") or [] if d["kind"] == "hard"]
            if hard_deps:
                warnings.append(
                    "%s es type=contract pero depende hard de %s: va al lote de su "
                    "feature en vez de a la ronda de contratos; revisar si es un contrato real."
                    % (t["id"], ", ".join(d["task_id"] for d in hard_deps))
                )
            else:
                contract_ids.append(t["id"])
    contract_ids.sort(key=tnum)
    contract_set = set(contract_ids)

    # tareas que caen en lotes: activas fuera de la ronda de contratos
    batch_tasks = [t for t in active if t["id"] not in contract_set]
    feat_tasks = {}
    for t in batch_tasks:
        feat_tasks.setdefault(t["feature_group"], []).append(t["id"])

    # grafo hard entre features (contract no genera aristas: ya mergeado en la ronda)
    hard_edges = {}   # (consumidora, productora) -> [(from_task, to_task)]
    feat_deps = {f: set() for f in feat_tasks}
    for t in batch_tasks:
        for dep in t.get("depends_on") or []:
            if dep["kind"] != "hard":
                continue
            prod = by_id[dep["task_id"]]
            if prod.get("status", "pending") == "cancelled":
                continue
            pf, cf = prod["feature_group"], t["feature_group"]
            if pf == cf or pf not in feat_tasks:
                continue
            feat_deps[cf].add(pf)
            hard_edges.setdefault((cf, pf), []).append((t["id"], dep["task_id"]))

    # SCCs: un ciclo hard entre features comparte lote (no se puede ordenar)
    components = sccs(set(feat_tasks), feat_deps)
    comp_of = {}
    for i, comp in enumerate(components):
        for f in comp:
            comp_of[f] = i
        if len(comp) > 1:
            warnings.append(
                "Ciclo de dependencias hard entre features %s: comparten lote. "
                "Recomendado: volver a task-derivation y romper el ciclo extrayendo "
                "una tarea type='contract'." % " y ".join(comp)
            )

    comp_deps = {i: set() for i in range(len(components))}
    for cf, pf in feat_deps.items():
        for p in pf:
            if comp_of[p] != comp_of[cf]:
                comp_deps[comp_of[cf]].add(comp_of[p])

    level = {}

    def comp_level(i):
        if i in level:
            return level[i]
        level[i] = 1 + max((comp_level(j) for j in comp_deps[i]), default=0)
        return level[i]

    for i in range(len(components)):
        comp_level(i)
    feat_level = {f: level[comp_of[f]] for f in feat_tasks}

    # prioridad de la feature = la mas alta de sus tareas (solo ordena dentro del lote)
    def feat_rank(fid):
        ranks = [PRIORITY_RANK.get(by_id[t].get("priority"), 1) for t in feat_tasks[fid]]
        return (min(ranks) if ranks else 1, tnum(fid))

    contract_round = None
    if contract_ids:
        contract_round = {
            "id": "BATCH-0",
            "task_ids": contract_ids,
            "rationale": CONTRACT_ROUND_RATIONALE,
        }

    max_level = max(feat_level.values(), default=0)
    batches = []
    for lv in range(1, max_level + 1):
        feats = sorted([f for f, l in feat_level.items() if l == lv], key=feat_rank)
        entries = []
        for fid in feats:
            order = topo_order(feat_tasks[fid], by_id)
            waits = {}
            for (cf, pf), pairs in sorted(hard_edges.items()):
                if cf != fid or feat_level.get(pf) == lv:
                    continue
                w = waits.setdefault(pf, {"feature_id": pf, "batch_id": "BATCH-%d" % feat_level[pf], "edges": []})
                for from_t, to_t in sorted(pairs, key=lambda p: (tnum(p[0]), tnum(p[1]))):
                    w["edges"].append({"from_task": from_t, "to_task": to_t, "kind": "hard"})
            for t in sorted(feat_tasks[fid], key=tnum):
                for dep in by_id[t].get("depends_on") or []:
                    if dep["kind"] == "contract" and dep["task_id"] in contract_set:
                        pf = by_id[dep["task_id"]]["feature_group"]
                        if pf == fid:
                            continue
                        w = waits.setdefault("c:" + pf, {"feature_id": pf, "batch_id": "BATCH-0", "edges": []})
                        w["edges"].append({"from_task": t, "to_task": dep["task_id"], "kind": "contract"})
            entries.append({
                "feature_id": fid,
                "adjustment": False,
                "groupable": False,
                "task_ids": sorted(feat_tasks[fid], key=tnum),
                "task_order": order,
                "waits_for": [waits[k] for k in sorted(waits, key=lambda k: k.split(":")[-1])],
            })
        unlocks = sorted({w["batch_id"] for e in entries for w in e["waits_for"]})
        if lv == 1 and contract_round and "BATCH-0" not in unlocks:
            unlocks = ["BATCH-0"] + unlocks
        batches.append({
            "id": "BATCH-%d" % lv,
            "features": entries,
            "unlocks_after": unlocks,
            "rationale": batch_rationale(entries, lv, hard_edges, feat_level, components, comp_of),
        })

    # warnings accionables: serializacion por productora unica en el nivel binding
    for fid in sorted(feat_tasks, key=tnum):
        lv = feat_level[fid]
        if lv <= 1:
            continue
        binding = sorted(p for p in feat_deps[fid] if feat_level[p] == lv - 1 and comp_of[p] != comp_of[fid])
        if len(binding) != 1:
            continue
        prod = binding[0]
        pairs = hard_edges.get((fid, prod), [])
        if len(pairs) == 1:
            from_t, to_t = pairs[0]
            warnings.append(
                "%s quedo en BATCH-%d detras de %s por la arista hard %s -> %s. "
                "Para paralelizar: extraer la firma de %s como tarea type='contract' "
                "(y cambiar el kind de la dependencia a 'contract'), lo que subiria "
                "%s a BATCH-%d." % (fid, lv, prod, from_t, to_t, to_t, fid, lv - 1)
            )
        elif pairs:
            listado = "; ".join("%s -> %s" % p for p in sorted(pairs))
            warnings.append(
                "%s quedo en BATCH-%d detras de %s por %d aristas hard (%s). "
                "Para paralelizar: extraer las firmas de las tareas productoras como "
                "tareas type='contract'." % (fid, lv, prod, len(pairs), listado)
            )

    feature_entries = sum(len(b["features"]) for b in batches)
    summary = {
        "max_parallel_degree": max((len(b["features"]) for b in batches), default=0),
        "critical_path_length": len(batches) + (1 if contract_round else 0),
        "batch_count": len(batches),
        "feature_count": feature_entries,
        "contract_task_count": len(contract_ids),
        "truly_serial_batches": sum(1 for b in batches if len(b["features"]) == 1),
    }

    prev_meta = (prev or {}).get("metadata", {}) or {}
    return {
        "version": int((prev or {}).get("version", 0)) + 1,
        "project": doc.get("project", {}),
        "metadata": {
            "created_at": prev_meta.get("created_at") or now,
            "updated_at": now,
            "tasks_version_ref": str(doc.get("version", "?")),
            "replanned": False,
            "completed_feature_ids": [],
            "pipeline_version": pipeline_version,
            "generated_by": "compute_execution_plan.py",
        },
        "summary": summary,
        "contract_round": contract_round,
        "batches": batches,
        "warnings": warnings,
    }


def batch_rationale(entries, lv, hard_edges, feat_level, components, comp_of):
    fids = [e["feature_id"] for e in entries]
    cycle = [c for c in components if len(c) > 1 and any(f in fids for f in c)]
    if cycle:
        return (
            "Ciclo hard entre %s: comparten lote porque no se pueden ordenar; ver warnings."
            % " y ".join(cycle[0])
        )
    if len(entries) == 1:
        fid = entries[0]["feature_id"]
        deps = []
        for (cf, pf), pairs in sorted(hard_edges.items()):
            if cf == fid:
                deps += ["%s -> %s (%s)" % (f, t, pf) for f, t in pairs]
        if deps:
            return "Lote serial: %s quedo aislada por sus dependencias hard: %s." % (fid, "; ".join(deps))
        return "Lote serial: %s es la unica feature de este nivel del grafo." % fid
    if lv == 1:
        return "Features sin dependencias hard entre si ni hacia otras features: corren en paralelo, cada una en su rama."
    return "Features que solo esperan trabajo ya mergeado de lotes anteriores (ver waits_for de cada una); entre si no tienen dependencias hard."


# ------------------------------------------------------------------ self-test


def self_test():
    import shutil
    import tempfile

    def base_tasks():
        return {
            "version": 3,
            "project": {"name": "demo", "domain_summary": "d", "source_language": "es"},
            "features": [
                {"id": "FG-01", "name": "A", "requirement_ids": ["RF-001"], "task_ids": ["T-001", "T-002"]},
                {"id": "FG-02", "name": "B", "requirement_ids": ["RF-002"], "task_ids": ["T-003"]},
                {"id": "FG-03", "name": "C", "requirement_ids": ["RF-003"], "task_ids": ["T-004", "T-005"]},
            ],
            "tasks": [
                {"id": "T-001", "feature_group": "FG-01", "type": "contract", "priority": "high",
                 "status": "pending", "depends_on": []},
                {"id": "T-002", "feature_group": "FG-01", "type": "feature", "priority": "high",
                 "status": "pending", "depends_on": []},
                {"id": "T-003", "feature_group": "FG-02", "type": "feature", "priority": "medium",
                 "status": "pending", "depends_on": [{"task_id": "T-001", "kind": "contract"}]},
                {"id": "T-004", "feature_group": "FG-03", "type": "feature", "priority": "low",
                 "status": "pending", "depends_on": [{"task_id": "T-002", "kind": "hard"}]},
                {"id": "T-005", "feature_group": "FG-03", "type": "feature", "priority": "low",
                 "status": "pending", "depends_on": [{"task_id": "T-004", "kind": "hard"}]},
            ],
        }

    failures = []

    def check(cond, label):
        if cond:
            print("self-test ok: %s" % label)
        else:
            failures.append(label)
            print("SELF-TEST FALLO: %s" % label)

    now = "2000-01-01T00:00:00+00:00"
    plan = compute(base_tasks(), "9.9.9", now, None)
    plan2 = compute(base_tasks(), "9.9.9", now, None)
    check(plan == plan2, "determinismo (mismo input -> mismo output)")
    check(plan["contract_round"]["task_ids"] == ["T-001"], "ronda de contratos con T-001")
    check(plan["summary"]["batch_count"] == 2, "dos lotes (FG-01+FG-02 / FG-03)")
    check(plan["summary"]["max_parallel_degree"] == 2, "paralelismo maximo 2")
    check(plan["summary"]["critical_path_length"] == 3, "critical path 3 (contratos + 2 lotes)")
    check(plan["summary"]["truly_serial_batches"] == 1, "un lote serial (FG-03)")
    b1 = plan["batches"][0]
    check([e["feature_id"] for e in b1["features"]] == ["FG-01", "FG-02"], "orden por prioridad en BATCH-1")
    fg02 = b1["features"][1]
    check(fg02["waits_for"] and fg02["waits_for"][0]["batch_id"] == "BATCH-0"
          and fg02["waits_for"][0]["edges"][0]["kind"] == "contract", "waits_for contract de FG-02 a BATCH-0")
    fg03 = plan["batches"][1]["features"][0]
    check(fg03["task_order"] == ["T-004", "T-005"], "task_order topologico de FG-03")
    check(fg03["waits_for"][0]["edges"][0] == {"from_task": "T-004", "to_task": "T-002", "kind": "hard"},
          "waits_for hard de FG-03 a FG-01")
    check(any("extraer la firma de T-002" in w for w in plan["warnings"]),
          "warning de extraccion de contrato por arista unica")
    placed = list(plan["contract_round"]["task_ids"])
    for b in plan["batches"]:
        for e in b["features"]:
            placed += e["task_ids"]
    check(sorted(placed) == ["T-001", "T-002", "T-003", "T-004", "T-005"],
          "toda tarea activa en exactamente un lote")

    # ciclo hard entre features -> mismo lote + warning
    cyc = base_tasks()
    cyc["tasks"][1]["depends_on"] = [{"task_id": "T-003", "kind": "hard"}]
    cyc["tasks"][2]["depends_on"] = [{"task_id": "T-002", "kind": "hard"}]
    plan_cyc = compute(cyc, None, now, None)
    b1c = plan_cyc["batches"][0]
    check(sorted(e["feature_id"] for e in b1c["features"]) == ["FG-01", "FG-02"],
          "ciclo hard: FG-01 y FG-02 comparten lote")
    check(any("Ciclo de dependencias hard" in w for w in plan_cyc["warnings"]), "warning de ciclo hard")

    # fail-fast: formato viejo de depends_on corta con exit 1
    tmp = Path(tempfile.mkdtemp(prefix="compute-plan-"))
    try:
        broken = base_tasks()
        broken["tasks"][2]["depends_on"] = ["T-001"]
        (tmp / "tasks.json").write_text(json.dumps(broken), encoding="utf-8")
        import subprocess
        r = subprocess.run([sys.executable, __file__, str(tmp)], capture_output=True, text=True)
        check(r.returncode == 1 and "formato viejo" in r.stdout, "fail-fast ante depends_on en formato viejo")

        # corrida real sobre carpeta + incremento de version en la reescritura
        (tmp / "tasks.json").write_text(json.dumps(base_tasks()), encoding="utf-8")
        for expected_version in (1, 2):
            r = subprocess.run(
                [sys.executable, __file__, str(tmp), "--pipeline-version", "9.9.9", "--ahora", now],
                capture_output=True, text=True)
            written = json.loads((tmp / "execution-plan.json").read_text(encoding="utf-8"))
            check(r.returncode == 0 and written["version"] == expected_version,
                  "escritura real: version %d" % expected_version)

        # guard de replanificacion: progress con trabajo empezado corta
        (tmp / "progress.json").write_text(json.dumps(
            {"features": [{"feature_id": "FG-01", "status": "in_progress"}], "tasks": []}), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, str(tmp)], capture_output=True, text=True)
        check(r.returncode == 1 and "replanificacion" in r.stdout, "guard de replanificacion")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("%s: %d fallo(s)" % ("SELF-TEST", len(failures)))
    return 1 if failures else 0


# ----------------------------------------------------------------------- main


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default=".dev/plan")
    ap.add_argument("--pipeline-version", default=None)
    ap.add_argument("--ahora", default=None, help="timestamp ISO a estampar (default: ahora UTC)")
    args = ap.parse_args(argv)

    plan_dir = Path(args.carpeta)
    tasks_path = plan_dir / "tasks.json"
    if not tasks_path.is_file():
        fail("no existe %s" % tasks_path)
    try:
        doc = json.loads(tasks_path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        fail("%s ilegible: %s" % (tasks_path, exc))

    guard_replan(plan_dir)

    prev = None
    out_path = plan_dir / "execution-plan.json"
    if out_path.is_file():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            print("aviso: execution-plan.json previo ilegible; se regenera desde version 1")

    now = args.ahora or datetime.now(timezone.utc).isoformat(timespec="seconds")
    plan = compute(doc, args.pipeline_version, now, prev)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = plan["summary"]
    print("escrito: %s (version %s)" % (out_path, plan["version"]))
    print(
        "lotes: %d | paralelismo maximo: %d | critical path: %d | seriales: %d | contratos: %d"
        % (s["batch_count"], s["max_parallel_degree"], s["critical_path_length"],
           s["truly_serial_batches"], s["contract_task_count"])
    )
    for w in plan["warnings"]:
        print("aviso: %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
