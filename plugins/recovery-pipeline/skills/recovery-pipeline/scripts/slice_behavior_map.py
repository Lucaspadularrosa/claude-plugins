#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tajada determinista del behavior-map para el agente que la consume.

`gap-analysis` no necesita los `flow` ni las reglas de negocio completas: busca
estados `partial`/`skeleton`, cabos sueltos, incoherencias y ausencias. Le alcanza
una proyeccion por capacidad (id, nombre, descripcion, actores, entry points,
modulos, estado, evidencia de estado, manejo de errores) mas el vocabulario en forma
compacta, las entidades con sus campos sin uso, las preguntas abiertas y los
veredictos no confirmados del evidence-check ya cruzados por capacidad. Suele ser el
20-30% del mapa original.

Mismo input -> mismo output. Solo stdlib, Python 3.8+. No modifica el mapa.

Uso:
  python slice_behavior_map.py [carpeta-recovery] --para gap-analysis [--salida ARCHIVO]
  python slice_behavior_map.py --self-test

Salida: escribe <carpeta>/.slice-gap-analysis.json e imprime tamaños (bytes del
mapa vs. la tajada). Exit 1 ante JSON invalido.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CAP_FIELDS = ("id", "name", "description", "actors", "entry_point_ids", "module_ids", "error_handling", "implementation_status", "status_evidence")


def slice_for_gap_analysis(bmap, evidence=None):
    non_confirmed = {}
    for chk in (evidence or {}).get("checks") or []:
        if chk.get("verdict") in ("refuted", "imprecise"):
            non_confirmed.setdefault(chk.get("capability_id"), []).append({"id": chk.get("id"), "aspect": chk.get("aspect"), "verdict": chk.get("verdict"), "detail": chk.get("detail")})
    caps = []
    for c in bmap.get("capabilities") or []:
        item = {k: c.get(k) for k in CAP_FIELDS}
        item["business_rule_count"] = len(c.get("business_rules") or [])
        item["flow_step_count"] = len(c.get("flow") or [])
        item["evidence_ref_count"] = len(c.get("evidence_refs") or [])
        if c.get("id") in non_confirmed:
            item["evidence_check"] = non_confirmed[c["id"]]
        caps.append(item)
    return {
        "derived_from": {"behavior_map_version": bmap.get("version"), "evidence_check_version": (evidence or {}).get("version"), "slice_for": "gap-analysis"},
        "summary": bmap.get("summary") or {},
        "capabilities": caps,
        "vocabulary": [{"term": v.get("term"), "kind": v.get("kind"), "variants": v.get("variants") or []} for v in bmap.get("vocabulary") or []],
        "data_entities": [{"id": e.get("id"), "name": e.get("name"), "unused_fields": [f.get("name") for f in e.get("fields") or [] if f.get("used") is False], "relationships": e.get("relationships") or []} for e in bmap.get("data_entities") or []],
        "open_questions": bmap.get("open_questions") or [],
        "warnings": bmap.get("warnings") or [],
        "evidence_summary": (evidence or {}).get("summary") or {},
    }


def self_test():
    checks = []
    bmap = {"version": 2, "summary": {"capability_count": 2}, "capabilities": [
        {"id": "CAP-001", "name": "A", "implementation_status": "complete", "flow": ["1", "2", "3"], "business_rules": [{"rule": "x", "evidence": "a:1"}], "evidence_refs": ["a:1", "a:2"]},
        {"id": "CAP-002", "name": "B", "implementation_status": "partial", "status_evidence": "falta", "flow": [], "business_rules": []},
    ], "vocabulary": [{"term": "socio", "kind": "objeto", "variants": ["member"], "meaning_from_code": "largo", "evidence_refs": ["a:1"]}],
        "data_entities": [{"id": "RENT-001", "name": "Socio", "fields": [{"name": "id", "used": True}, {"name": "legacy", "used": False}]}], "open_questions": ["q"]}
    ev = {"version": 1, "summary": {"refuted": 1}, "checks": [{"id": "CHK-001", "capability_id": "CAP-001", "aspect": "flow_step", "verdict": "refuted", "detail": "no"}, {"id": "CHK-002", "capability_id": "CAP-002", "aspect": "business_rule", "verdict": "confirmed", "detail": ""}]}
    s = slice_for_gap_analysis(bmap, ev)
    c1 = s["capabilities"][0]
    checks.append(("sin flow ni reglas", "flow" not in c1 and "business_rules" not in c1 and c1["flow_step_count"] == 3))
    checks.append(("refutado cruzado", c1["evidence_check"][0]["verdict"] == "refuted" and "evidence_check" not in s["capabilities"][1]))
    checks.append(("campos sin uso", s["data_entities"][0]["unused_fields"] == ["legacy"]))
    checks.append(("vocabulario compacto", "meaning_from_code" not in s["vocabulary"][0]))
    checks.append(("contenido pesado fuera", "largo" not in json.dumps(s) and "evidence_refs" not in json.dumps(s["capabilities"])))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/recovery")
    ap.add_argument("--para", default="gap-analysis", choices=["gap-analysis"])
    ap.add_argument("--salida", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    src = folder / "behavior-map.json"
    if not src.exists():
        print("error: falta %s" % src)
        return 1
    try:
        bmap = json.loads(src.read_text(encoding="utf-8"))
        evp = folder / "evidence-check.json"
        evidence = json.loads(evp.read_text(encoding="utf-8")) if evp.exists() else None
    except json.JSONDecodeError as e:
        print("error: %s" % e)
        return 1
    data = slice_for_gap_analysis(bmap, evidence)
    out = Path(args.salida) if args.salida else folder / (".slice-%s.json" % args.para)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    print("tajada %s: %d bytes (mapa %d) -> %s" % (args.para, len(text.encode("utf-8")), src.stat().st_size, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
