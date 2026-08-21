#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cosechador determinista de metricas de la suite: .dev/* + git -> metrics.json/.html.

Cero tokens de modelo: los pipelines NO instrumentan nada — sus artefactos ya son el
log de eventos (todos llevan summary y pipeline_version). Este script los cosecha a
demanda, de forma defensiva (ningun campo es obligatorio: lo que falta se omite y se
avisa) y retroactiva (funciona sobre cualquier proyecto que ya uso la suite).

Que cosecha (si existe):
  .dev/requirements/   linea de base (conteos), inspecciones (defectos por severidad),
                       changelog (corridas por tipo/estado, churn de la baseline:
                       CRs aplicados sobre features ya baselineadas y a cuantos dias)
  .dev/plan/           tareas, lotes y paralelismo, inspeccion del plan
  .dev/build/          reviews y gates por feature (hallazgos, tests/lint,
                       audit de dependencias, rondas aproximadas por version)
  .dev/recovery/       spot-check de evidencia (tasa de refutados), estado, preguntas
  .dev/audit/          hallazgos por dimension y reporte (señal/ruido si esta)
  git                  commits [T-xxx], merges, rango de fechas

Determinista: mismo repo -> mismo output. Sin reloj: `generated_from` es la fecha
mas nueva vista en los artefactos. Solo stdlib, Python 3.8+. Solo lectura sobre
.dev/ y git; escribe unicamente en .dev/metrics/.

Uso:
  python metrics_harvest.py [raiz-del-proyecto] [--salida DIR] [--export ARCHIVO.jsonl]
  python metrics_harvest.py --self-test

  --salida   por defecto <raiz>/.dev/metrics/ (metrics.json + metrics.html)
  --export   apendea el registro compacto del proyecto a un JSONL central (para
             comparar versiones del plugin entre proyectos)

Exit 1 solo ante errores de IO o self-test fallido.
"""

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)


def load(path):
    """JSON o None (avisando); nunca explota."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warn("ilegible %s: %s" % (p.name, exc))
        return None


def g(doc, *keys, default=None):
    """Acceso anidado defensivo: g(doc, 'summary', 'total')."""
    cur = doc
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def rate(num, den):
    return round(num / den, 3) if isinstance(num, (int, float)) and den else None


def parse_date(s):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


DATES_SEEN = []
VERSIONS_SEEN = {}


def note_meta(doc, pipeline):
    if not isinstance(doc, dict):
        return
    for key in ("updated_at", "created_at", "date"):
        d = parse_date(g(doc, "metadata", key) or doc.get(key))
        if d:
            DATES_SEEN.append(d)
    pv = g(doc, "metadata", "pipeline_version") or doc.get("pipeline_version")
    if pv and pipeline:
        VERSIONS_SEEN.setdefault(pipeline, set()).add(str(pv))


# ------------------------------------------------------------------ secciones


