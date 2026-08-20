#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista del reporte de estado: state-report.json -> state-report.html.

Toma el diagnostico que escribe gap-analysis (y el cuestionario del dueño si existe)
y lo convierte en una pagina HTML autocontenida, pensada para compartir: el dueño se
la manda a un socio o stakeholder sin abrir un editor ni conocer la suite.
Mismo input -> misma pagina; sin tokens de modelo, sin red, sin dependencias.

Seguridad por construccion: TODO el texto crudo se escapa (html.escape) antes de
entrar al HTML. La pagina no referencia ningun recurso externo (CSS inline, sin
imagenes, sin scripts). Las fechas salen de los metadatos del JSON, nunca del reloj:
el render es reproducible.

La pagina se degrada sola: una seccion sin datos no se emite. Una app sin pantallas,
sin huecos o sin preguntas genera un reporte igual de valido, solo mas corto.

Solo stdlib, Python 3.8+. No modifica los JSON.

Uso:
  python render_state_report.py [carpeta-recovery] [--salida ARCHIVO] [--titulo "Nombre"]
  python render_state_report.py --self-test

  carpeta-recovery  por defecto .dev/recovery (donde escribe gap-analysis); debe
                    contener state-report.json; owner-questions.json es opcional
  --salida          por defecto <carpeta-recovery>/state-report.html

