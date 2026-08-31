#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill determinista de feature_id: state-report.json x product-map.json.

Tras reconstruir la linea de base, cada `feature_state` del reporte de estado tiene
que apuntar al `FG-xx` real del product-map. Antes eso costaba una pasada completa
de `gap-analysis` releyendo inventario, behavior-map y evidence-check para escribir
un id por feature. Es un cruce por ids: la reconstruccion pone en cada feature del
mapa sus `capability_refs` (`CAP-xxx`) y este script interseca contra los
`capability_refs` del reporte.

Reglas:
  - Un feature_state cuyas capacidades caen en UN solo FG -> feature_id = ese FG.
  - Sin capacidades en comun -> fallback por nombre normalizado (misma cadena sin
    tildes, minusculas, sin puntuacion).
  - Caen en VARIOS FG (la reconstruccion partio el grupo) o un FG absorbe varios
    feature_states (los unio): NO se resuelve aca. Se reporta y sale con exit 2 para
    que el orquestador invoque a `gap-analysis` en modo actualizacion solo en ese
    caso.
  - Los `gaps` heredan `feature_ids` de los feature_states que citan sus CAP.
  - Version +1 del state-report; los ids GAP/OWN no se tocan.

Solo stdlib, Python 3.8+.

Uso:
  python backfill_feature_ids.py [carpeta-recovery] [--requirements CARPETA] [--dry-run]
  python backfill_feature_ids.py --self-test

Salida: una linea por feature resuelta y el resumen. Exit 0 si todo mapeo, 2 si
quedaron grupos partidos/unidos (requiere agente), 1 ante error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def backfill(state, pmap):
    features = pmap.get("features") or []
    caps_by_fg = {f["id"]: set(f.get("capability_refs") or []) for f in features}
    name_by_fg = {norm(f.get("name")): f["id"] for f in features}
    resolved, unresolved = [], []
    fg_owner = {}
    for fs in state.get("feature_states") or []:
        caps = set(fs.get("capability_refs") or [])
        hits = sorted(fg for fg, fcaps in caps_by_fg.items() if caps & fcaps)
        if len(hits) == 1:
            chosen = hits[0]
        elif not hits and norm(fs.get("name")) in name_by_fg:
            chosen = name_by_fg[norm(fs.get("name"))]
        elif len(hits) > 1:
            unresolved.append({"name": fs.get("name"), "reason": "partida", "candidates": hits})
            continue
        else:
            unresolved.append({"name": fs.get("name"), "reason": "sin_correspondencia", "candidates": []})
            continue
        fg_owner.setdefault(chosen, []).append(fs.get("name"))
        fs["feature_id"] = chosen
        resolved.append((fs.get("name"), chosen))
    for fg, owners in fg_owner.items():
        if len(owners) > 1:
            for o in owners:
                unresolved.append({"name": o, "reason": "unida", "candidates": [fg]})
    cap_to_fg = {}
    for fs in state.get("feature_states") or []:
        if fs.get("feature_id"):
            for c in fs.get("capability_refs") or []:
                cap_to_fg[c] = fs["feature_id"]
    for g in state.get("gaps") or []:
        fgs = sorted({cap_to_fg[r] for r in (g.get("evidence_refs") or []) if r in cap_to_fg})
        if fgs and not g.get("feature_ids"):
            g["feature_ids"] = fgs
    return resolved, unresolved


def self_test():
    checks = []
    state = {"version": 2, "feature_states": [
        {"feature_id": None, "name": "Socios", "capability_refs": ["CAP-001", "CAP-002"]},
        {"feature_id": None, "name": "Reportes", "capability_refs": ["CAP-003"]},
        {"feature_id": None, "name": "Pagos", "capability_refs": ["CAP-004", "CAP-005"]},
        {"feature_id": None, "name": "Auditoria", "capability_refs": []},
    ], "gaps": [{"id": "GAP-001", "evidence_refs": ["CAP-003", "a.js:1"], "feature_ids": []}]}
    pmap = {"features": [
        {"id": "FG-01", "name": "Gestion de socios", "capability_refs": ["CAP-001", "CAP-002"]},
        {"id": "FG-02", "name": "Reportes", "capability_refs": ["CAP-003"]},
        {"id": "FG-03", "name": "Cobros", "capability_refs": ["CAP-004"]},
        {"id": "FG-04", "name": "Conciliacion", "capability_refs": ["CAP-005"]},
        {"id": "FG-05", "name": "Auditoria", "capability_refs": []},
    ]}
    resolved, unresolved = backfill(state, pmap)
    by = dict(resolved)
    checks.append(("por caps", by.get("Socios") == "FG-01" and by.get("Reportes") == "FG-02"))
    checks.append(("por nombre normalizado", by.get("Auditoria") == "FG-05"))
    checks.append(("partida detectada", any(u["reason"] == "partida" and u["candidates"] == ["FG-03", "FG-04"] for u in unresolved)))
    checks.append(("gap hereda FG", state["gaps"][0]["feature_ids"] == ["FG-02"]))
    state2 = {"feature_states": [{"feature_id": None, "name": "A", "capability_refs": ["CAP-001"]}, {"feature_id": None, "name": "B", "capability_refs": ["CAP-002"]}], "gaps": []}
    pmap2 = {"features": [{"id": "FG-01", "name": "AB", "capability_refs": ["CAP-001", "CAP-002"]}]}
    _, un2 = backfill(state2, pmap2)
    checks.append(("unida detectada", len(un2) == 2 and all(u["reason"] == "unida" for u in un2)))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/recovery")
    ap.add_argument("--requirements", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    req = Path(args.requirements) if args.requirements else folder.parent / "requirements"
    sp, pp = folder / "state-report.json", req / "product-map.json"
    for p in (sp, pp):
        if not p.exists():
            print("error: falta %s" % p)
            return 1
    try:
        state = json.loads(sp.read_text(encoding="utf-8"))
        pmap = json.loads(pp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print("error: %s" % e)
        return 1
    resolved, unresolved = backfill(state, pmap)
    for name, fg in resolved:
        print("%s -> %s" % (name, fg))
    for u in unresolved:
        print("SIN RESOLVER: %s (%s%s)" % (u["name"], u["reason"], (": " + ", ".join(u["candidates"])) if u["candidates"] else ""))
    if not args.dry_run:
        state["version"] = int(state.get("version") or 0) + 1
        sp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("backfill: %d resueltas, %d sin resolver%s" % (len(resolved), len(unresolved), " (requiere gap-analysis en modo actualizacion)" if unresolved else ""))
    return 2 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
