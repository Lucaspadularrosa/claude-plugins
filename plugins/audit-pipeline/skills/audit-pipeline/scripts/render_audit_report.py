#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista del reporte de auditoria: findings + verdicts -> audit-report.{json,md}.

El orquestador no redacta el reporte: lo hace este script cruzando
`findings-merged.json` (o los `findings-*.json` si no hubo consolidacion) con los
veredictos de `verdicts/<finding_id>.json` que escriben `finding-verifier` y
`verify_mechanical.py`. Asi el contenido completo de la auditoria nunca entra al
contexto del agente principal: el orquestador lee solo el `summary` que imprime este
script.

Reglas de consolidacion (las mismas que antes aplicaba el orquestador):
  confirmed    -> confirmed_findings, con severidad ajustada si el veredicto la trae
  refuted      -> refuted_findings (con la razon, por transparencia)
  needs_human  -> needs_human con la pregunta exacta
  low          -> low_unverified (no se verifican)
  high/medium sin veredicto -> warnings (no entran como confirmados)

Mismo input -> mismo output. `created_at` sale de los metadatos, nunca del reloj.
Solo stdlib, Python 3.8+.

Uso:
  python render_audit_report.py [carpeta-audit] --run-id AUD-001 [--scope "todo"] [--pipeline-version X.Y.Z]
  python render_audit_report.py --self-test

Salida: escribe audit-report.json y audit-report.md e imprime el summary en una
linea (y en JSON con --json). Exit 1 ante JSON invalido o si faltan los findings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
DIMENSION_LABEL = {"bugs": "Bugs", "security": "Seguridad", "improvements": "Mejoras"}
DIMENSION_FILES = [("bugs", "findings-bugs.json"), ("security", "findings-security.json"), ("improvements", "findings-improvements.json")]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_findings(folder):
    merged = folder / "findings-merged.json"
    if merged.exists():
        data = load_json(merged)
        return list(data.get("findings") or []), data.get("metadata") or {}, list(data.get("warnings") or []), True
    findings, meta, warnings = [], {}, []
    for dim, name in DIMENSION_FILES:
        p = folder / name
        if not p.exists():
            continue
        data = load_json(p)
        meta = meta or dict(data.get("metadata") or {})
        for f in data.get("findings") or []:
            f = dict(f)
            f["dimension"] = dim
            findings.append(f)
        warnings.extend(data.get("warnings") or [])
    return findings, meta, warnings, False


def load_verdicts(folder):
    out = {}
    vdir = folder / "verdicts"
    if not vdir.exists():
        return out
    for p in sorted(vdir.glob("*.json")):
        v = load_json(p)
        fid = v.get("finding_id") or p.stem
        out[fid] = v
    return out


def dimension_of(f):
    if f.get("dimension"):
        return f["dimension"]
    prefix = str(f.get("id", "")).split("-")[0]
    return {"BUG": "bugs", "SEC": "security", "IMP": "improvements"}.get(prefix, "other")


def consolidate(folder, run_id, scope, pipeline_version, previous_version):
    findings, meta, warnings, merged_used = load_findings(folder)
    verdicts = load_verdicts(folder)
    confirmed, needs_human, refuted, low = [], [], [], []
    dims = set()
    for f in findings:
        dims.add(dimension_of(f))
        sev = f.get("severity")
        if sev == "low":
            low.append(f)
            continue
        v = verdicts.get(f["id"])
        if v is None:
            warnings.append("%s (%s) quedo sin veredicto: no entra como confirmado." % (f["id"], sev))
            continue
        verdict = v.get("verdict")
        if verdict == "confirmed":
            entry = {"finding": f, "verification": v}
            if v.get("adjusted_severity"):
                entry["finding"] = dict(f, severity=v["adjusted_severity"], original_severity=sev)
            confirmed.append(entry)
        elif verdict == "needs_human":
            needs_human.append({"finding": f, "question": v.get("question_for_human") or "", "verification": v})
        else:
            refuted.append({"finding_id": f["id"], "title": f.get("title"), "dimension": dimension_of(f),
                            "refutation_basis": v.get("refutation_basis"), "reasoning": v.get("reasoning", "")})
    confirmed.sort(key=lambda e: (SEVERITY_ORDER.get(e["finding"].get("severity"), 9), dimension_of(e["finding"]), e["finding"]["id"]))
    needs_human.sort(key=lambda e: e["finding"]["id"])
    refuted.sort(key=lambda e: e["finding_id"])
    low.sort(key=lambda f: f["id"])
    counts = {"high": 0, "medium": 0, "low_unverified": len(low)}
    for e in confirmed:
        s = e["finding"].get("severity")
        if s in counts:
            counts[s] += 1
    report = {
        "version": previous_version + 1,
        "metadata": {
            "created_at": meta.get("created_at"),
            "run_id": run_id,
            "scope": scope or meta.get("scope"),
            "dimensions": sorted(dims),
            "baseline_available": (Path(folder).parent / "requirements" / "requirements.json").exists(),
            "pipeline_version": pipeline_version or meta.get("pipeline_version"),
            "consolidated_by": "render_audit_report",
            "dedupe_applied": merged_used,
        },
        "summary": {"confirmed": counts, "refuted": len(refuted), "needs_human": len(needs_human)},
        "confirmed_findings": confirmed,
        "needs_human": needs_human,
        "refuted_findings": refuted,
        "low_unverified": low,
        "warnings": warnings,
    }
    return report