def harvest_requirements(dev):
    req = dev / "requirements"
    if not req.is_dir():
        return None
    out = {}

    counts = {}
    for name, doc_keys in (("lel.json", ("symbols",)), ("scenarios.json", ("scenarios",)),
                           ("requirements.json", ("requirements", "functional_requirements")),
                           ("product-map.json", ("features",))):
        doc = load(req / name)
        note_meta(doc, "requerimientos")
        if doc is None:
            continue
        items = None
        for key in doc_keys:
            if isinstance(doc.get(key), list):
                items = doc[key]
                break
        if items is None:
            continue
        label = name.replace(".json", "")
        counts[label] = {"total": len(items)}
        statuses = {}
        for it in items:
            st = it.get("status") if isinstance(it, dict) else None
            if st:
                statuses[st] = statuses.get(st, 0) + 1
        if statuses:
            counts[label]["by_status"] = dict(sorted(statuses.items()))
        if label == "requirements":
            recovered = sum(1 for it in items
                            if isinstance(it, dict) and it.get("origin") == "recovered")
            if recovered:
                counts[label]["recovered"] = recovered
    if counts:
        out["baseline"] = counts

    inspections = {}
    for name in ("lel-inspection", "requirements-inspection", "design-inspection"):
        doc = load(req / (name + ".json"))
        note_meta(doc, "requerimientos")
        if doc is not None and isinstance(doc.get("summary"), dict):
            inspections[name] = doc["summary"]
    if inspections:
        out["inspections"] = inspections

    changelog = load(req / "changelog.json")
    note_meta(changelog, None)
    entries = changelog.get("entries") if isinstance(changelog, dict) else None
    if isinstance(entries, list):
        by_kind, by_status = {}, {}
        first_baseline = {}   # feature_id -> fecha del primer increment/recovery aplicado
        churn = []
        for e in sorted((x for x in entries if isinstance(x, dict)),
                        key=lambda x: str(x.get("date", ""))):
            by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
            by_status[e.get("status", "?")] = by_status.get(e.get("status", "?"), 0) + 1
            d = parse_date(e.get("date"))
            if d:
                DATES_SEEN.append(d)
            if e.get("status") != "applied":
                continue
            fids = e.get("feature_ids") or []
            if e.get("kind") in ("increment", "recovery"):
                for f in fids:
                    first_baseline.setdefault(f, d)
            elif e.get("kind") == "change_request":
                touched = [f for f in fids if f in first_baseline]
                if touched:
                    days = None
                    if d and all(first_baseline[f] for f in touched):
                        days = min((d - first_baseline[f]).days for f in touched)
                    churn.append({"id": e.get("id"), "feature_ids": touched,
                                  "days_after_baseline": days})
        out["changelog"] = {"entries": len(entries), "by_kind": by_kind,
                            "by_status": by_status}
        if first_baseline:
            out["changelog"]["baseline_churn"] = {
                "features_baselined": len(first_baseline),
                "crs_on_baselined": len(churn),
                "churn_rate": rate(len(churn), len(first_baseline)),
                "detail": churn,
            }
    return out or None


def harvest_planning(dev):
    plan = dev / "plan"
    if not plan.is_dir():
        return None
    out = {}
    tasks = load(plan / "tasks.json")
    note_meta(tasks, "planning")
    task_list = g(tasks, "tasks") if isinstance(g(tasks, "tasks"), list) else None
    if task_list is not None:
        out["tasks"] = {"total": len(task_list)}
    ep = load(plan / "execution-plan.json")
    note_meta(ep, "planning")
    batches = g(ep, "batches")
    if isinstance(batches, list):
        sizes = [len(b.get("feature_ids", b.get("features", [])) or [])
                 for b in batches if isinstance(b, dict)]
        out["execution"] = {"batches": len(batches), "max_parallelism": max(sizes or [0])}
    insp = load(plan / "plan-inspection.json")
    note_meta(insp, "planning")
    if insp is not None and isinstance(insp.get("summary"), dict):
        out["inspection"] = insp["summary"]
    progress = load(plan / "progress.json")
    note_meta(progress, "build")
    feats = g(progress, "features")
    if isinstance(feats, list):
        by_status = {}
        for f in feats:
            st = f.get("status", "?") if isinstance(f, dict) else "?"
            by_status[st] = by_status.get(st, 0) + 1
        out["progress"] = {"features": len(feats), "by_status": by_status}
    elif isinstance(feats, dict):
        out["progress"] = {"features": len(feats)}
    return out or None


def _verdict_folder(folder, pipeline):
    """Agrega los veredictos por feature de reviews/ o security/."""
    if not folder.is_dir():
        return None
    total = high = 0
    passed_flags = {"tests_passed": [0, 0], "lint_passed": [0, 0],
                    "dependency_audit_passed": [0, 0]}
    rounds = []
    n = 0
    for f in sorted(folder.glob("*.json")):
        doc = load(f)
        note_meta(doc, pipeline)
        if doc is None:
            continue
        n += 1
        s = doc.get("summary") or {}
        total += s.get("total_findings") or 0
        high += s.get("high") or 0
        for key, acc in passed_flags.items():
            if isinstance(s.get(key), bool):
                acc[1] += 1
                acc[0] += 1 if s[key] else 0
        if isinstance(doc.get("version"), int):
            rounds.append(doc["version"])
    if not n:
        return None
    out = {"features": n, "findings_total": total, "findings_high": high,
           "findings_per_feature": rate(total, n)}
    for key, (ok, seen) in passed_flags.items():
        if seen:
            out[key.replace("_passed", "_pass_rate")] = rate(ok, seen)
    if rounds:
        # version del JSON como proxy de rondas de correccion (1 = a la primera)
        out["avg_rounds_proxy"] = round(sum(rounds) / len(rounds), 2)
    return out


