#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Muestra determinista para el spot-check: behavior-map.json -> .spot-check-input.json.

La regla de seleccion de `evidence-spot-check` es deterministica por diseño (dos
corridas sobre el mismo mapa eligen lo mismo), o sea: es un script. Antes el agente
leia el behavior-map entero para quedarse con <= 13 capacidades. Ahora recibe solo
la tajada.

Regla (la del agente):
  - todas las capacidades `complete`, hasta 10; si hay mas, las de mas reglas de
    negocio y, a igualdad, las de id mas bajo;
  - las primeras 3 `partial` por id;
  - `skeleton` y `dead` se ignoran.

Con `--caps CAP-001,CAP-007` (re-verificacion tras una correccion) la muestra es
exactamente esa lista.

Solo stdlib, Python 3.8+. No modifica el behavior-map.

Uso:
  python sample_capabilities.py [carpeta-recovery] [--caps CAP-001,CAP-002] [--max-complete 10] [--max-partial 3]
  python sample_capabilities.py --self-test

Salida: escribe <carpeta>/.spot-check-input.json (capacidades completas, version del
mapa y la regla aplicada) e imprime los ids muestreados. Exit 1 ante JSON invalido.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def id_num(cid):
    m = re.search(r"(\d+)$", str(cid))
    return int(m.group(1)) if m else 0


def sample(bmap, caps=None, max_complete=10, max_partial=3):
    capabilities = bmap.get("capabilities") or []
    if caps:
        wanted = set(caps)
        chosen = [c for c in capabilities if c.get("id") in wanted]
        missing = sorted(wanted - {c.get("id") for c in chosen})
        return chosen, {"mode": "explicit", "missing": missing}
    complete = [c for c in capabilities if c.get("implementation_status") == "complete"]
    complete.sort(key=lambda c: (-len(c.get("business_rules") or []), id_num(c.get("id")), c.get("id")))
    partial = [c for c in capabilities if c.get("implementation_status") == "partial"]
    partial.sort(key=lambda c: (id_num(c.get("id")), c.get("id")))
    chosen = complete[:max_complete] + partial[:max_partial]
    chosen.sort(key=lambda c: (id_num(c.get("id")), c.get("id")))
    return chosen, {"mode": "rule", "complete_total": len(complete), "partial_total": len(partial), "max_complete": max_complete, "max_partial": max_partial}


def self_test():
    checks = []
    caps = []
    for i in range(1, 16):
        caps.append({"id": "CAP-%03d" % i, "implementation_status": "complete", "business_rules": [{"rule": "r"}] * (i % 4)})
    for i in range(16, 21):
        caps.append({"id": "CAP-%03d" % i, "implementation_status": "partial"})
    caps.append({"id": "CAP-021", "implementation_status": "skeleton"})
    bmap = {"version": 3, "capabilities": caps}
    chosen, info = sample(bmap)
    ids = [c["id"] for c in chosen]
    checks.append(("13 muestreadas", len(ids) == 13))
    checks.append(("complete con mas reglas primero", "CAP-003" in ids and "CAP-007" in ids and "CAP-004" not in ids))
    checks.append(("primeras 3 partial", ids[-3:] == ["CAP-016", "CAP-017", "CAP-018"]))
    checks.append(("skeleton excluido", "CAP-021" not in ids))
    checks.append(("determinista", [c["id"] for c in sample(bmap)[0]] == ids))
    ch2, info2 = sample(bmap, caps=["CAP-020", "CAP-099"])
    checks.append(("explicito", [c["id"] for c in ch2] == ["CAP-020"] and info2["missing"] == ["CAP-099"]))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/recovery")
    ap.add_argument("--caps", default=None)
    ap.add_argument("--max-complete", type=int, default=10)
    ap.add_argument("--max-partial", type=int, default=3)
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
    except json.JSONDecodeError as e:
        print("error: %s" % e)
        return 1
    caps = [c.strip() for c in args.caps.split(",") if c.strip()] if args.caps else None
    chosen, info = sample(bmap, caps, args.max_complete, args.max_partial)
    out = folder / ".spot-check-input.json"
    out.write_text(json.dumps({"behavior_map_version_ref": str(bmap.get("version", "")), "selection": info, "capabilities": chosen}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("muestra: %d capacidades -> %s" % (len(chosen), out))
    print(", ".join(c.get("id", "?") for c in chosen))
    if info.get("missing"):
        print("aviso: no estan en el mapa: %s" % ", ".join(info["missing"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
