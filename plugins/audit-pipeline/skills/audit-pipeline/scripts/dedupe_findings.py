#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidacion determinista de hallazgos: findings-*.json -> findings-merged.json.

Las tres dimensiones de la auditoria corren en paralelo sobre el mismo codigo y sus
dominios se solapan (validacion de entrada es bug y seguridad; un error tragado es
bug y deuda). Sin este paso, el mismo `archivo:linea` dispara dos verificaciones
adversariales. Este script:

1. Une los hallazgos de `findings-bugs.json`, `findings-security.json` y
   `findings-improvements.json` (los que existan).
2. Detecta solapamientos por evidencia: mismo archivo y lineas a distancia <= 5.
3. Fusiona:
   - dentro de la misma dimension, siempre (sobrevive el id mas bajo; union de
     evidencias; severidad y confianza mas altas; `merged_ids` guarda el rastro);
   - entre `bugs` y `security`, tambien (es donde el solape es real);
   - `improvements` nunca se fusiona con otra dimension: un bug y una mejora sobre
     las mismas lineas son cosas distintas. Se enlazan por `related_ids`.
4. Arma los grupos de verificacion por archivo: un `finding-verifier` por grupo, con
   la sugerencia de modelo (`opus` si el grupo tiene algun `high`, `sonnet` si no).
   Los hallazgos `verification_mode: mechanical` van a `mechanical` (los verifica
   `verify_mechanical.py`, no un agente); los `low` a `low_unverified`.

Mismo input -> mismo output. Solo stdlib, Python 3.8+. No modifica los findings.

Uso:
  python dedupe_findings.py [carpeta-audit] [--distancia N] [--json]
  python dedupe_findings.py --self-test

  carpeta-audit  por defecto .dev/audit
  --distancia    lineas de tolerancia para considerar la misma evidencia (default 5)
  --json         imprime el summary en JSON ademas de la linea legible

Salida: escribe <carpeta>/findings-merged.json e imprime el resumen (total de
entrada, duplicados, grupos a verificar por modelo). Exit 1 ante JSON invalido.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DIMENSION_FILES = [
    ("bugs", "findings-bugs.json"),
    ("security", "findings-security.json"),
    ("improvements", "findings-improvements.json"),
]
SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
REF_RE = re.compile(r"^(?P<path>.+?)(?::(?P<line>\d+)(?:-\d+)?)?$")


def parse_ref(ref):
    m = REF_RE.match(str(ref).strip())
    if not m:
        return None, None
    path = m.group("path").strip().replace("\\", "/").lstrip("./")
    line = int(m.group("line")) if m.group("line") else None
    return path, line


def refs_overlap(refs_a, refs_b, distance):
    for a in refs_a:
        pa, la = parse_ref(a)
        if not pa:
            continue
        for b in refs_b:
            pb, lb = parse_ref(b)
            if pa != pb:
                continue
            if la is None or lb is None or abs(la - lb) <= distance:
                return True
    return False


def id_number(fid):
    m = re.search(r"(\d+)$", str(fid))
    return int(m.group(1)) if m else 0


def can_merge(dim_a, dim_b):
    if dim_a == dim_b:
        return True
    return {dim_a, dim_b} == {"bugs", "security"}


def load_findings(folder):
    items = []
    warnings = []
    metadata = {}
    for dim, name in DIMENSION_FILES:
        path = folder / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not metadata:
            metadata = dict(data.get("metadata") or {})
        for f in data.get("findings") or []:
            f = dict(f)
            f["dimension"] = dim
            f.setdefault("confidence", "medium")
            f.setdefault("verification_mode", "adversarial")
            f["evidence_refs"] = list(f.get("evidence_refs") or [])
            items.append(f)
        warnings.extend(data.get("warnings") or [])
    return items, metadata, warnings