def md_finding(e):
    f = e["finding"]
    v = e.get("verification") or {}
    out = ["### %s — %s (`%s`, %s)" % (f["id"], f.get("title", ""), f.get("severity"), DIMENSION_LABEL.get(dimension_of(f), dimension_of(f))), ""]
    if f.get("original_severity") and f.get("original_severity") != f.get("severity"):
        out.append("_Severidad ajustada por el verificador: %s -> %s._" % (f["original_severity"], f["severity"]))
        out.append("")
    if f.get("description"):
        out += [f["description"], ""]
    for label, key in (("Escenario de falla", "failure_scenario"), ("Vector", "attack_vector"), ("Impacto", "impact"), ("Retorno", "payoff")):
        if f.get(key):
            out += ["- **%s**: %s" % (label, f[key])]
    if f.get("evidence_refs"):
        out.append("- **Evidencia**: " + ", ".join("`%s`" % r for r in f["evidence_refs"]))
    if f.get("merged_ids"):
        out.append("- **Absorbe**: " + ", ".join(f["merged_ids"]))
    if f.get("related_requirement_ids"):
        out.append("- **Requisitos**: " + ", ".join(f["related_requirement_ids"]))
    if v.get("reasoning"):
        out.append("- **Veredicto**: %s" % v["reasoning"])
    fix = f.get("proposed_fix") or f.get("proposed_change")
    if fix:
        out.append("- **Fix propuesto**: %s" % fix)
    out.append("")
    return out


def render_md(report):
    m = report["metadata"]
    s = report["summary"]
    out = ["# Reporte de auditoria %s" % m.get("run_id", ""), "",
           "> Derivado de `findings-*.json` + `verdicts/` por `render_audit_report.py` — no editar a mano. Version %d." % report["version"], "",
           "- **Alcance**: %s" % (m.get("scope") or "todo el repo"),
           "- **Dimensiones**: %s" % ", ".join(DIMENSION_LABEL.get(d, d) for d in m.get("dimensions", [])),
           "- **Linea de base disponible**: %s" % ("si" if m.get("baseline_available") else "no"),
           "", "## Resumen ejecutivo", "",
           "| Confirmados high | Confirmados medium | Low sin verificar | Descartados | Necesitan respuesta |",
           "|---|---|---|---|---|",
           "| %d | %d | %d | %d | %d |" % (s["confirmed"]["high"], s["confirmed"]["medium"], s["confirmed"]["low_unverified"], s["refuted"], s["needs_human"]), ""]
    by_dim = {}
    for e in report["confirmed_findings"]:
        d = dimension_of(e["finding"])
        by_dim.setdefault(d, {"high": 0, "medium": 0})
        sev = e["finding"].get("severity")
        if sev in by_dim[d]:
            by_dim[d][sev] += 1
    if by_dim:
        out += ["| Dimension | high | medium |", "|---|---|---|"]
        for d in sorted(by_dim):
            out.append("| %s | %d | %d |" % (DIMENSION_LABEL.get(d, d), by_dim[d]["high"], by_dim[d]["medium"]))
        out.append("")
    out += ["## Hallazgos confirmados", ""]
    if not report["confirmed_findings"]:
        out += ["Ninguno.", ""]
    for e in report["confirmed_findings"]:
        out += md_finding(e)
    if report["needs_human"]:
        out += ["## Necesitan tu respuesta", ""]
        for e in report["needs_human"]:
            f = e["finding"]
            out += ["- **%s** — %s: %s" % (f["id"], f.get("title", ""), e.get("question") or "(sin pregunta)")]
        out.append("")
    if report["refuted_findings"]:
        out += ["## Descartados por el verificador", ""]
        for r in report["refuted_findings"]:
            out += ["- **%s** — %s (`%s`): %s" % (r["finding_id"], r.get("title") or "", r.get("refutation_basis"), r.get("reasoning", ""))]
        out.append("")
    if report["low_unverified"]:
        out += ["## Low (sin verificar)", ""]
        for f in report["low_unverified"]:
            out += ["- **%s** — %s (%s)" % (f["id"], f.get("title", ""), ", ".join("`%s`" % r for r in f.get("evidence_refs") or []))]
        out.append("")
    if report["warnings"]:
        out += ["## Avisos", ""] + ["- %s" % w for w in report["warnings"]] + [""]
    return "\n".join(out)


