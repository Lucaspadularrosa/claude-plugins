#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista de la linea de base: .dev/requirements/*.json -> *.md legibles.

Los .json son los artefactos canonicos que escriben los subagentes; los .md son
vistas derivadas para humanos. Este script los regenera completos desde el JSON,
siempre desde cero: mismo input -> mismo .md, sin tokens de modelo, sin red, sin
dependencias. Los agentes NO escriben estos .md; los cambios manuales se pierden.

Artefactos que renderiza (los que existan en la carpeta):
  lel.json              -> lel.md
  product-map.json      -> product-map.md
  scenarios.json        -> scenarios.md
  requirements.json     -> requirements.md
  data-model.json       -> data-model.md
  technical-design.json -> technical-design.md

Cada .md arranca con el encabezado de sincronia que verifican las inspecciones:
  > Derivado de `<archivo>.json` version N — no editar a mano.

Solo stdlib, Python 3.8+. No modifica los .json.

Uso:
  python render_baseline_docs.py [carpeta] [--salida DIR] [--solo NOMBRE ...]

  carpeta   por defecto .dev/requirements (donde viven los .json canonicos)
  --salida  carpeta de salida (por defecto la misma carpeta de entrada)
  --solo    renderizar solo estos artefactos (ej.: --solo lel requirements)

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
    """Lista de ids -> 'A-01, A-02' (o '—' si esta vacia)."""
    return ", ".join(str(s) for s in seq) if seq else "—"


def header(doc_title, data, json_name):
    """Titulo + encabezado de derivacion con la version del JSON canonico."""
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
    summary = project.get("domain_summary", "")
    if summary:
        lines.append(summary)
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
        if q.get("status"):
            line += " — estado: %s" % q["status"]
        if q.get("resolution"):
            line += " — resolucion: %s" % q["resolution"]
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


# ------------------------------------------------------------------ lel.md


def render_lel(data):
    out = header("LEL — Lexico Extendido del Lenguaje", data, "lel.json")
    symbols = data.get("symbols", []) or []
    by_type = {}
    for s in symbols:
        by_type[s.get("type", "?")] = by_type.get(s.get("type", "?"), 0) + 1
    active = sum(1 for s in symbols if s.get("status", "active") == "active")
    tipos = ", ".join("%s: %d" % (t, n) for t, n in sorted(by_type.items()))
    out.append("Simbolos: %d (%s) — activos: %d." % (len(symbols), tipos, active))
    out.append("")
    out.append("## Simbolos")
    out.append("")
    for s in symbols:
        out.append("### %s — %s (%s)" % (s.get("id", "?"), s.get("canonical_name", ""), s.get("type", "?")))
        if s.get("status", "active") != "active":
            out.append("- Estado: **%s**" % s["status"])
        names = [n for n in (s.get("names") or []) if n != s.get("canonical_name")]
        if names:
            out.append("- Nombres: %s" % ", ".join(names))
        if s.get("aliases"):
            out.append("- Aliases: %s" % ", ".join(s["aliases"]))
        for label, key in (("Nociones", "notions"), ("Impactos", "impacts")):
            entries = s.get(key) or []
            if entries:
                out.append("- %s:" % label)
                for e in entries:
                    out.append("  - `%s`: %s" % (e.get("id", "?"), e.get("statement", "")))
        if s.get("related_symbol_ids"):
            out.append("- Relacionados: %s" % ids(s["related_symbol_ids"]))
        for label, key in (("Preguntas abiertas", "open_questions"), ("Suposiciones", "assumptions")):
            if s.get(key):
                out.append("- %s: %s" % (label, "; ".join(str(x) for x in s[key])))
        out.append("")
    alias_map = data.get("alias_map", []) or []
    if alias_map:
        out.append("## Alias")
        out.append("")
        out.append("| Alias | Simbolo | Confianza |")
        out.append("|---|---|---|")
        for a in alias_map:
            out.append("| %s | %s | %s |" % (cell(a.get("alias")), cell(a.get("symbol_id")), cell(a.get("confidence"))))
        out.append("")
    section_open_questions(out, data.get("open_questions"))
    section_strings(out, "Suposiciones", data.get("assumptions"))
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# ---------------------------------------------------------- product-map.md

