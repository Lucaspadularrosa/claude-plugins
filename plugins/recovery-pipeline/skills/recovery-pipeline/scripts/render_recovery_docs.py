#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista del diagnostico: .dev/recovery/*.json -> *.md legibles.

Los .json son los artefactos canonicos que escriben los subagentes del recovery; los
.md son vistas derivadas para humanos. Este script los regenera completos desde el
JSON: mismo input -> mismo .md, sin tokens de modelo, sin red, sin dependencias.
Los agentes NO escriben estos .md (antes lo hacian y duplicaban el artefacto entero
en tokens de salida); los cambios manuales se pierden.

Artefactos que renderiza (los que existan en la carpeta):
  code-inventory.json   -> code-inventory.md
  behavior-map.json     -> behavior-map.md
  state-report.json     -> state-report.md
  owner-questions.json  -> owner-questions.md   (con espacio de respuesta por pregunta)

Cada .md arranca con el encabezado de sincronia:
  > Derivado de `<archivo>.json` version N — no editar a mano.

Solo stdlib, Python 3.8+. No modifica los .json.

Uso:
  python render_recovery_docs.py [carpeta] [--solo NOMBRE ...]
  python render_recovery_docs.py --self-test

  carpeta   por defecto .dev/recovery
  --solo    renderizar solo estos artefactos (ej.: --solo state-report owner-questions)

Salida: una linea por .md generado. Exit 1 solo si un .json presente no parsea.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATE_LABEL = {"complete": "Completa", "partial": "A medias", "skeleton": "Esqueleto", "dead": "Muerta"}
GAP_KIND = {"half_built": "A medio construir", "loose_end": "Cabos sueltos", "inconsistency": "Incoherencias",
            "structural_absence": "Ausencias estructurales", "unconfirmed_decision": "Decisiones sin confirmar"}
PRIORITY = {"high": "Alta", "medium": "Media", "low": "Baja"}


def cell(text):
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def refs(seq):
    return ", ".join("`%s`" % r for r in (seq or []))


def header(title, data, json_name):
    return ["# %s" % title, "", "> Derivado de `%s` version %s — no editar a mano." % (json_name, data.get("version", "?")), ""]


def strings_section(out, title, items):
    if items:
        out += ["## %s" % title, ""] + ["- %s" % s for s in items] + [""]


def render_code_inventory(d):
    s = d.get("summary") or {}
    out = header("Inventario de codigo", d, "code-inventory.json")
    out += ["- **Lenguaje principal**: %s" % s.get("primary_language", ""),
            "- **Frameworks**: %s" % ", ".join(s.get("frameworks") or []),
            "- **LOC estimadas**: %s" % s.get("loc_estimate", ""),
            "- **Tests**: %s" % s.get("test_presence", ""),
            "- **Docs**: %s" % s.get("docs_presence", ""), ""]
    if d.get("stack"):
        out += ["## Stack", "", "| Capa | Tecnologia | Version | Evidencia |", "|---|---|---|---|"]
        out += ["| %s | %s | %s | %s |" % (cell(x.get("layer")), cell(x.get("technology")), cell(x.get("version")), cell(x.get("evidence"))) for x in d["stack"]]
        out.append("")
    if d.get("layout"):
        out += ["## Layout", "", "| Ruta | Proposito | Evidencia |", "|---|---|---|"]
        out += ["| `%s` | %s | %s |" % (cell(x.get("path")), cell(x.get("purpose")), cell(x.get("evidence"))) for x in d["layout"]]
        out.append("")
    if d.get("modules"):
        out += ["## Modulos", "", "| Id | Nombre | Responsabilidad | Depende de | Rutas |", "|---|---|---|---|---|"]
        out += ["| %s | %s | %s | %s | %s |" % (x.get("id"), cell(x.get("name")), cell(x.get("responsibility")), ", ".join(x.get("depends_on") or []), cell(", ".join(x.get("paths") or []))) for x in d["modules"]]
        out.append("")
    if d.get("entry_points"):
        out += ["## Puntos de entrada (%d)" % len(d["entry_points"]), "", "| Id | Tipo | Ruta | Descripcion | Evidencia |", "|---|---|---|---|---|"]
        out += ["| %s | %s | `%s` | %s | %s |" % (x.get("id"), x.get("kind"), cell(x.get("path")), cell(x.get("description")), cell(x.get("evidence"))) for x in d["entry_points"]]
        out.append("")
    for key, title in (("data_stores", "Stores de datos"), ("external_services", "Servicios externos")):
        if d.get(key):
            out += ["## %s" % title, ""] + ["- **%s** (%s): %s" % (cell(x.get("name")), cell(x.get("kind") or x.get("purpose")), cell(x.get("evidence"))) for x in d[key]] + [""]
    if d.get("health_signals"):
        out += ["## Señales de salud", ""] + ["- [%s] %s — %s" % (x.get("severity"), cell(x.get("signal")), cell(x.get("evidence"))) for x in d["health_signals"]] + [""]
    if d.get("doc_contradictions"):
        out += ["## Contradicciones con la doc", ""] + ["- **%s** (%s) vs. realidad: %s — %s" % (cell(x.get("claim")), cell(x.get("doc")), cell(x.get("reality")), cell(x.get("evidence"))) for x in d["doc_contradictions"]] + [""]
    strings_section(out, "Preguntas abiertas", d.get("open_questions"))
    strings_section(out, "Avisos", d.get("warnings"))
    return "\n".join(out)