def self_test():
    import tempfile

    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / ".dev" / "audit"
        (folder / "verdicts").mkdir(parents=True)
        (folder / "findings-merged.json").write_text(json.dumps({
            "metadata": {"created_at": "2026-02-02", "scope": "src/", "pipeline_version": "1.3.0"},
            "findings": [
                {"id": "BUG-001", "dimension": "bugs", "severity": "high", "title": "roto", "evidence_refs": ["a.js:1"], "proposed_fix": "arreglar"},
                {"id": "SEC-001", "dimension": "security", "severity": "medium", "title": "idor", "evidence_refs": ["b.js:2"]},
                {"id": "SEC-002", "dimension": "security", "severity": "medium", "title": "duda", "evidence_refs": ["c.js:3"]},
                {"id": "IMP-001", "dimension": "improvements", "severity": "low", "title": "tests", "evidence_refs": ["d.js:4"]},
                {"id": "IMP-002", "dimension": "improvements", "severity": "high", "title": "sin veredicto", "evidence_refs": ["e.js:5"]},
            ], "warnings": []}), encoding="utf-8")
        (folder / "verdicts" / "BUG-001.json").write_text(json.dumps({"finding_id": "BUG-001", "verdict": "confirmed", "adjusted_severity": "medium", "reasoning": "leido a.js:1"}), encoding="utf-8")
        (folder / "verdicts" / "SEC-001.json").write_text(json.dumps({"finding_id": "SEC-001", "verdict": "refuted", "refutation_basis": "guard_upstream", "reasoning": "hay middleware"}), encoding="utf-8")
        (folder / "verdicts" / "SEC-002.json").write_text(json.dumps({"finding_id": "SEC-002", "verdict": "needs_human", "question_for_human": "¿el rol X puede?"}), encoding="utf-8")
        rep = consolidate(folder, "AUD-001", None, None, 0)
        s = rep["summary"]
        checks.append(("confirmado con severidad ajustada", s["confirmed"] == {"high": 0, "medium": 1, "low_unverified": 1}))
        checks.append(("refutado", s["refuted"] == 1 and rep["refuted_findings"][0]["refutation_basis"] == "guard_upstream"))
        checks.append(("needs_human", s["needs_human"] == 1 and "rol" in rep["needs_human"][0]["question"]))
        checks.append(("sin veredicto -> warning", any("IMP-002" in w for w in rep["warnings"])))
        checks.append(("scope y version desde metadata", rep["metadata"]["scope"] == "src/" and rep["metadata"]["pipeline_version"] == "1.3.0"))
        checks.append(("version +1", rep["version"] == 1))
        md = render_md(rep)
        checks.append(("md con secciones", "## Hallazgos confirmados" in md and "## Descartados" in md and "BUG-001" in md))
        checks.append(("determinista", render_md(consolidate(folder, "AUD-001", None, None, 0)) == md))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/audit")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--scope", default=None)
    ap.add_argument("--pipeline-version", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    if not folder.exists():
        print("error: no existe %s" % folder)
        return 1
    prev = folder / "audit-report.json"
    previous_version = 0
    run_id = args.run_id
    if prev.exists():
        try:
            prev_data = load_json(prev)
            previous_version = int(prev_data.get("version") or 0)
            if not run_id:
                last = str((prev_data.get("metadata") or {}).get("run_id") or "AUD-000")
                run_id = "AUD-%03d" % (int(last.split("-")[-1]) + 1)
        except (json.JSONDecodeError, ValueError, OSError):
            previous_version = 0
    run_id = run_id or "AUD-001"
    try:
        report = consolidate(folder, run_id, args.scope, args.pipeline_version, previous_version)
    except (json.JSONDecodeError, OSError) as e:
        print("error: %s" % e)
        return 1
    if not report["confirmed_findings"] and not report["low_unverified"] and not report["refuted_findings"] and not report["needs_human"] and not (folder / "findings-merged.json").exists():
        print("error: no hay findings en %s" % folder)
        return 1
    (folder / "audit-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "audit-report.md").write_text(render_md(report), encoding="utf-8")
    s = report["summary"]
    print("%s: confirmados high %d / medium %d, low sin verificar %d, descartados %d, necesitan respuesta %d, avisos %d -> %s" % (
        run_id, s["confirmed"]["high"], s["confirmed"]["medium"], s["confirmed"]["low_unverified"], s["refuted"], s["needs_human"], len(report["warnings"]), folder / "audit-report.md"))
    if args.json:
        print(json.dumps({"run_id": run_id, "version": report["version"], "summary": s, "warnings": report["warnings"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