_STATUS_ORDER = ("baselined", "elaborated", "stub", "proposed", "deprecated")
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def render_product_map(data):
    out = header("Mapa del producto", data, "product-map.json")
    features = data.get("features", []) or []
    counts = {}
    for f in features:
        counts[f.get("status", "?")] = counts.get(f.get("status", "?"), 0) + 1
    resumen = ", ".join("%s: %d" % (s, counts[s]) for s in _STATUS_ORDER if s in counts)
    extras = ", ".join("%s: %d" % (s, n) for s, n in sorted(counts.items()) if s not in _STATUS_ORDER)
    out.append("Features: %d (%s)." % (len(features), "; ".join(x for x in (resumen, extras) if x)))
    out.append("")
    for status in list(_STATUS_ORDER) + sorted(set(counts) - set(_STATUS_ORDER)):
        group = [f for f in features if f.get("status") == status]
        if not group:
            continue
        group.sort(key=lambda f: (_PRIORITY_ORDER.get(f.get("priority"), 9), str(f.get("id"))))
        out.append("## %s (%d)" % (status.capitalize(), len(group)))
        out.append("")
        for f in group:
            out.append("### %s — %s (prioridad %s)" % (f.get("id", "?"), f.get("name", ""), f.get("priority", "?")))
            if f.get("description"):
                out.append(f["description"])
            stubs = f.get("scenario_stubs") or []
            if stubs:
                out.append("- Escenarios:")
                for sc in stubs:
                    sid = sc.get("id", "?")
                    title = sc.get("title") or sc.get("name") or ""
                    st = sc.get("status", "")
                    out.append("  - `%s` %s%s" % (sid, title, " (%s)" % st if st else ""))
            if f.get("discovered_in"):
                out.append("- Descubierta en: %s" % f["discovered_in"])
            out.append("")
    proposals = data.get("pending_proposals", []) or []
    if proposals:
        out.append("## Propuestas pendientes")
        out.append("")
        for p in proposals:
            desc = p.get("summary") or p.get("description") or p.get("proposal") or ""
            line = "- `%s` sobre `%s`" % (p.get("id", "?"), p.get("target_id", p.get("target_feature_id", "?")))
            if p.get("suggested_action"):
                line += " (%s)" % p["suggested_action"]
            if p.get("status"):
                line += " [%s]" % p["status"]
            if desc:
                line += ": %s" % desc
            out.append(line)
        out.append("")
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# ------------------------------------------------------------ scenarios.md


