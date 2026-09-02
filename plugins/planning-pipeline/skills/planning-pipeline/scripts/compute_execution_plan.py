#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calculo determinista del plan de ejecucion: tasks.json -> execution-plan.json.

Reemplaza a la etapa `execution-planning` en la planificacion INICIAL: el armado de
lotes es teoria de grafos pura (niveles topologicos sobre las dependencias hard entre
features), no requiere juicio de modelo. Mismo input -> mismo output, sin tokens,
sin red, sin dependencias. La REPLANIFICACION tambien es del script (--replan):
las features done salen del grafo, las in_progress conservan su lote, lo nuevo entra
por niveles con ids que continuan la numeracion, los ajustes sobre features
construidas se emiten como entradas `adjustment` (y `groupable` si son triviales) y
los contratos nuevos van a un lote propio previo a sus consumidores. Lo unico que no
resuelve son los CONFLICTOS (tarea nueva de una feature en curso que depende hard de
trabajo aun no mergeado): los escribe en warnings con prefijo CONFLICTO y exit 2 para
que el orquestador los presente al usuario (o delegue al subagente
`execution-planning`). Sin --replan se niega a correr si detecta build en progreso.

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
  python compute_execution_plan.py [carpeta] --replan [--pipeline-version X.Y.Z]
  python compute_execution_plan.py --self-test

  carpeta             por defecto .dev/plan (donde vive tasks.json)
  --pipeline-version  version del plugin a estampar en metadata (default: null)
  --ahora             timestamp a estampar (default: ahora UTC; util para tests)

Exit 0 con el plan escrito; exit 1 ante contrato roto o replanificacion detectada
sin --replan; exit 2 con el plan escrito pero con CONFLICTOs a resolver.
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
# Suites viejas avanzaban el status del build en tasks.json (hoy vive en
# progress.json): se toleran como progreso legado, no como contrato roto.
LEGACY_BUILD_STATUSES = {"done", "in_progress"}
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
        if t.get("status", "pending") not in TASK_STATUSES | LEGACY_BUILD_STATUSES:
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


def guard_replan(plan_dir, doc):
    """Si hay build en progreso, la replanificacion es del subagente, no del script."""
    legacy = sorted(
        t.get("id") for t in (doc.get("tasks") or [])
        if isinstance(t, dict) and t.get("status") in LEGACY_BUILD_STATUSES
    )
    if legacy:
        fail(
            "tasks.json registra trabajo de build (%s%s): esto es una replanificacion; "
            "corre este script con --replan"
            % (", ".join(str(t) for t in legacy[:5]), "..." if len(legacy) > 5 else "")
        )
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
            "replanificacion; corre este script con --replan"
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