def merge_two(base, other):
    base.setdefault("merged_ids", [])
    base["merged_ids"].append(other["id"])
    base["merged_ids"].extend(other.get("merged_ids") or [])
    for ref in other["evidence_refs"]:
        if ref not in base["evidence_refs"]:
            base["evidence_refs"].append(ref)
    if SEVERITY_RANK.get(other.get("severity"), 0) > SEVERITY_RANK.get(base.get("severity"), 0):
        base["severity"] = other["severity"]
    if CONFIDENCE_RANK.get(other.get("confidence"), 0) > CONFIDENCE_RANK.get(base.get("confidence"), 0):
        base["confidence"] = other["confidence"]
    if base["dimension"] != other["dimension"]:
        base.setdefault("dimensions", [base["dimension"]])
        if other["dimension"] not in base["dimensions"]:
            base["dimensions"].append(other["dimension"])
    for key in ("related_requirement_ids", "related_feature_ids"):
        vals = list(base.get(key) or [])
        for v in other.get(key) or []:
            if v not in vals:
                vals.append(v)
        if vals:
            base[key] = vals
    if other.get("verification_mode") == "adversarial":
        base["verification_mode"] = "adversarial"
    base.setdefault("merged_titles", []).append(other.get("title", ""))


def dedupe(findings, distance):
    ordered = sorted(findings, key=lambda f: (SEVERITY_RANK.get(f.get("severity"), 0) * -1, f["dimension"], id_number(f["id"]), f["id"]))
    kept = []
    for f in ordered:
        target = None
        for k in kept:
            if not refs_overlap(k["evidence_refs"], f["evidence_refs"], distance):
                continue
            if can_merge(k["dimension"], f["dimension"]):
                target = k
                break
            k.setdefault("related_ids", [])
            if f["id"] not in k["related_ids"]:
                k["related_ids"].append(f["id"])
            f.setdefault("related_ids", [])
            if k["id"] not in f["related_ids"]:
                f["related_ids"].append(k["id"])
        if target is None:
            kept.append(f)
        else:
            if id_number(f["id"]) < id_number(target["id"]) and f["dimension"] == target["dimension"]:
                f, target = target, f
                idx = kept.index(f)
                kept[idx] = target
            merge_two(target, f)
    kept.sort(key=lambda f: (f["dimension"], id_number(f["id"]), f["id"]))
    return kept


def build_groups(findings):
    groups = {}
    mechanical = []
    low = []
    for f in findings:
        if f.get("severity") == "low":
            low.append(f["id"])
            continue
        if f.get("verification_mode") == "mechanical":
            mechanical.append(f["id"])
            continue
        path, _ = parse_ref(f["evidence_refs"][0]) if f["evidence_refs"] else (None, None)
        key = path or "(sin archivo)"
        g = groups.setdefault(key, {"file": key, "finding_ids": [], "severity_max": "medium"})
        g["finding_ids"].append(f["id"])
        if f.get("severity") == "high":
            g["severity_max"] = "high"
    out = []
    for i, key in enumerate(sorted(groups), start=1):
        g = groups[key]
        g["group_id"] = "VG-%03d" % i
        g["model_hint"] = "opus" if g["severity_max"] == "high" else "sonnet"
        out.append({"group_id": g["group_id"], "file": g["file"], "finding_ids": g["finding_ids"], "severity_max": g["severity_max"], "model_hint": g["model_hint"]})
    return out, mechanical, low


def consolidate(folder, distance):
    findings, metadata, warnings = load_findings(folder)
    input_total = len(findings)
    merged = dedupe(findings, distance)
    groups, mechanical, low = build_groups(merged)
    by_dim = {}
    for f in merged:
        by_dim[f["dimension"]] = by_dim.get(f["dimension"], 0) + 1
    to_verify = {"high": 0, "medium": 0}
    for f in merged:
        if f.get("severity") in to_verify and f.get("verification_mode") != "mechanical":
            to_verify[f["severity"]] += 1
    result = {
        "version": 1,
        "metadata": {
            "created_at": metadata.get("created_at"),
            "scope": metadata.get("scope"),
            "pipeline_version": metadata.get("pipeline_version"),
            "distance": distance,
        },
        "summary": {
            "input_total": input_total,
            "merged_total": len(merged),
            "duplicates_removed": input_total - len(merged),
            "by_dimension": by_dim,
            "to_verify": to_verify,
            "mechanical": len(mechanical),
            "low_unverified": len(low),
            "verification_groups": len(groups),
            "groups_opus": sum(1 for g in groups if g["model_hint"] == "opus"),
            "groups_sonnet": sum(1 for g in groups if g["model_hint"] == "sonnet"),
        },
        "findings": merged,
        "verification_groups": groups,
        "mechanical": mechanical,
        "low_unverified": low,
        "warnings": warnings,
    }
    return result