def render_scenarios(data):
    out = header("Escenarios", data, "scenarios.json")
    scenarios = data.get("scenarios", []) or []
    summary = data.get("summary", {}) or {}
    out.append(
        "Escenarios: %d (current: %s, future: %s). Episodios: %s. Excepciones: %s."
        % (
            len(scenarios),
            summary.get("current_scenarios", "?"),
            summary.get("future_scenarios", "?"),
            summary.get("total_episodes", "?"),
            summary.get("total_exceptions", "?"),
        )
    )
    out.append("")
    for sc in scenarios:
        out.append("## %s — %s" % (sc.get("id", "?"), sc.get("title", "")))
        meta = "Tipo: %s | Estado: %s" % (sc.get("scenario_type", "?"), sc.get("status", "?"))
        out.append("_%s_" % meta)
        out.append("")
        if sc.get("goal"):
            out.append("**Objetivo**: %s" % sc["goal"])
            out.append("")
        ctx = sc.get("context") or {}
        ctx_bits = [ctx.get("geographic_location"), ctx.get("temporality")]
        ctx_bits = [c for c in ctx_bits if c]
        if ctx_bits:
            out.append("- Contexto: %s" % " — ".join(ctx_bits))
        for pre in ctx.get("preconditions") or []:
            out.append("- Precondicion: %s" % pre)
        actors = ["%s (`%s`)" % (a.get("name", "?"), a.get("lel_symbol_id", "?")) for a in sc.get("actors") or []]
        if actors:
            out.append("- Actores: %s" % ", ".join(actors))
        resources = ["%s (`%s`)" % (r.get("name", "?"), r.get("lel_symbol_id", "?")) for r in sc.get("resources") or []]
        if resources:
            out.append("- Recursos: %s" % ", ".join(resources))
        out.append("")
        episodes = sc.get("episodes") or []
        if episodes:
            out.append("**Episodios**:")
            out.append("")
            for i, ep in enumerate(episodes, start=1):
                marks = []
                if ep.get("episode_type") and ep["episode_type"] != "simple":
                    marks.append(ep["episode_type"])
                if ep.get("condition"):
                    marks.append("si: %s" % ep["condition"])
                suffix = " (-> %s)" % ep["referenced_scenario_id"] if ep.get("referenced_scenario_id") else ""
                mark = " _[%s]_" % "; ".join(marks) if marks else ""
                out.append("%d. %s%s%s" % (i, ep.get("sentence", ""), mark, suffix))
            out.append("")
        exceptions = sc.get("exceptions") or []
        if exceptions:
            out.append("**Excepciones**:")
            out.append("")
            for ex in exceptions:
                handling = ex.get("handling") or ex.get("resolution") or ex.get("treatment") or ex.get("response") or ""
                line = "- `%s`: %s" % (ex.get("id", "?"), ex.get("cause", ""))
                if handling:
                    line += " -> %s" % handling
                if ex.get("referenced_scenario_id"):
                    line += " (-> %s)" % ex["referenced_scenario_id"]
                out.append(line)
            out.append("")
        if sc.get("lel_symbol_ids"):
            out.append("- Simbolos LEL: %s" % ids(sc["lel_symbol_ids"]))
        if sc.get("related_scenario_ids"):
            out.append("- Relacionados: %s" % ids(sc["related_scenario_ids"]))
        out.append("")
    section_open_questions(out, data.get("open_questions"))
    section_strings(out, "Suposiciones", data.get("assumptions"))
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# --------------------------------------------------------- requirements.md


def _render_requirement(out, r, functional):
    out.append("### %s — %s" % (r.get("id", "?"), r.get("title", "")))
    meta = "Feature: %s | Prioridad: %s | Esfuerzo: %s | Verificacion: %s | Estado: %s" % (
        r.get("feature_group", "?"),
        r.get("priority", "?"),
        r.get("estimated_effort", "?"),
        r.get("verification_method", "?"),
        r.get("status", "?"),
    )
    if not functional and r.get("category"):
        meta = "Categoria: %s | %s" % (r["category"], meta)
    out.append("_%s_" % meta)
    out.append("")
    if r.get("statement"):
        out.append(r["statement"])
        out.append("")
    if not functional and r.get("metric"):
        out.append("- Metrica: %s" % r["metric"])
    if r.get("depends_on"):
        out.append("- Depende de: %s" % ids(r["depends_on"]))
    criteria = r.get("acceptance_criteria") or []
    if criteria:
        out.append("- Criterios de aceptacion:")
        for ac in criteria:
            out.append(
                "  - `%s` — Dado %s; cuando %s; entonces %s"
                % (ac.get("id", "?"), ac.get("given", "?"), ac.get("when", "?"), ac.get("then", "?"))
            )
    trace = []
    if r.get("source_scenario_ids"):
        trace.append("escenarios %s" % ids(r["source_scenario_ids"]))
    if r.get("lel_symbol_ids"):
        trace.append("simbolos %s" % ids(r["lel_symbol_ids"]))
    if trace:
        out.append("- Traza: %s" % "; ".join(trace))
    if r.get("assumptions"):
        out.append("- Suposiciones: %s" % "; ".join(str(a) for a in r["assumptions"]))
    if r.get("open_questions"):
        out.append("- Preguntas abiertas: %s" % "; ".join(str(q) for q in r["open_questions"]))
    out.append("")


