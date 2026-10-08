#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deriva .dev/metrics/analysis.md desde analysis.json (el diagnostico del analista).

El analista (metrics-analyst) escribe SOLO el JSON estructurado; el .md lo deriva este
script, como todo .md de la suite. Motivo: el harness de Claude Code rechaza que un
subagente escriba archivos de reporte en Markdown ("Subagents should return findings
as text, not write report files"), y en la corrida de prueba analysis.md nunca se
creo. Un JSON de datos no tiene ese problema, y el render queda determinista.

Uso:
  python render_analysis.py [raiz-del-proyecto]   lee <raiz>/.dev/metrics/analysis.json
  python render_analysis.py --self-test
Exit 0 si derivo; 1 si el JSON no existe o no parsea.
Solo stdlib, Python 3.8+.
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

PRIORIDAD = {"alta": "Alta", "media": "Media", "baja": "Baja"}


def render(doc):
    out = ["# Analisis de metricas de la suite", "",
           "> Derivado de `analysis.json` version %s — no editar a mano." % doc.get("version", "?"),
           "> Lo escribe render_analysis.py a partir del diagnostico del analista.", ""]
    if doc.get("fecha") or doc.get("metrics_generated_from"):
        out.append("_Analisis del %s sobre datos al %s._" % (doc.get("fecha") or "?", doc.get("metrics_generated_from") or "?"))
        out.append("")
    n = doc.get("sample_size") or {}
    if n:
        out.append("Muestra: " + ", ".join("%s %s" % (v, k.replace("_", " ")) for k, v in n.items() if v) + ".")
        out.append("")
    if doc.get("lectura_general"):
        out.append("## Lectura general")
        out.append("")
        out.append(str(doc["lectura_general"]))
        out.append("")
    dx = doc.get("diagnosticos") or []
    if dx:
        out.append("## Diagnosticos (por prioridad)")
        out.append("")
        orden = {"alta": 0, "media": 1, "baja": 2}
        for d in sorted(dx, key=lambda x: orden.get(x.get("prioridad"), 9)):
            out.append("### %s · %s · prioridad %s" % (d.get("id", "?"), d.get("metrica", "?"), PRIORIDAD.get(d.get("prioridad"), d.get("prioridad", "?"))))
            out.append("")
            if d.get("valor") is not None or d.get("umbral"):
                out.append("- Valor: `%s` (umbral %s)" % (d.get("valor"), d.get("umbral") or "—"))
            if d.get("lectura"):
                out.append("- Lectura: %s" % d["lectura"])
            if d.get("correccion"):
                out.append("- Correccion: %s" % d["correccion"])
            if d.get("sospechoso"):
                out.append("- Donde: `%s`" % d["sospechoso"])
            out.append("")
    cerca = doc.get("señales_cercanas") or doc.get("senales_cercanas") or []
    if cerca:
        out.append("## Señales cerca del umbral")
        out.append("")
        for s in cerca:
            out.append("- `%s` = %s (umbral %s): %s" % (s.get("metrica"), s.get("valor"), s.get("umbral"), s.get("nota", "")))
        out.append("")
    comp = doc.get("comparacion")
    if isinstance(comp, dict):
        out.append("## Contra la linea de base")
        out.append("")
        if comp.get("resumen"):
            out.append(str(comp["resumen"]))
            out.append("")
        for titulo, clave in (("Regresiones", "regresiones"), ("Mejoras", "mejoras"), ("No comparable por", "no_comparable_por")):
            items = comp.get(clave) or []
            if items:
                out.append("**%s**" % titulo)
                out.append("")
                for it in items:
                    out.append("- %s" % it)
                out.append("")
    huecos = doc.get("huecos_de_cosecha") or []
    if huecos:
        out.append("## Huecos de cosecha")
        out.append("")
        for h in huecos:
            marca = " (requiere cambio de contrato)" if h.get("requiere_cambio_de_contrato") else ""
            out.append("- `%s`: %s%s" % (h.get("metrica"), h.get("por_que", ""), marca))
        out.append("")
    for w in doc.get("warnings") or []:
        out.append("> aviso: %s" % w)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def main(argv):
    if "--self-test" in argv:
        return self_test()
    raiz = Path(argv[0]) if argv and not argv[0].startswith("--") else Path(".")
    src = raiz / ".dev" / "metrics" / "analysis.json"
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: %s: %s" % (src, exc))
        return 1
    dest = src.with_suffix(".md")
    dest.write_text(render(doc), encoding="utf-8")
    print("derivado: %s (version %s, %d diagnostico(s))" % (dest, doc.get("version", "?"), len(doc.get("diagnosticos") or [])))
    return 0


def self_test():
    doc = {"version": 1, "fecha": "2026-10-08", "metrics_generated_from": "2026-10-08",
           "sample_size": {"features_reviewed": 2, "evidence_checks": 22},
           "lectura_general": "n=2 features: tendencia, no evidencia.",
           "diagnosticos": [
               {"id": "DX-002", "prioridad": "baja", "metrica": "x", "valor": 1, "umbral": ">= 1", "lectura": "l", "correccion": "c", "sospechoso": "s"},
               {"id": "DX-001", "prioridad": "alta", "metrica": "build.reviews.avg_rounds_proxy", "valor": 2.0, "umbral": ">= 2.0",
                "lectura": "rondas altas", "correccion": "implementer verifica antes", "sospechoso": "build-pipeline/feature-implementer"}],
           "comparacion": {"resumen": "igual salvo tokens", "regresiones": ["run_tokens"], "mejoras": [], "no_comparable_por": []},
           "huecos_de_cosecha": [{"metrica": "rondas reales", "por_que": "no hay historial", "requiere_cambio_de_contrato": True}],
           "warnings": ["muestra chica"]}
    md = render(doc)
    checks = [
        ("Derivado de `analysis.json` version 1" in md, "encabezado derivado"),
        (md.index("DX-001") < md.index("DX-002"), "ordenado por prioridad"),
        ("- Donde: `build-pipeline/feature-implementer`" in md, "sospechoso"),
        ("**Regresiones**" in md and "- run_tokens" in md, "comparacion"),
        ("(requiere cambio de contrato)" in md, "hueco con contrato"),
        ("> aviso: muestra chica" in md, "warnings"),
        ("## Lectura general" in render({"version": 2, "lectura_general": "x"}), "minimo"),
    ]
    failures = 0
    for cond, label in checks:
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))
        failures += 0 if cond else 1
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