def harvest_build(dev):
    build = dev / "build"
    if not build.is_dir():
        return None
    out = {}
    reviews = _verdict_folder(build / "reviews", "build")
    if reviews:
        out["reviews"] = reviews
    gates = _verdict_folder(build / "security", "build")
    if gates:
        out["security_gates"] = gates
    debt = build / "tech-debt.md"
    if debt.is_file():
        out["tech_debt_entries"] = len(re.findall(r"^- ", debt.read_text(encoding="utf-8"),
                                                  re.MULTILINE))
    return out or None


def harvest_recovery(dev):
    rec = dev / "recovery"
    if not rec.is_dir():
        return None
    out = {}
    ev = load(rec / "evidence-check.json")
    note_meta(ev, "recovery")
    s = g(ev, "summary")
    if isinstance(s, dict):
        checks = s.get("checks")
        out["evidence_check"] = dict(s)
        out["evidence_check"]["refuted_rate"] = rate(s.get("refuted"), checks)
        out["evidence_check"]["confirmed_rate"] = rate(s.get("confirmed"), checks)
    st = load(rec / "state-report.json")
    note_meta(st, "recovery")
    if isinstance(g(st, "summary"), dict):
        out["state"] = g(st, "summary")
    qs = load(rec / "owner-questions.json")
    note_meta(qs, "recovery")
    qlist = g(qs, "questions")
    if isinstance(qlist, list):
        answered = sum(1 for q in qlist
                       if isinstance(q, dict) and q.get("status") == "answered")
        out["owner_questions"] = {"total": len(qlist), "answered": answered,
                                  "answer_rate": rate(answered, len(qlist))}
    return out or None


def harvest_audit(dev):
    aud = dev / "audit"
    if not aud.is_dir():
        return None
    out = {}
    dims = {}
    for name in ("findings-bugs", "findings-security", "findings-improvements"):
        doc = load(aud / (name + ".json"))
        note_meta(doc, "audit")
        if doc is not None and isinstance(doc.get("summary"), dict):
            dims[name.replace("findings-", "")] = doc["summary"]
    if dims:
        out["dimensions"] = dims
    report = load(aud / "audit-report.json")
    note_meta(report, "audit")
    if isinstance(g(report, "summary"), dict):
        out["report"] = g(report, "summary")
        proposed = sum(s.get("total") or 0 for s in dims.values())
        confirmed = None
        for key in ("confirmed", "confirmed_findings", "total_confirmed"):
            if isinstance(g(report, "summary", key), int):
                confirmed = g(report, "summary", key)
                break
        if confirmed is not None and proposed:
            out["signal_ratio"] = rate(confirmed, proposed)
    if (aud / "history").is_dir():
        out["runs"] = len([d for d in (aud / "history").iterdir() if d.is_dir()])
    return out or None


def harvest_git(root):
    def git(*args):
        try:
            r = subprocess.run(["git", "-C", str(root)] + list(args),
                               capture_output=True, text=True, timeout=30)
            return r.stdout.strip() if r.returncode == 0 else None
        except OSError:
            return None

    if git("rev-parse", "--is-inside-work-tree") != "true":
        return None
    out = {}
    task_commits = git("log", "--oneline", "--grep", r"\[T-[0-9]")
    if task_commits is not None:
        out["task_commits"] = len([l for l in task_commits.splitlines() if l])
    merges = git("rev-list", "--count", "--merges", "HEAD")
    if merges and merges.isdigit():
        out["merges"] = int(merges)
    for label, args in (("first_commit", ["log", "--reverse", "--format=%as", "-1"]),
                        ("last_commit", ["log", "--format=%as", "-1"])):
        v = git(*args)
        if v:
            out[label] = v.splitlines()[0]
            d = parse_date(out[label])
            if d:
                DATES_SEEN.append(d)
    return out or None