def self_test():
    import tempfile

    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "findings-bugs.json").write_text(json.dumps({
            "version": 1, "metadata": {"created_at": "2026-01-01", "scope": "todo", "pipeline_version": "1.3.0"},
            "findings": [
                {"id": "BUG-001", "severity": "medium", "title": "sin validar", "evidence_refs": ["src/api.js:10"]},
                {"id": "BUG-002", "severity": "high", "title": "otro", "evidence_refs": ["src/db.js:40"]},
                {"id": "BUG-003", "severity": "low", "title": "raro", "evidence_refs": ["src/x.js:1"]},
            ], "warnings": ["w1"]}), encoding="utf-8")
        (folder / "findings-security.json").write_text(json.dumps({
            "version": 1, "metadata": {},
            "findings": [
                {"id": "SEC-001", "severity": "high", "title": "input", "evidence_refs": ["src/api.js:12"]},
                {"id": "SEC-002", "severity": "medium", "title": "secreto", "evidence_refs": ["config.js:3"],
                 "verification_mode": "mechanical", "confidence": "high"},
            ], "warnings": []}), encoding="utf-8")
        (folder / "findings-improvements.json").write_text(json.dumps({
            "version": 1, "metadata": {},
            "findings": [
                {"id": "IMP-001", "severity": "high", "title": "tests", "evidence_refs": ["src/api.js:11"]},
            ], "warnings": []}), encoding="utf-8")
        res = consolidate(folder, 5)
        s = res["summary"]
        checks.append(("entrada 6", s["input_total"] == 6))
        checks.append(("bug+sec fusionados", s["duplicates_removed"] == 1))
        merged = {f["id"]: f for f in res["findings"]}
        checks.append(("sobrevive SEC-001 con BUG-001 absorbido", "BUG-001" in (merged.get("SEC-001", {}).get("merged_ids") or []) or "SEC-001" in (merged.get("BUG-001", {}).get("merged_ids") or [])))
        surv = merged.get("SEC-001") or merged.get("BUG-001")
        checks.append(("severidad maxima conservada", surv["severity"] == "high"))
        checks.append(("ambas evidencias", len(surv["evidence_refs"]) == 2))
        checks.append(("IMP no fusionado", "IMP-001" in merged))
        checks.append(("IMP enlazado", surv["id"] in (merged["IMP-001"].get("related_ids") or [])))
        checks.append(("mecanico aparte", res["mechanical"] == ["SEC-002"]))
        checks.append(("low aparte", res["low_unverified"] == ["BUG-003"]))
        files = {g["file"] for g in res["verification_groups"]}
        checks.append(("grupo por archivo", files == {"src/api.js", "src/db.js"}))
        api = [g for g in res["verification_groups"] if g["file"] == "src/api.js"][0]
        checks.append(("grupo api con 2 ids y opus", len(api["finding_ids"]) == 2 and api["model_hint"] == "opus"))
        checks.append(("pipeline_version acarreada", res["metadata"]["pipeline_version"] == "1.3.0"))
        again = consolidate(folder, 5)
        checks.append(("determinista", json.dumps(again, sort_keys=True) == json.dumps(res, sort_keys=True)))
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/audit")
    ap.add_argument("--distancia", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    if not folder.exists():
        print("error: no existe %s" % folder)
        return 1
    try:
        res = consolidate(folder, args.distancia)
    except (json.JSONDecodeError, OSError) as e:
        print("error: %s" % e)
        return 1
    out = folder / "findings-merged.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = res["summary"]
    print("findings-merged: %d de entrada, %d duplicados, %d a verificar (%d grupos: %d opus, %d sonnet), %d mecanicos, %d low sin verificar -> %s" % (
        s["input_total"], s["duplicates_removed"], s["to_verify"]["high"] + s["to_verify"]["medium"],
        s["verification_groups"], s["groups_opus"], s["groups_sonnet"], s["mechanical"], s["low_unverified"], out))
    if args.json:
        print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