Salida: la ruta generada. Exit 1 ante errores de IO/JSON o self-test fallido.
"""

import argparse
import html
import json
import sys
from pathlib import Path

STATE_LABELS = {
    "complete": ("Completa", "ok"),
    "partial": ("A medias", "warn"),
    "skeleton": ("Esqueleto", "bad"),
}

GAP_KIND_LABELS = {
    "half_built": "A medio construir",
    "loose_end": "Cabos sueltos",
    "inconsistency": "Incoherencias",
    "structural_absence": "Ausencias estructurales",
    "unconfirmed_decision": "Decisiones sin confirmar",
}

PRIORITY_LABELS = {"high": "Alta", "medium": "Media", "low": "Baja"}

CSS = """
:root { --ok:#0a7d55; --warn:#b45309; --bad:#b91c1c; --ink:#1f2430; --muted:#5b6472;
        --line:#e3e6eb; --bg:#f6f7f9; --card:#ffffff; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:16px/1.55 -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif; }
main { max-width:60rem; margin:0 auto; padding:2rem 1.25rem 4rem; }
h1 { font-size:1.6rem; margin:0 0 .25rem; }
h2 { font-size:1.15rem; margin:2.2rem 0 .8rem; border-bottom:1px solid var(--line);
     padding-bottom:.35rem; }
h3 { font-size:1rem; margin:1.2rem 0 .4rem; }
p { margin:.4rem 0; }
.sub { color:var(--muted); font-size:.9rem; }
.lead { font-size:1.05rem; background:var(--card); border:1px solid var(--line);
        border-radius:10px; padding:1rem 1.2rem; margin:1.2rem 0; }
.chips { display:flex; flex-wrap:wrap; gap:.5rem; margin:.8rem 0 0; padding:0;
         list-style:none; }
.chips li { background:var(--card); border:1px solid var(--line); border-radius:999px;
            padding:.25rem .8rem; font-size:.85rem; }
.chips b { font-variant-numeric:tabular-nums; }
.tablewrap { overflow-x:auto; background:var(--card); border:1px solid var(--line);
             border-radius:10px; }
table { border-collapse:collapse; width:100%; font-size:.92rem; }
th, td { text-align:left; padding:.55rem .8rem; border-top:1px solid var(--line);
         vertical-align:top; }
thead th { border-top:0; color:var(--muted); font-size:.8rem;
           text-transform:uppercase; letter-spacing:.04em; }
.badge { display:inline-block; border-radius:999px; padding:.1rem .6rem;
         font-size:.8rem; font-weight:600; color:#fff; white-space:nowrap; }
.badge.ok { background:var(--ok); } .badge.warn { background:var(--warn); }
.badge.bad { background:var(--bad); } .badge.mut { background:var(--muted); }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding: .8rem 1rem; margin:.6rem 0; }
.card .meta { color:var(--muted); font-size:.82rem; margin-top:.35rem; }
ul.plain { margin:.3rem 0 .3rem 1.1rem; padding:0; }
footer { margin-top:3rem; color:var(--muted); font-size:.82rem;
         border-top:1px solid var(--line); padding-top:.8rem; }
code { background:var(--bg); border:1px solid var(--line); border-radius:4px;
       padding:0 .3rem; font-size:.85em; }
"""


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def _state_badge(state):
    label, cls = STATE_LABELS.get(state, (state or "desconocido", "mut"))
    return '<span class="badge %s">%s</span>' % (cls, esc(label))


def _chip(label, value):
    return "<li>%s: <b>%s</b></li>" % (esc(label), esc(value))


def render_header(report, title):
    summary = report.get("summary", {})
    meta = report.get("metadata", {})
    out = ["<h1>%s</h1>" % esc(title)]
    when = meta.get("updated_at") or meta.get("created_at")
    if when:
        out.append('<p class="sub">Datos al %s · generado por el pipeline de '
                   "comprension (solo lectura sobre el codigo)</p>" % esc(when))
    if summary.get("overall_state"):
        out.append('<p class="lead">%s</p>' % esc(summary["overall_state"]))
    chips = []
    for key, label in (("features_complete", "Completas"),
                       ("features_partial", "A medias"),
                       ("features_skeleton", "Esqueleto"),
                       ("dead_code_findings", "Codigo muerto"),
                       ("gap_count", "Huecos"),
                       ("question_count", "Preguntas al dueño")):
        if key in summary:
            chips.append(_chip(label, summary[key]))
    if chips:
        out.append('<ul class="chips">%s</ul>' % "".join(chips))
    return out


def render_features(report):
    features = report.get("feature_states") or []
    if not features:
        return []
    rows = []
    for f in features:
        name = esc(f.get("name", ""))
        fid = f.get("feature_id")
        if fid:
            name += ' <span class="sub">(%s)</span>' % esc(fid)
        missing = f.get("missing") or []
        missing_html = ("<ul class='plain'>%s</ul>"
                        % "".join("<li>%s</li>" % esc(m) for m in missing)
                        if missing else "—")
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (name, _state_badge(f.get("state")), missing_html))
    return ["<h2>Features por estado</h2>",
            '<div class="tablewrap"><table><thead><tr>'
            "<th>Feature</th><th>Estado</th><th>Que falta</th>"
            "</tr></thead><tbody>%s</tbody></table></div>" % "".join(rows)]


def render_gaps(report):
    gaps = [g for g in (report.get("gaps") or [])]
    if not gaps:
        return []
    out = ["<h2>Huecos encontrados</h2>"]
    for kind in GAP_KIND_LABELS:
        of_kind = [g for g in gaps if g.get("kind") == kind]
        if not of_kind:
            continue
        out.append("<h3>%s</h3>" % esc(GAP_KIND_LABELS[kind]))
        for g in of_kind:
            status = ('<span class="badge mut">Resuelto</span> '
                      if g.get("status") == "resolved" else "")
            body = ["<p>%s<b>%s</b> — %s</p>"
                    % (status, esc(g.get("id", "")), esc(g.get("description", "")))]
            if g.get("suggested_resolution"):
                body.append("<p>Resolucion sugerida: %s</p>"
                            % esc(g["suggested_resolution"]))
            refs = g.get("evidence_refs") or []
            if refs:
                body.append('<p class="meta">Evidencia: %s</p>'
                            % " · ".join("<code>%s</code>" % esc(r) for r in refs))
            out.append('<div class="card">%s</div>' % "".join(body))
    unknown = [g for g in gaps if g.get("kind") not in GAP_KIND_LABELS]
    for g in unknown:
        out.append('<div class="card"><p><b>%s</b> — %s</p></div>'
                   % (esc(g.get("id", "")), esc(g.get("description", ""))))
    return out


def render_audit_signals(report):
    signals = report.get("audit_signals") or []
    if not signals:
        return []
    items = []
    for s in signals:
        refs = s.get("evidence_refs") or []
        refs_html = (' <span class="sub">(%s)</span>'
                     % " · ".join(esc(r) for r in refs) if refs else "")
        items.append("<li>%s%s</li>" % (esc(s.get("signal", "")), refs_html))
    return ["<h2>Señales para auditoria</h2>",
            '<p class="sub">Posibles bugs, seguridad o deuda: el punto de partida '
            "de una auditoria a fondo, no un veredicto.</p>",
            '<ul class="plain">%s</ul>' % "".join(items)]


def render_questions(questions_doc):
    questions = [q for q in ((questions_doc or {}).get("questions") or [])
                 if q.get("status") != "answered"]
    if not questions:
        return []
    out = ["<h2>Preguntas pendientes al dueño</h2>",
           '<p class="sub">Decisiones que el codigo tomo y nadie valido. '
           "Se responden sin leer una linea de codigo.</p>"]
    order = {"high": 0, "medium": 1, "low": 2}
    questions = sorted(questions, key=lambda q: (order.get(q.get("priority"), 3),
                                                 str(q.get("id", ""))))
    for q in questions:
        prio = PRIORITY_LABELS.get(q.get("priority"), q.get("priority", ""))
        body = ["<p><b>%s</b> <span class='badge %s'>%s</span></p>"
                % (esc(q.get("id", "")),
                   {"high": "bad", "medium": "warn"}.get(q.get("priority"), "mut"),
                   esc("Prioridad " + str(prio)) if prio else "")]
        body.append("<p>%s</p>" % esc(q.get("question", "")))
        choices = q.get("choices") or []
        if choices:
            body.append('<ul class="plain">%s</ul>'
                        % "".join("<li>%s</li>" % esc(c) for c in choices))
        out.append('<div class="card">%s</div>' % "".join(body))
    return out


def render_warnings(report):
    warnings = report.get("warnings") or []
    if not warnings:
        return []
    return ["<h2>Avisos</h2>",
            '<ul class="plain">%s</ul>'
            % "".join("<li>%s</li>" % esc(w) for w in warnings)]


def render(report, questions_doc, title):
    parts = ["<!doctype html>", '<html lang="es"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>%s</title>" % esc(title),
             "<style>%s</style></head><body><main>" % CSS]
    parts += render_header(report, title)
    parts += render_features(report)
    parts += render_gaps(report)
    parts += render_audit_signals(report)
    parts += render_questions(questions_doc)
    parts += render_warnings(report)
    version = report.get("pipeline_version") or report.get("metadata", {}).get("pipeline_version")
    footer = "Reporte de estado generado por recovery-pipeline"
    if version:
        footer += " v%s" % esc(version)
    footer += ". Toda afirmacion cita evidencia del codigo; nada es opinion."
    parts.append("<footer>%s</footer></main></body></html>" % footer)
    return "\n".join(parts)


def load_json(path):
    with open(str(path), encoding="utf-8") as fh:
        return json.load(fh)


def self_test():
    report = {
        "metadata": {"updated_at": "2026-01-01", "pipeline_version": "9.9.9"},
        "summary": {"overall_state": "App a <medias> & honesta", "features_complete": 1,
                    "features_partial": 1, "gap_count": 1, "question_count": 1},
        "feature_states": [
            {"feature_id": None, "name": "Alta de <script>usuarios</script>",
             "state": "partial", "missing": ["validar & sanear"],
             "capability_refs": ["CAP-001"], "evidence_refs": ["CAP-001"]},
            {"feature_id": "FG-01", "name": "Login", "state": "complete",
             "missing": [], "evidence_refs": ["CAP-002"]},
        ],
        "gaps": [{"id": "GAP-001", "kind": "loose_end", "status": "open",
                  "description": "campo guardado y nunca leido",
                  "evidence_refs": ["src/a.py:10"],
                  "suggested_resolution": "confirmar con el dueño"}],
        "audit_signals": [{"signal": "sin manejo de errores en el pago",
                           "evidence_refs": ["src/pay.py:44"]}],
        "warnings": ["evidencia imprecisa en CAP-003"],
    }
    questions = {"questions": [
        {"id": "OWN-001", "question": "¿La pantalla de reportes va o se saca?",
         "status": "open", "priority": "high", "expected_answer_type": "choice",
         "choices": ["la terminamos", "se saca"]},
        {"id": "OWN-002", "question": "ya respondida", "status": "answered",
         "priority": "low"},
    ]}
    page = render(report, questions, "Estado de la aplicacion")
    checks = [
        "<script>" not in page,                     # todo texto escapado
        "&lt;script&gt;usuarios&lt;/script&gt;" in page,
        "A medias" in page and "Completa" in page,  # semaforo
        "Cabos sueltos" in page,                    # hueco agrupado por tipo
        "OWN-001" in page and "ya respondida" not in page,  # solo abiertas
        "recovery-pipeline v9.9.9" in page,
        "http" not in page.lower().replace("html", ""),  # sin recursos externos
        render(report, questions, "Estado de la aplicacion") == page,  # determinista
    ]
    empty_page = render({"summary": {}}, None, "Estado de la aplicacion")
    checks.append("Features por estado" not in empty_page)  # degradacion
    if not all(checks):
        print("self-test FALLO: checks=%s" % checks)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/recovery")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--titulo", default="Estado de la aplicacion")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        sys.exit(self_test())

    folder = Path(args.carpeta)
    report_path = folder / "state-report.json"
    if not report_path.is_file():
        print("no existe %s" % report_path)
        sys.exit(1)
    try:
        report = load_json(report_path)
        questions_path = folder / "owner-questions.json"
        questions_doc = load_json(questions_path) if questions_path.is_file() else None
    except (OSError, ValueError) as exc:
        print("error leyendo los JSON: %s" % exc)
        sys.exit(1)

    out_path = Path(args.salida) if args.salida else folder / "state-report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(report, questions_doc, args.titulo), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