def render_behavior_map(d):
    s = d.get("summary") or {}
    out = header("Mapa de comportamiento", d, "behavior-map.json")
    out += ["- **Capacidades**: %s (completas %s, a medias %s, esqueleto %s)" % (s.get("capability_count", 0), s.get("complete_count", 0), s.get("partial_count", 0), s.get("skeleton_count", 0)),
            "- **Terminos del vocabulario**: %s" % s.get("vocabulary_term_count", 0), ""]
    for c in d.get("capabilities") or []:
        out += ["## %s — %s (%s)" % (c.get("id"), c.get("name"), STATE_LABEL.get(c.get("implementation_status"), c.get("implementation_status"))), ""]
        if c.get("description"):
            out += [c["description"], ""]
        out += ["- **Actores**: %s" % ", ".join(c.get("actors") or []),
                "- **Entry points**: %s · **Modulos**: %s" % (", ".join(c.get("entry_point_ids") or []), ", ".join(c.get("module_ids") or [])),
                "- **Manejo de errores**: %s" % c.get("error_handling", "")]
        if c.get("status_evidence"):
            out.append("- **Estado**: %s" % c["status_evidence"])
        if c.get("flow"):
            out += ["", "**Flujo**", ""] + ["%d. %s" % (i, step) for i, step in enumerate(c["flow"], 1)]
        if c.get("business_rules"):
            out += ["", "**Reglas de negocio**", ""] + ["- %s (`%s`)" % (cell(r.get("rule")), r.get("evidence")) for r in c["business_rules"]]
        if c.get("evidence_refs"):
            out += ["", "Evidencia: %s" % refs(c["evidence_refs"])]
        out.append("")
    if d.get("vocabulary"):
        out += ["## Vocabulario", "", "| Termino | Tipo | Variantes | Significado en el codigo | Evidencia |", "|---|---|---|---|---|"]
        out += ["| %s | %s | %s | %s | %s |" % (cell(v.get("term")), v.get("kind"), cell(", ".join(v.get("variants") or [])), cell(v.get("meaning_from_code")), cell(", ".join(v.get("evidence_refs") or []))) for v in d["vocabulary"]]
        out.append("")
    if d.get("data_entities"):
        out += ["## Entidades de datos", ""]
        for e in d["data_entities"]:
            fields = ", ".join("%s:%s%s" % (f.get("name"), f.get("type"), "" if f.get("used", True) else " (sin uso)") for f in e.get("fields") or [])
            out += ["- **%s %s** — campos: %s; relaciones: %s; evidencia: %s" % (e.get("id"), cell(e.get("name")), cell(fields), cell(", ".join(e.get("relationships") or [])), cell(e.get("evidence")))]
        out.append("")
    strings_section(out, "Preguntas abiertas", d.get("open_questions"))
    strings_section(out, "Avisos", d.get("warnings"))
    return "\n".join(out)


