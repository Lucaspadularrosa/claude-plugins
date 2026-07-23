#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista del plan: .dev/plan/*.json -> *.md legibles.

Los .json son los artefactos canonicos que escriben los subagentes; los .md son
vistas derivadas para humanos. Este script los regenera completos desde el JSON,
siempre desde cero: mismo input -> mismo .md, sin tokens de modelo, sin red, sin
dependencias. Los agentes NO escriben estos .md; los cambios manuales se pierden.

Artefactos que renderiza (los que existan en la carpeta):
  tasks.json          -> tasks.md
  execution-plan.json -> execution-plan.md

Cada .md arranca con el encabezado de sincronia que verifican las inspecciones:
  > Derivado de `<archivo>.json` version N — no editar a mano.

Solo stdlib, Python 3.8+. No modifica los .json.

Uso:
  python render_plan_docs.py [carpeta] [--salida DIR] [--solo NOMBRE ...]

  carpeta   por defecto .dev/plan (donde viven los .json canonicos)
  --salida  carpeta de salida (por defecto la misma carpeta)
  --solo    renderizar solo estos artefactos (tasks, execution-plan)

Salida: una linea por .md generado y avisos por .json ausente o ilegible.
Exit 1 solo si un .json presente no se pudo parsear o hubo error de IO.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --------------------------------------------------------------- utilidades


def cell(text):
    """Texto seguro para una celda de tabla Markdown: sin pipes ni saltos."""
    return " ".join(str(text if text is not None else "").split()).replace("|", "\\|")


def ids(seq):
    return ", ".join(str(s) for s in seq) if seq else "—"


def header(doc_title, data, json_name):
    project = data.get("project", {}) or {}
    name = project.get("name", "")
    lines = ["# %s%s" % (doc_title, " — %s" % name if name else ""), ""]
    lines.append(
        "> Derivado de `%s` version %s — no editar a mano." % (json_name, data.get("version", "?"))
    )
    lines.append("> Regenerado por script al cierre de cada corrida; los cambios manuales se pierden.")
    lines.append("")
    updated = (data.get("metadata", {}) or {}).get("updated_at", "")
    if updated:
        lines.append("_Actualizado: %s_" % updated)
        lines.append("")
    return lines


def section_open_questions(out, questions):
    if not questions:
        return
    out.append("## Preguntas abiertas")
    out.append("")
    for q in questions:
        flag = " **[bloqueante]**" if q.get("blocking") else ""
        role = " (%s)" % q["target_role"] if q.get("target_role") else ""
        line = "- `%s`%s%s: %s" % (q.get("id", "?"), flag, role, q.get("question", ""))
        if q.get("related_task_ids"):
            line += " — tareas: %s" % ids(q["related_task_ids"])
        out.append(line)
    out.append("")


def section_strings(out, title, items):
    if not items:
        return
    out.append("## %s" % title)
    out.append("")
    for s in items:
        out.append("- %s" % s)
    out.append("")


def _dep(dep):
    """Una entrada de depends_on -> 'T-002 (hard)'."""
    if isinstance(dep, dict):
        return "%s (%s)" % (dep.get("task_id", "?"), dep.get("kind", "hard"))
    return str(dep)


# ------------------------------------------------------------------ tasks.md


def render_tasks(data):
    out = header("Tareas del plan", data, "tasks.json")
    features = data.get("features", []) or []
    tasks = data.get("tasks", []) or []
    summary = data.get("summary", {}) or {}
    metadata = data.get("metadata", {}) or {}
    cx = summary.get("complexity_breakdown", {}) or {}
    out.append(
        "Features: %d. Tareas: %d (complejidad low: %s, medium: %s, high: %s)."
        % (len(features), len(tasks), cx.get("low", 0), cx.get("medium", 0), cx.get("high", 0))
    )
    uncovered = summary.get("uncovered_requirement_ids") or []
    if uncovered:
        out.append("Requisitos sin cubrir: %s." % ids(uncovered))
    if metadata.get("applied_changelog_ids"):
        out.append("Changelog absorbido: %s." % ids(metadata["applied_changelog_ids"]))
    if metadata.get("deferred_changelog_ids"):
        out.append("Changelog postergado: %s." % ids(metadata["deferred_changelog_ids"]))
    out.append("")
    by_feature = {}
    for t in tasks:
        by_feature.setdefault(t.get("feature_group"), []).append(t)
    for f in features:
        fid = f.get("id", "?")
        out.append("## %s — %s" % (fid, f.get("name", "")))
        if f.get("synthetic"):
            out.append("_%s_" % (f.get("note") or "Feature sintetica de planificacion."))
        if f.get("description"):
            out.append(f["description"])
        if f.get("requirement_ids"):
            out.append("")
            out.append("Requisitos: %s" % ids(f["requirement_ids"]))
        out.append("")
        rows = by_feature.get(fid) or [t for t in tasks if t.get("id") in (f.get("task_ids") or [])]
        if rows:
            out.append("| Tarea | Titulo | Tipo | Prioridad | Complejidad | Depende de | Requisitos | Estado |")
            out.append("|---|---|---|---|---|---|---|---|")
            for t in rows:
                deps = ", ".join(_dep(d) for d in t.get("depends_on") or []) or "—"
                out.append(
                    "| %s | %s | %s | %s | %s | %s | %s | %s |"
                    % (
                        cell(t.get("id")),
                        cell(t.get("title")),
                        cell(t.get("type")),
                        cell(t.get("priority")),
                        cell(t.get("complexity")),
                        cell(deps),
                        cell(ids(t.get("requirement_ids") or [])),
                        cell(t.get("status", "pending")),
                    )
                )
            out.append("")
    orphans = [t for t in tasks if t.get("feature_group") not in {f.get("id") for f in features}]
    if orphans:
        out.append("## Tareas sin feature en el plan")
        out.append("")
        for t in orphans:
            out.append("- `%s` %s (feature declarada: %s)" % (t.get("id", "?"), t.get("title", ""), t.get("feature_group", "?")))
        out.append("")
    section_open_questions(out, data.get("open_questions"))
    section_strings(out, "Suposiciones", data.get("assumptions"))
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# --------------------------------------------------------- execution-plan.md