def compute_replan(doc, progress, prev, pipeline_version, now):
    """Lotes solo del trabajo restante, conservando lo construido y lo en curso."""
    by_id = validate_tasks(doc)
    if not prev:
        fail("--replan necesita el execution-plan.json previo")
    warnings = []
    fstatus = {e.get("feature_id"): e.get("status", "pending") for e in progress.get("features") or []}
    tstatus = {e.get("task_id"): e.get("status", "pending") for e in progress.get("tasks") or []}
    # Build legado: suites viejas escribian el avance en tasks.json. Se lee como
    # progreso (progress.json tiene prioridad) para que el script corra sobre
    # proyectos que ya construyeron con ese contrato.
    legacy = {t["id"]: t["status"] for t in doc["tasks"] if t.get("status") in LEGACY_BUILD_STATUSES}
    if legacy:
        for ltid, lst in legacy.items():
            tstatus.setdefault(ltid, lst)
        for fid in {t["feature_group"] for t in doc["tasks"]}:
            sts = {tstatus.get(t["id"], "pending") for t in doc["tasks"]
                   if t["feature_group"] == fid and t.get("status", "pending") != "cancelled"}
            if sts == {"done"}:
                fstatus.setdefault(fid, "done")
            elif sts & LEGACY_BUILD_STATUSES:
                fstatus.setdefault(fid, "in_progress")
        warnings.append(
            "tasks.json trae status de build legado en %d tarea(s): se leyo como "
            "progreso (progress.json tiene prioridad si existe)." % len(legacy)
        )
    prev_batch_of = {}
    max_batch = 0
    for b in prev.get("batches") or []:
        num = int(str(b.get("id", "BATCH-0")).split("-")[-1])
        max_batch = max(max_batch, num)
        for e in b.get("features") or []:
            prev_batch_of[e.get("feature_id")] = (b.get("id"), num)
    prev_contracts = set(((prev.get("contract_round") or {}).get("task_ids")) or [])

    done = {f for f, st in fstatus.items() if st == "done"}
    inprog = {}
    for f, st in fstatus.items():
        if st == "in_progress":
            if f in prev_batch_of:
                inprog[f] = prev_batch_of[f]
            else:
                warnings.append("%s esta in_progress pero no figura en el plan previo: se replanifica como pending." % f)

    active = [t for t in doc["tasks"] if t.get("status", "pending") != "cancelled"]
    new_contracts = []
    feat_tasks = {}
    adjustment = set()
    for t in active:
        tid, fid = t["id"], t["feature_group"]
        if tid in prev_contracts:
            continue
        if t.get("type") == "contract" and tstatus.get(tid, "pending") == "pending" \
                and not [d for d in t.get("depends_on") or [] if d["kind"] == "hard"]:
            new_contracts.append(tid)
            continue
        if fid in done:
            if tstatus.get(tid, "pending") != "pending":
                continue
            adjustment.add(fid)
        feat_tasks.setdefault(fid, []).append(tid)
    new_contracts.sort(key=tnum)
    contract_batch = None
    next_num = max_batch + 1
    if new_contracts:
        contract_batch = {"id": "BATCH-%d" % next_num, "features": [], "unlocks_after": [],
                          "task_ids": new_contracts,
                          "rationale": "Ronda de contratos de la replanificacion: se mergea antes de sus consumidores."}
        next_num += 1
    base_level = next_num

    # grafo hard entre features restantes (done satisfechas; in_progress fija su nivel)
    hard_edges = {}
    feat_deps = {f: set() for f in feat_tasks}
    for fid, tids in feat_tasks.items():
        for tid in tids:
            for dep in by_id[tid].get("depends_on") or []:
                if dep["kind"] != "hard":
                    continue
                prod = by_id[dep["task_id"]]
                pf = prod["feature_group"]
                if prod.get("status", "pending") == "cancelled" or pf == fid:
                    continue
                if pf in done and tstatus.get(dep["task_id"], "done" if pf in done else "pending") != "pending":
                    continue
                if pf not in feat_tasks:
                    continue
                feat_deps[fid].add(pf)
                hard_edges.setdefault((fid, pf), []).append((tid, dep["task_id"]))

    components = sccs(set(feat_tasks), feat_deps)
    comp_of = {}
    for i, comp in enumerate(components):
        for f in comp:
            comp_of[f] = i
        if len(comp) > 1:
            warnings.append("Ciclo de dependencias hard entre features %s: comparten lote. Recomendado: romperlo con una tarea type='contract'." % " y ".join(comp))
    comp_deps = {i: set() for i in range(len(components))}
    for cf, pf in feat_deps.items():
        for p in pf:
            if comp_of[p] != comp_of[cf]:
                comp_deps[comp_of[cf]].add(comp_of[p])
    fixed = {}
    for i, comp in enumerate(components):
        nums = [inprog[f][1] for f in comp if f in inprog]
        if nums:
            fixed[i] = min(nums)
            if len(set(nums)) > 1 or any(f not in inprog for f in comp):
                warnings.append("CONFLICTO: las features %s estan en un ciclo o componente con lotes en curso distintos; revisar a mano." % " y ".join(comp))
    level = {}

    def comp_level(i):
        if i in level:
            return level[i]
        if i in fixed:
            level[i] = fixed[i]
            return level[i]
        level[i] = max(base_level, 1 + max((comp_level(j) for j in comp_deps[i]), default=0))
        return level[i]

    for i in range(len(components)):
        comp_level(i)
    feat_level = {f: level[comp_of[f]] for f in feat_tasks}
    # conflictos: in_progress que depende hard de algo que cae en un lote posterior o igual
    for fid, (bid, num) in inprog.items():
        for p in feat_deps.get(fid, ()):
            if feat_level[p] >= num:
                pairs = "; ".join("%s -> %s" % e for e in hard_edges.get((fid, p), []))
                warnings.append("CONFLICTO: %s (en curso, %s) depende hard de %s que cae en BATCH-%d (%s). Decidir: mover la tarea, esperar o extraer contrato."
                                % (fid, bid, p, feat_level[p], pairs))

    def feat_rank(fid):
        ranks = [PRIORITY_RANK.get(by_id[t].get("priority"), 1) for t in feat_tasks[fid]]
        return (min(ranks) if ranks else 1, tnum(fid))

    batches = []
    if contract_batch:
        batches.append(contract_batch)
    for lv in sorted(set(feat_level.values())):
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
                    if dep["kind"] != "contract":
                        continue
                    pf = by_id[dep["task_id"]]["feature_group"]
                    if pf == fid:
                        continue
                    bid = contract_batch["id"] if (contract_batch and dep["task_id"] in new_contracts) else "BATCH-0"
                    w = waits.setdefault("c:" + pf, {"feature_id": pf, "batch_id": bid, "edges": []})
                    w["edges"].append({"from_task": t, "to_task": dep["task_id"], "kind": "contract"})
            is_adj = fid in adjustment
            groupable = is_adj and len(feat_tasks[fid]) <= 1 and all(by_id[t].get("complexity") == "low" for t in feat_tasks[fid])
            entries.append({
                "feature_id": fid,
                "adjustment": is_adj,
                "groupable": groupable,
                "task_ids": sorted(feat_tasks[fid], key=tnum),
                "task_order": order,
                "waits_for": [waits[k] for k in sorted(waits, key=lambda k: k.split(":")[-1])],
            })
        unlocks = sorted({w["batch_id"] for e in entries for w in e["waits_for"]})
        kept_ids = {inprog[f][0] for f in feats if f in inprog}
        bid = sorted(kept_ids)[0] if kept_ids else "BATCH-%d" % lv
        rationale = batch_rationale(entries, lv, hard_edges, feat_level, components, comp_of)
        if kept_ids:
            rationale = "Lote en curso conservado (%s). " % ", ".join(sorted(f for f in feats if f in inprog)) + rationale
        adj = [e["feature_id"] for e in entries if e["adjustment"]]
        if adj:
            rationale += " Ajustes sobre features ya construidas: %s%s." % (
                ", ".join(adj), " (groupable: compartir rama/agente)" if any(e["groupable"] for e in entries) else "")
        batches.append({"id": bid, "features": entries, "unlocks_after": unlocks, "rationale": rationale})

    summary = {
        "max_parallel_degree": max((len([e for e in b["features"] if not e.get("groupable")]) for b in batches if b.get("features")), default=0),
        "critical_path_length": len(batches) + (1 if prev.get("contract_round") else 0),
        "batch_count": len(batches),
        "feature_count": sum(len(b["features"]) for b in batches),
        "contract_task_count": len(prev_contracts) + len(new_contracts),
        "truly_serial_batches": sum(1 for b in batches if len(b["features"]) == 1),
    }
    prev_meta = prev.get("metadata", {}) or {}
    return {
        "version": int(prev.get("version", 0)) + 1,
        "project": doc.get("project", {}),
        "metadata": {
            "created_at": prev_meta.get("created_at") or now,
            "updated_at": now,
            "tasks_version_ref": str(doc.get("version", "?")),
            "replanned": True,
            "completed_feature_ids": sorted(done, key=tnum),
            "pipeline_version": pipeline_version,
            "generated_by": "compute_execution_plan.py --replan",
        },
        "summary": summary,
        "contract_round": prev.get("contract_round"),
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

        # build legado: status done en tasks.json (sin --replan) guia a --replan en vez de cortar por contrato
        (tmp / "progress.json").unlink()
        legacy_doc = base_tasks()
        legacy_doc["tasks"][1]["status"] = "done"
        (tmp / "tasks.json").write_text(json.dumps(legacy_doc), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, str(tmp)], capture_output=True, text=True)
        check(r.returncode == 1 and "--replan" in r.stdout and "status invalido" not in r.stdout,
              "guard: status de build legado en tasks.json guia a --replan")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # replanificacion por script: FG-01 done, FG-02 in_progress, FG-03 pending + FG-04 nueva con ajuste sobre FG-01
    prev_plan = compute(base_tasks(), None, now, None)
    rp = base_tasks()
    rp["version"] = 5
    rp["features"].append({"id": "FG-04", "name": "D", "requirement_ids": ["RF-004"], "task_ids": ["T-006"]})
    rp["tasks"] += [
        {"id": "T-006", "feature_group": "FG-04", "type": "feature", "priority": "high", "status": "pending",
         "depends_on": [{"task_id": "T-003", "kind": "hard"}]},
        {"id": "T-007", "feature_group": "FG-01", "type": "feature", "priority": "low", "complexity": "low",
         "status": "pending", "depends_on": [], "adjusts_task_id": "T-002"},
        {"id": "T-008", "feature_group": "FG-04", "type": "contract", "priority": "high", "status": "pending", "depends_on": []},
    ]
    progress = {"features": [{"feature_id": "FG-01", "status": "done"}, {"feature_id": "FG-02", "status": "in_progress"},
                             {"feature_id": "FG-03", "status": "pending"}],
                "tasks": [{"task_id": "T-001", "status": "done"}, {"task_id": "T-002", "status": "done"},
                          {"task_id": "T-003", "status": "in_progress"}]}
    plan_r = compute_replan(rp, progress, prev_plan, "9.9.9", now)
    check(plan_r["metadata"]["replanned"] and plan_r["metadata"]["completed_feature_ids"] == ["FG-01"], "replan: done fuera del grafo")
    bids = [b["id"] for b in plan_r["batches"]]
    check(bids[0] == "BATCH-3" and plan_r["batches"][0]["task_ids"] == ["T-008"], "replan: contratos nuevos en lote propio (%s)" % bids)
    b_fg02 = next(b for b in plan_r["batches"] if any(e["feature_id"] == "FG-02" for e in b["features"]))
    check(b_fg02["id"] == "BATCH-1", "replan: in_progress conserva su lote")
    e_fg01 = next(e for b in plan_r["batches"] for e in b["features"] if e["feature_id"] == "FG-01")
    check(e_fg01["adjustment"] and e_fg01["groupable"] and e_fg01["task_ids"] == ["T-007"], "replan: ajuste trivial groupable")
    lv = {e["feature_id"]: b["id"] for b in plan_r["batches"] for e in b["features"]}
    check(lv["FG-03"] == "BATCH-4" and lv["FG-04"] == "BATCH-4", "replan: pending y nueva en paralelo, numeracion continua (%s)" % lv)
    check(plan_r["version"] == 2 and plan_r["metadata"]["tasks_version_ref"] == "5", "replan: version +1 y tasks_version_ref")
    check(not any(w.startswith("CONFLICTO") for w in plan_r["warnings"]), "replan: sin conflictos")
    rp["tasks"][2]["depends_on"].append({"task_id": "T-004", "kind": "hard"})   # T-003 (in_progress) depende hard de FG-03 pendiente
    plan_c = compute_replan(rp, progress, prev_plan, None, now)
    check(any(w.startswith("CONFLICTO") for w in plan_c["warnings"]), "replan: conflicto detectado")

    # replan sobre proyecto legado: el avance vive en tasks.json, sin progress.json
    lg = base_tasks()
    for t in lg["tasks"]:
        if t["feature_group"] == "FG-01":
            t["status"] = "done"
    lg["tasks"][3]["status"] = "in_progress"   # T-004 de FG-03 a medias
    plan_lg = compute_replan(lg, {}, prev_plan, None, now)
    check(plan_lg["metadata"]["completed_feature_ids"] == ["FG-01"], "legado: FG-01 done leida de tasks.json")
    lv_lg = {e["feature_id"]: b["id"] for b in plan_lg["batches"] for e in b["features"]}
    check("FG-01" not in lv_lg and set(lv_lg) == {"FG-02", "FG-03"}, "legado: solo el trabajo restante en lotes (%s)" % lv_lg)
    check(lv_lg["FG-03"] == "BATCH-2", "legado: in_progress conserva su lote")
    check(any("legado" in w for w in plan_lg["warnings"]), "legado: warning de status leido de tasks.json")

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
    ap.add_argument("--replan", action="store_true", help="replanificacion: lotes solo del trabajo restante")
    args = ap.parse_args(argv)

    plan_dir = Path(args.carpeta)
    tasks_path = plan_dir / "tasks.json"
    if not tasks_path.is_file():
        fail("no existe %s" % tasks_path)
    try:
        doc = json.loads(tasks_path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        fail("%s ilegible: %s" % (tasks_path, exc))

    progress = None
    if args.replan:
        ppath = plan_dir / "progress.json"
        if not ppath.is_file():
            if any(isinstance(t, dict) and t.get("status") in LEGACY_BUILD_STATUSES
                   for t in (doc.get("tasks") or [])):
                progress = {}  # build legado: el avance vive en tasks.json y se lee de ahi
            else:
                fail("--replan necesita progress.json (estado del build); si no existe, preguntale al usuario")
        else:
            try:
                progress = json.loads(ppath.read_text(encoding="utf-8-sig"))
            except (ValueError, OSError) as exc:
                fail("progress.json ilegible: %s" % exc)
    else:
        guard_replan(plan_dir, doc)

    prev = None
    out_path = plan_dir / "execution-plan.json"
    if out_path.is_file():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            print("aviso: execution-plan.json previo ilegible; se regenera desde version 1")

    now = args.ahora or datetime.now(timezone.utc).isoformat(timespec="seconds")
    plan = compute_replan(doc, progress, prev, args.pipeline_version, now) if args.replan else compute(doc, args.pipeline_version, now, prev)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = plan["summary"]
    print("escrito: %s (version %s)" % (out_path, plan["version"]))
    print(
        "lotes: %d | paralelismo maximo: %d | critical path: %d | seriales: %d | contratos: %d"
        % (s["batch_count"], s["max_parallel_degree"], s["critical_path_length"],
           s["truly_serial_batches"], s["contract_task_count"])
    )
    conflicts = 0
    for w in plan["warnings"]:
        if w.startswith("CONFLICTO"):
            conflicts += 1
            print(w)
        else:
            print("aviso: %s" % w)
    if conflicts:
        print("%d CONFLICTO(s): el plan quedo escrito pero requiere decision del usuario." % conflicts)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