def render_state_report(d):
    s = d.get("summary") or {}
    out = header("Estado de la aplicacion", d, "state-report.json")
    out += [s.get("overall_state", ""), "",
            "| Completas | A medias | Esqueleto | Codigo muerto | Huecos | Preguntas |", "|---|---|---|---|---|---|",
            "| %s | %s | %s | %s | %s | %s |" % (s.get("features_complete", 0), s.get("features_partial", 0), s.get("features_skeleton", 0), s.get("dead_code_findings", 0), s.get("gap_count", 0), s.get("question_count", 0)), ""]
    if d.get("feature_states"):
        out += ["## Features por estado", "", "| Feature | Estado | Que falta | Capacidades |", "|---|---|---|---|"]
        for f in d["feature_states"]:
            name = "%s%s" % (("%s — " % f["feature_id"]) if f.get("feature_id") else "", f.get("name", ""))
            out.append("| %s | %s | %s | %s |" % (cell(name), STATE_LABEL.get(f.get("state"), f.get("state")), cell("; ".join(f.get("missing") or [])), ", ".join(f.get("capability_refs") or [])))
        out.append("")
    gaps = d.get("gaps") or []
    if gaps:
        out += ["## Huecos", ""]
        by_kind = {}
        for g in gaps:
            by_kind.setdefault(g.get("kind"), []).append(g)
        for kind in GAP_KIND:
            if kind not in by_kind:
                continue
            out += ["### %s" % GAP_KIND[kind], ""]
            for g in by_kind[kind]:
                out.append("- **%s** [%s] %s — evidencia: %s. Resolucion sugerida: %s" % (g.get("id"), g.get("status", "open"), cell(g.get("description")), cell(", ".join(g.get("evidence_refs") or [])), cell(g.get("suggested_resolution"))))
            out.append("")
        for kind, items in by_kind.items():
            if kind in GAP_KIND:
                continue
            out += ["### %s" % kind, ""] + ["- **%s** %s" % (g.get("id"), cell(g.get("description"))) for g in items] + [""]
    if d.get("audit_signals"):
        out += ["## Señales para auditoria", ""] + ["- %s (%s)" % (cell(a.get("signal")), cell(", ".join(a.get("evidence_refs") or []))) for a in d["audit_signals"]] + [""]
    strings_section(out, "Avisos", d.get("warnings"))
    return "\n".join(out)


def render_owner_questions(d, state=None):
    out = header("Cuestionario para el dueño", d, "owner-questions.json")
    out += ["Responde debajo de cada pregunta (o en `owner-answers.md`, una entrada por `OWN-xxx`). Las de prioridad alta bloquean entender el alcance real.", ""]
    names = {}
    for f in (state or {}).get("feature_states") or []:
        if f.get("feature_id"):
            names[f["feature_id"]] = f.get("name", "")
    groups = {}
    for q in d.get("questions") or []:
        key = ", ".join(q.get("feature_ids") or []) or "General"
        groups.setdefault(key, []).append(q)
    for key in sorted(groups):
        label = key if key == "General" else ", ".join("%s%s" % (fid, (" %s" % names[fid]) if fid in names else "") for fid in key.split(", "))
        out += ["## %s" % label, ""]
        for q in sorted(groups[key], key=lambda q: ({"high": 0, "medium": 1, "low": 2}.get(q.get("priority"), 3), q.get("id", ""))):
            status = " _(respondida)_" if q.get("status") == "answered" else ""
            out += ["### %s (prioridad %s)%s" % (q.get("id"), PRIORITY.get(q.get("priority"), q.get("priority")), status), "", q.get("question", "")]
            if q.get("choices"):
                out += [""] + ["- [ ] %s" % c for c in q["choices"]]
            if q.get("source_gap_ids"):
                out += ["", "_Origen: %s_" % ", ".join(q["source_gap_ids"])]
            out += ["", "**Respuesta:**", "", "> ", ""]
    return "\n".join(out)