# --------------------------------------------------------------------- salida


def collect(root):
    DATES_SEEN.clear()
    VERSIONS_SEEN.clear()
    del WARNINGS[:]
    root = Path(root)
    dev = root / ".dev"
    metrics = {"version": 1, "project": root.resolve().name}
    sections = {"requirements": harvest_requirements(dev),
                "planning": harvest_planning(dev),
                "build": harvest_build(dev),
                "recovery": harvest_recovery(dev),
                "audit": harvest_audit(dev),
                "git": harvest_git(root)}
    for name, data in sections.items():
        if data:
            metrics[name] = data
    metrics["pipeline_versions"] = {k: sorted(v) for k, v in sorted(VERSIONS_SEEN.items())}
    metrics["generated_from"] = max(DATES_SEEN).isoformat() if DATES_SEEN else None
    if WARNINGS:
        metrics["warnings"] = list(WARNINGS)
    return metrics


def headline(metrics):
    """El registro compacto para --export: lo comparable entre proyectos."""
    return {
        "project": metrics.get("project"),
        "generated_from": metrics.get("generated_from"),
        "pipeline_versions": metrics.get("pipeline_versions"),
        "refuted_rate": g(metrics, "recovery", "evidence_check", "refuted_rate"),
        "review_findings_per_feature": g(metrics, "build", "reviews", "findings_per_feature"),
        "review_avg_rounds": g(metrics, "build", "reviews", "avg_rounds_proxy"),
        "gate_findings_per_feature": g(metrics, "build", "security_gates", "findings_per_feature"),
        "audit_signal_ratio": g(metrics, "audit", "signal_ratio"),
        "baseline_churn_rate": g(metrics, "requirements", "changelog", "baseline_churn", "churn_rate"),
        "inspection_defects": sum(
            s.get("total_defects") or 0
            for s in (g(metrics, "requirements", "inspections") or {}).values()),
    }


CSS = ("body{margin:0;background:#f6f7f9;color:#1f2430;font:15px/1.5 -apple-system,"
       '"Segoe UI",Roboto,sans-serif}main{max-width:56rem;margin:0 auto;'
       "padding:2rem 1.25rem}h1{font-size:1.4rem}h2{font-size:1.05rem;margin:1.8rem 0 .5rem;"
       "border-bottom:1px solid #e3e6eb;padding-bottom:.3rem}.wrap{overflow-x:auto;"
       "background:#fff;border:1px solid #e3e6eb;border-radius:8px}table{border-collapse:"
       "collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:.4rem .7rem;"
       "border-top:1px solid #e3e6eb}thead th{border-top:0;color:#5b6472;font-size:.75rem;"
       "text-transform:uppercase}footer{margin-top:2.5rem;color:#5b6472;font-size:.8rem}")


def _rows(d, prefix=""):
    rows = []
    for k, v in d.items():
        if isinstance(v, dict):
            rows += _rows(v, prefix + k + ".")
        elif isinstance(v, list):
            rows.append((prefix + k, "%d items" % len(v)))
        else:
            rows.append((prefix + k, v))
    return rows