def render_requirements(data):
    out = header("Requisitos", data, "requirements.json")
    functional = data.get("functional_requirements", []) or []
    non_functional = data.get("non_functional_requirements", []) or []
    summary = data.get("summary", {}) or {}
    out.append(
        "Requisitos: %d funcionales + %d no funcionales. Prioridad alta: %s, media: %s, baja: %s."
        % (
            len(functional),
            len(non_functional),
            summary.get("high_priority", "?"),
            summary.get("medium_priority", "?"),
            summary.get("low_priority", "?"),
        )
    )
    out.append("")
    groups = data.get("feature_groups", []) or []
    if groups:
        out.append("## Features")
        out.append("")
        out.append("| Id | Feature | Requisitos |")
        out.append("|---|---|---|")
        for g in groups:
            out.append("| %s | %s | %s |" % (cell(g.get("id")), cell(g.get("name")), cell(ids(g.get("requirement_ids") or []))))
        out.append("")
    rules = data.get("business_rules", []) or []
    if rules:
        out.append("## Reglas de negocio")
        out.append("")
        for br in rules:
            kind = " (%s)" % br["kind"] if br.get("kind") else ""
            line = "- `%s`%s: %s" % (br.get("id", "?"), kind, br.get("statement", ""))
            if br.get("enforced_by"):
                line += " — la hacen cumplir: %s" % ids(br["enforced_by"])
            out.append(line)
        out.append("")
    if functional:
        out.append("## Requisitos funcionales")
        out.append("")
        for r in functional:
            _render_requirement(out, r, functional=True)
    if non_functional:
        out.append("## Requisitos no funcionales")
        out.append("")
        for r in non_functional:
            _render_requirement(out, r, functional=False)
    section_open_questions(out, data.get("open_questions"))
    section_strings(out, "Suposiciones", data.get("assumptions"))
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# ----------------------------------------------------------- data-model.md


def render_data_model(data):
    out = header("Modelo de datos", data, "data-model.json")
    entities = data.get("entities", []) or []
    relationships = data.get("relationships", []) or []
    summary = data.get("summary", {}) or {}
    out.append(
        "Entidades: %d. Relaciones: %d. Normalizacion: %s."
        % (len(entities), len(relationships), summary.get("normalization_level", "?"))
    )
    out.append("")
    names = {e.get("id"): e.get("name", e.get("id", "?")) for e in entities}
    if entities:
        out.append("## Entidades")
        out.append("")
        for e in entities:
            out.append("### %s — %s" % (e.get("id", "?"), e.get("name", "")))
            if e.get("description"):
                out.append(e["description"])
                out.append("")
            bits = []
            if e.get("lel_symbol_id"):
                bits.append("simbolo `%s`" % e["lel_symbol_id"])
            if e.get("primary_key"):
                bits.append("PK: %s" % ids(e["primary_key"]))
            if e.get("source_requirement_ids"):
                bits.append("requisitos %s" % ids(e["source_requirement_ids"]))
            if bits:
                out.append("_%s_" % " | ".join(bits))
                out.append("")
            fields = e.get("fields") or []
            if fields:
                out.append("| Campo | Tipo | Obligatorio | Unico | Notas |")
                out.append("|---|---|---|---|---|")
                for f in fields:
                    out.append(
                        "| %s | %s | %s | %s | %s |"
                        % (
                            cell(f.get("name")),
                            cell(f.get("type")),
                            "si" if f.get("required") else "no",
                            "si" if f.get("unique") else "no",
                            cell(f.get("notes", "")),
                        )
                    )
                out.append("")
            if e.get("open_questions"):
                out.append("- Preguntas abiertas: %s" % "; ".join(str(q) for q in e["open_questions"]))
                out.append("")
    if relationships:
        out.append("## Relaciones")
        out.append("")
        for r in relationships:
            line = "- `%s`: %s -> %s (%s)" % (
                r.get("id", "?"),
                names.get(r.get("from_entity_id"), r.get("from_entity_id", "?")),
                names.get(r.get("to_entity_id"), r.get("to_entity_id", "?")),
                r.get("type", "?"),
            )
            if r.get("name"):
                line += " — %s" % r["name"]
            if r.get("notes"):
                line += ". %s" % r["notes"]
            out.append(line)
        out.append("")
    section_open_questions(out, data.get("open_questions"))
    section_strings(out, "Suposiciones", data.get("assumptions"))
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# ----------------------------------------------------- technical-design.md