def render_execution_plan(data):
    out = header("Plan de ejecucion", data, "execution-plan.json")
    summary = data.get("summary", {}) or {}
    metadata = data.get("metadata", {}) or {}
    batches = data.get("batches", []) or []
    widest = ""
    for b in batches:
        feats = b.get("features") or []
        if len(feats) == summary.get("max_parallel_degree"):
            widest = " (lote %s)" % b.get("id", "?")
            break
    out.append("- Maximo paralelismo: %s agentes simultaneos%s." % (summary.get("max_parallel_degree", "?"), widest))
    out.append("- Critical path: %s turno(s)." % summary.get("critical_path_length", "?"))
    out.append("- Lotes realmente seriales: %s de %s." % (summary.get("truly_serial_batches", "?"), summary.get("batch_count", "?")))
    out.append("- Features: %s. Tareas-contrato: %s." % (summary.get("feature_count", "?"), summary.get("contract_task_count", "?")))
    if metadata.get("replanned"):
        out.append("- Replanificado: si. Features completadas fuera del grafo: %s." % ids(metadata.get("completed_feature_ids") or []))
    out.append("")
    contract_round = data.get("contract_round")
    if contract_round:
        out.append("## Ronda de contratos (%s)" % contract_round.get("id", "BATCH-0"))
        out.append("")
        out.append("- Tareas: %s" % ids(contract_round.get("task_ids") or []))
        if contract_round.get("rationale"):
            out.append("- %s" % contract_round["rationale"])
        out.append("")
    for b in batches:
        out.append("## %s" % b.get("id", "?"))
        out.append("")
        if b.get("unlocks_after"):
            out.append("_Desbloquea tras: %s_" % ids(b["unlocks_after"]))
            out.append("")
        if b.get("rationale"):
            out.append(b["rationale"])
            out.append("")
        for f in b.get("features") or []:
            title = "### %s" % f.get("feature_id", "?")
            if f.get("adjustment"):
                title += " (ajuste)"
            out.append(title)
            if f.get("branch"):
                out.append("- Rama: `%s`" % f["branch"])
            order = f.get("task_order") or f.get("task_ids") or []
            if order:
                out.append("- Orden de tareas: %s" % " -> ".join(str(t) for t in order))
            for w in f.get("waits_for") or []:
                edges = "; ".join(
                    "%s -> %s (%s)" % (e.get("from_task", "?"), e.get("to_task", "?"), e.get("kind", "?"))
                    for e in w.get("edges") or []
                )
                line = "- Espera a %s (%s)" % (w.get("feature_id", "?"), w.get("batch_id", "?"))
                if edges:
                    line += ": %s" % edges
                out.append(line)
            out.append("")
    warnings = data.get("warnings", []) or []
    if warnings:
        out.append("## Sugerencias de extraccion de contratos y avisos")
        out.append("")
        for w in warnings:
            out.append("- %s" % w)
        out.append("")
    return out


# --------------------------------------------------------------------- main

RENDERERS = {
    "tasks": ("tasks.json", "tasks.md", render_tasks),
    "execution-plan": ("execution-plan.json", "execution-plan.md", render_execution_plan),
}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default=".dev/plan", help="carpeta con los .json canonicos (default: .dev/plan)")
    ap.add_argument("--salida", default=None, help="carpeta de salida (default: la misma carpeta)")
    ap.add_argument("--solo", nargs="+", choices=sorted(RENDERERS), default=None, help="renderizar solo estos artefactos")
    args = ap.parse_args(argv)

    src = Path(args.carpeta)
    if not src.is_dir():
        print("No existe la carpeta: %s" % src)
        return 1
    out_dir = Path(args.salida) if args.salida else src
    out_dir.mkdir(parents=True, exist_ok=True)

    names = args.solo or sorted(RENDERERS)
    rendered = 0
    failed = 0
    for name in names:
        json_name, md_name, renderer = RENDERERS[name]
        json_path = src / json_name
        if not json_path.is_file():
            print("aviso: no existe %s — se saltea" % json_path)
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            print("ERROR: %s ilegible: %s" % (json_path, exc))
            failed += 1
            continue
        lines = renderer(data)
        while lines and lines[-1] == "":
            lines.pop()
        dest = out_dir / md_name
        dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("derivado: %s (version %s)" % (dest, data.get("version", "?")))
        rendered += 1

    print("Listo: %d .md derivados en %s%s" % (rendered, out_dir, " (%d con error)" % failed if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