def render_html(metrics):
    parts = ["<!doctype html>", '<html lang="es"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>Metricas de la suite</title>",
             "<style>%s</style></head><body><main>" % CSS,
             "<h1>Metricas — %s</h1>" % html.escape(str(metrics.get("project", "")))]
    if metrics.get("generated_from"):
        parts.append('<p>Datos al %s (fecha mas nueva vista en los artefactos).</p>'
                     % html.escape(metrics["generated_from"]))
    for section in ("requirements", "planning", "build", "recovery", "audit", "git",
                    "pipeline_versions"):
        data = metrics.get(section)
        if not data:
            continue
        rows = "".join("<tr><td>%s</td><td>%s</td></tr>"
                       % (html.escape(str(k)), html.escape(str(v)))
                       for k, v in _rows(data))
        parts.append("<h2>%s</h2>" % section)
        parts.append('<div class="wrap"><table><thead><tr><th>Metrica</th>'
                     "<th>Valor</th></tr></thead><tbody>%s</tbody></table></div>" % rows)
    for w in metrics.get("warnings", []):
        parts.append("<p><small>aviso: %s</small></p>" % html.escape(str(w)))
    parts.append("<footer>Cosecha determinista de los artefactos de la suite. "
                 "Cero tokens de modelo.</footer></main></body></html>")
    return "\n".join(parts)


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = root / ".dev" / "requirements"
        rec = root / ".dev" / "recovery"
        rev = root / ".dev" / "build" / "reviews"
        for d in (req, rec, rev):
            d.mkdir(parents=True)
        (req / "changelog.json").write_text(json.dumps({"entries": [
            {"id": "REC-001", "kind": "recovery", "date": "2026-01-10",
             "status": "applied", "feature_ids": ["FG-01", "FG-02"]},
            {"id": "CR-001", "kind": "change_request", "date": "2026-02-09",
             "status": "applied", "feature_ids": ["FG-01"]},
            {"id": "CR-002", "kind": "change_request", "date": "2026-02-11",
             "status": "rejected", "feature_ids": ["FG-02"]}]}))
        (req / "lel.json").write_text(json.dumps(
            {"metadata": {"pipeline_version": "2.4.0"},
             "symbols": [{"id": "SYM-1"}, {"id": "SYM-2"}]}))
        (rec / "evidence-check.json").write_text(json.dumps(
            {"metadata": {"pipeline_version": "2.0.0", "updated_at": "2026-03-01"},
             "summary": {"sampled_capabilities": 5, "checks": 10, "confirmed": 8,
                         "imprecise": 1, "refuted": 1}}))
        (rev / "fg-01.json").write_text(json.dumps(
            {"version": 2, "pipeline_version": "1.5.0",
             "summary": {"total_findings": 3, "high": 1, "tests_passed": True,
                         "lint_passed": False}}))
        (rev / "bad.json").write_text("{no es json")
        m = collect(root)
        hl = headline(m)
        page = render_html(m)
        checks = [
            g(m, "requirements", "baseline", "lel", "total") == 2,
            g(m, "requirements", "changelog", "baseline_churn", "features_baselined") == 2,
            g(m, "requirements", "changelog", "baseline_churn", "crs_on_baselined") == 1,
            g(m, "requirements", "changelog", "baseline_churn", "detail")[0]["days_after_baseline"] == 30,
            g(m, "recovery", "evidence_check", "refuted_rate") == 0.1,
            g(m, "build", "reviews", "features") == 1,
            g(m, "build", "reviews", "avg_rounds_proxy") == 2.0,
            m.get("generated_from") == "2026-03-01",          # sin reloj
            "2.0.0" in (m["pipeline_versions"].get("recovery") or []),
            any("bad.json" in w for w in m.get("warnings", [])),  # defensivo
            hl["refuted_rate"] == 0.1 and hl["baseline_churn_rate"] == 0.5,
            "&lt;" not in page or "<script>" not in page,
            collect(root) == m,                                # determinista
        ]
        empty = collect(root / "nada")
        checks.append("requirements" not in empty)             # degradacion
    if not all(checks):
        print("self-test FALLO: %s" % checks)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--export", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        sys.exit(self_test())

    metrics = collect(args.raiz)
    out_dir = Path(args.salida) if args.salida else Path(args.raiz) / ".dev" / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "metrics.html").write_text(render_html(metrics), encoding="utf-8")
    print(str(out_dir / "metrics.json"))
    print(str(out_dir / "metrics.html"))
    if args.export:
        exp = Path(args.export)
        exp.parent.mkdir(parents=True, exist_ok=True)
        with open(str(exp), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(headline(metrics), ensure_ascii=False) + "\n")
        print("export -> %s" % exp)
    for w in WARNINGS:
        print("aviso: %s" % w)


if __name__ == "__main__":
    main()