def render_technical_design(data):
    out = header("Diseno tecnico", data, "technical-design.json")
    modules = data.get("modules", []) or []
    apis = data.get("api_contracts", []) or []
    screens = data.get("screens", []) or []
    decisions = data.get("decisions", []) or []
    out.append(
        "Modulos: %d. Contratos de API: %d. Pantallas: %d. Decisiones: %d."
        % (len(modules), len(apis), len(screens), len(decisions))
    )
    out.append("")
    stack = data.get("stack", []) or []
    if stack:
        out.append("## Stack")
        out.append("")
        out.append("| Capa | Tecnologia | Racional |")
        out.append("|---|---|---|")
        for s in stack:
            out.append("| %s | %s | %s |" % (cell(s.get("layer")), cell(s.get("technology")), cell(s.get("rationale", ""))))
        out.append("")
    if modules:
        out.append("## Modulos")
        out.append("")
        for m in modules:
            out.append("### %s — %s" % (m.get("id", "?"), m.get("name", "")))
            if m.get("responsibility"):
                out.append(m["responsibility"])
            bits = []
            if m.get("feature_group"):
                bits.append("feature %s" % m["feature_group"])
            if m.get("depends_on"):
                bits.append("depende de %s" % ids(m["depends_on"]))
            if m.get("requirement_ids"):
                bits.append("requisitos %s" % ids(m["requirement_ids"]))
            if m.get("entity_ids"):
                bits.append("entidades %s" % ids(m["entity_ids"]))
            if bits:
                out.append("")
                out.append("_%s_" % " | ".join(bits))
            out.append("")
    if apis:
        out.append("## Contratos de API")
        out.append("")
        out.append("| Id | Metodo | Path | Proposito | Auth | Requisitos |")
        out.append("|---|---|---|---|---|---|")
        for a in apis:
            out.append(
                "| %s | %s | %s | %s | %s | %s |"
                % (
                    cell(a.get("id")),
                    cell(a.get("method")),
                    cell(a.get("path")),
                    cell(a.get("purpose", "")),
                    "si" if a.get("auth_required") else "no",
                    cell(ids(a.get("requirement_ids") or [])),
                )
            )
        out.append("")
    if screens:
        out.append("## Pantallas")
        out.append("")
        for s in screens:
            line = "- `%s` **%s**: %s" % (s.get("id", "?"), s.get("name", ""), s.get("purpose", ""))
            if s.get("role_access"):
                line += " (roles: %s)" % ids(s["role_access"])
            if s.get("requirement_ids"):
                line += " — requisitos %s" % ids(s["requirement_ids"])
            out.append(line)
        out.append("")
    if decisions:
        out.append("## Decisiones (ADRs)")
        out.append("")
        for d in decisions:
            out.append("### %s — %s (%s)" % (d.get("id", "?"), d.get("title", ""), d.get("status", "?")))
            for label, key in (("Contexto", "context"), ("Decision", "decision"), ("Consecuencias", "consequences")):
                if d.get(key):
                    out.append("- %s: %s" % (label, d[key]))
            if d.get("requirement_ids"):
                out.append("- Requisitos: %s" % ids(d["requirement_ids"]))
            out.append("")
    section_open_questions(out, data.get("open_questions"))
    section_strings(out, "Suposiciones", data.get("assumptions"))
    section_strings(out, "Avisos", data.get("warnings"))
    return out


# --------------------------------------------------------------------- main

RENDERERS = {
    "lel": ("lel.json", "lel.md", render_lel),
    "product-map": ("product-map.json", "product-map.md", render_product_map),
    "scenarios": ("scenarios.json", "scenarios.md", render_scenarios),
    "requirements": ("requirements.json", "requirements.md", render_requirements),
    "data-model": ("data-model.json", "data-model.md", render_data_model),
    "technical-design": ("technical-design.json", "technical-design.md", render_technical_design),
}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default=".dev/requirements", help="carpeta con los .json canonicos (default: .dev/requirements)")
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