RENDERERS = [
    ("code-inventory", render_code_inventory),
    ("behavior-map", render_behavior_map),
    ("state-report", render_state_report),
    ("owner-questions", None),
]


def run(folder, only=None):
    written, problems = [], []
    state = None
    sp = folder / "state-report.json"
    if sp.exists():
        try:
            state = json.loads(sp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append("state-report.json: %s" % e)
    for name, fn in RENDERERS:
        if only and name not in only:
            continue
        src = folder / ("%s.json" % name)
        if not src.exists():
            continue
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append("%s: %s" % (src.name, e))
            continue
        text = render_owner_questions(data, state) if name == "owner-questions" else fn(data)
        dst = folder / ("%s.md" % name)
        dst.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
        written.append(dst)
    return written, problems


def self_test():
    import tempfile

    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "code-inventory.json").write_text(json.dumps({"version": 2, "summary": {"primary_language": "js"}, "entry_points": [{"id": "ENTRY-001", "kind": "http_route", "path": "/a", "description": "x", "evidence": "a.js:1"}], "warnings": ["w"]}), encoding="utf-8")
        (folder / "behavior-map.json").write_text(json.dumps({"version": 1, "summary": {}, "capabilities": [{"id": "CAP-001", "name": "Alta", "implementation_status": "partial", "flow": ["p1"], "business_rules": [{"rule": "r", "evidence": "a.js:2"}], "evidence_refs": ["a.js:1"]}], "vocabulary": [{"term": "socio", "kind": "objeto"}], "data_entities": [{"id": "RENT-001", "name": "Socio", "fields": [{"name": "id", "type": "int", "used": False}]}]}), encoding="utf-8")
        (folder / "state-report.json").write_text(json.dumps({"version": 3, "summary": {"overall_state": "A medias."}, "feature_states": [{"feature_id": "FG-01", "name": "Socios", "state": "partial", "missing": ["x"], "capability_refs": ["CAP-001"]}], "gaps": [{"id": "GAP-001", "kind": "half_built", "status": "open", "description": "d", "evidence_refs": ["CAP-001"], "suggested_resolution": "s"}], "audit_signals": [{"signal": "sin tests", "evidence_refs": ["a.js"]}]}), encoding="utf-8")
        (folder / "owner-questions.json").write_text(json.dumps({"version": 1, "questions": [{"id": "OWN-001", "question": "¿La terminamos?", "status": "open", "feature_ids": ["FG-01"], "source_gap_ids": ["GAP-001"], "priority": "high", "expected_answer_type": "choice", "choices": ["si", "no"]}]}), encoding="utf-8")
        written, problems = run(folder)
        checks.append(("4 md", len(written) == 4 and not problems))
        inv = (folder / "code-inventory.md").read_text(encoding="utf-8")
        checks.append(("header version", "version 2" in inv and "ENTRY-001" in inv))
        bm = (folder / "behavior-map.md").read_text(encoding="utf-8")
        checks.append(("behavior md", "CAP-001" in bm and "(sin uso)" in bm and "A medias" in bm))
        sr = (folder / "state-report.md").read_text(encoding="utf-8")
        checks.append(("state md", "A medio construir" in sr and "FG-01" in sr and "sin tests" in sr))
        oq = (folder / "owner-questions.md").read_text(encoding="utf-8")
        checks.append(("questions md", "FG-01 Socios" in oq and "- [ ] si" in oq and "**Respuesta:**" in oq))
        w2, _ = run(folder, only=["state-report"])
        checks.append(("--solo", len(w2) == 1))
        checks.append(("determinista", (folder / "state-report.md").read_text(encoding="utf-8") == sr))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/recovery")
    ap.add_argument("--solo", nargs="*", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    if not folder.exists():
        print("error: no existe %s" % folder)
        return 1
    written, problems = run(folder, args.solo)
    for w in written:
        print("md: %s" % w)
    for p in problems:
        print("error: %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
