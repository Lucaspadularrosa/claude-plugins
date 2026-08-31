#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificacion mecanica de hallazgos: aserciones binarias sobre el codigo, sin agente.

Un secreto hardcodeado en `config.js:12`, una dependencia con CVE en el lockfile o
un archivo que existe se refutan o confirman con una asercion, no con una pasada
de modelo leyendo codigo. Este script toma los hallazgos con
`verification_mode: mechanical` de `findings-merged.json` y ejecuta sus
`mechanical_assertions`:

  literal_present   {file, line?, pattern}   el texto aparece en el archivo (si hay
                                             `line`, en esa linea +/- 2)
  file_exists       {file}                   el archivo existe
  lockfile_has      {file, package}          el paquete aparece en el lockfile

Todas pasan -> `confirmed`. Alguna falla -> `refuted` con
`refutation_basis: mechanical_assertion_failed`. Sin aserciones declaradas ->
`needs_human` (el auditor marco mecanico pero no dijo que verificar). Cada veredicto
se escribe a `<carpeta>/verdicts/<finding_id>.json` con el mismo contrato que emite
`finding-verifier`, asi `render_audit_report.py` no distingue el origen.

Restringido a proposito: solo lo que es verdaderamente binario. Todo lo que exige
contexto (¿esa linea es un fixture de test?) es adversarial, no mecanico.

Solo stdlib, Python 3.8+. Solo lectura sobre el proyecto.

Uso:
  python verify_mechanical.py [carpeta-audit] [--raiz RUTA]
  python verify_mechanical.py --self-test

  carpeta-audit  por defecto .dev/audit (lee findings-merged.json)
  --raiz         raiz del proyecto para resolver rutas (default: directorio actual)

Salida: una linea por veredicto y el conteo. Exit 1 ante JSON invalido.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_lines(root, rel):
    path = root / rel
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def run_assertion(root, a):
    kind = a.get("kind")
    rel = str(a.get("file") or "")
    if kind == "file_exists":
        ok = (root / rel).exists()
        return ok, "%s %s" % (rel, "existe" if ok else "no existe")
    if kind == "literal_present":
        lines = read_lines(root, rel)
        if lines is None:
            return False, "%s no se pudo leer" % rel
        pattern = str(a.get("pattern") or "")
        if not pattern:
            return False, "asercion sin pattern"
        line = a.get("line")
        if line:
            lo, hi = max(1, int(line) - 2), min(len(lines), int(line) + 2)
            window = lines[lo - 1:hi]
            ok = any(pattern in l for l in window)
            return ok, "%s:%s %s" % (rel, line, "contiene el patron" if ok else "no contiene el patron en +/-2 lineas")
        ok = any(pattern in l for l in lines)
        return ok, "%s %s" % (rel, "contiene el patron" if ok else "no contiene el patron")
    if kind == "lockfile_has":
        lines = read_lines(root, rel)
        if lines is None:
            return False, "%s no se pudo leer" % rel
        pkg = str(a.get("package") or "")
        ok = any(pkg in l for l in lines) if pkg else False
        return ok, "%s %s %s" % (rel, "lista" if ok else "no lista", pkg)
    return False, "kind desconocido: %s" % kind


def verify_finding(root, f):
    assertions = f.get("mechanical_assertions") or []
    if not assertions:
        return {
            "finding_id": f["id"], "verdict": "needs_human", "adjusted_severity": None,
            "reasoning": "Marcado como mecanico sin aserciones declaradas: no hay nada que ejecutar.",
            "evidence_refs": list(f.get("evidence_refs") or []), "reproduction_attempted": None,
            "refutation_basis": None,
            "question_for_human": "¿Que asercion concreta (archivo, linea, patron) confirma este hallazgo?",
            "verified_by": "verify_mechanical",
        }
    results = [run_assertion(root, a) for a in assertions]
    ok = all(r[0] for r in results)
    detail = "; ".join(r[1] for r in results)
    return {
        "finding_id": f["id"], "verdict": "confirmed" if ok else "refuted",
        "adjusted_severity": None,
        "reasoning": "Aserciones mecanicas: %s." % detail,
        "evidence_refs": list(f.get("evidence_refs") or []),
        "reproduction_attempted": "%d aserciones ejecutadas" % len(results),
        "refutation_basis": None if ok else "mechanical_assertion_failed",
        "question_for_human": None,
        "verified_by": "verify_mechanical",
    }


def run(folder, root):
    merged = json.loads((folder / "findings-merged.json").read_text(encoding="utf-8"))
    ids = set(merged.get("mechanical") or [])
    out_dir = folder / "verdicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    verdicts = []
    for f in merged.get("findings") or []:
        if f["id"] not in ids:
            continue
        v = verify_finding(root, f)
        (out_dir / ("%s.json" % f["id"])).write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        verdicts.append(v)
    return verdicts


def self_test():
    import tempfile

    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config.js").write_text("const a = 1;\nconst API_KEY = 'x';\n", encoding="utf-8")
        (root / "package-lock.json").write_text('{"packages": {"node_modules/lodash": {"version": "4.17.20"}}}', encoding="utf-8")
        audit = root / ".dev" / "audit"
        audit.mkdir(parents=True)
        (audit / "findings-merged.json").write_text(json.dumps({
            "findings": [
                {"id": "SEC-001", "severity": "high", "evidence_refs": ["config.js:2"], "verification_mode": "mechanical",
                 "mechanical_assertions": [{"kind": "literal_present", "file": "config.js", "line": 2, "pattern": "API_KEY"}]},
                {"id": "SEC-002", "severity": "medium", "evidence_refs": ["package-lock.json:1"], "verification_mode": "mechanical",
                 "mechanical_assertions": [{"kind": "lockfile_has", "file": "package-lock.json", "package": "left-pad"}]},
                {"id": "SEC-003", "severity": "medium", "evidence_refs": ["x.js:1"], "verification_mode": "mechanical"},
                {"id": "BUG-001", "severity": "high", "evidence_refs": ["config.js:1"], "verification_mode": "adversarial"},
            ],
            "mechanical": ["SEC-001", "SEC-002", "SEC-003"],
        }), encoding="utf-8")
        verdicts = {v["finding_id"]: v for v in run(audit, root)}
        checks.append(("solo mecanicos", set(verdicts) == {"SEC-001", "SEC-002", "SEC-003"}))
        checks.append(("literal confirmado", verdicts["SEC-001"]["verdict"] == "confirmed"))
        checks.append(("lockfile refutado", verdicts["SEC-002"]["verdict"] == "refuted" and verdicts["SEC-002"]["refutation_basis"] == "mechanical_assertion_failed"))
        checks.append(("sin aserciones -> needs_human", verdicts["SEC-003"]["verdict"] == "needs_human"))
        checks.append(("archivos escritos", (audit / "verdicts" / "SEC-001.json").exists()))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/audit")
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    if not (folder / "findings-merged.json").exists():
        print("error: falta %s (corre dedupe_findings.py primero)" % (folder / "findings-merged.json"))
        return 1
    try:
        verdicts = run(folder, Path(args.raiz))
    except (json.JSONDecodeError, OSError) as e:
        print("error: %s" % e)
        return 1
    for v in verdicts:
        print("%s: %s" % (v["finding_id"], v["verdict"]))
    counts = {}
    for v in verdicts:
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print("mecanicos verificados: %d (%s) -> %s" % (len(verdicts), ", ".join("%s %d" % kv for kv in sorted(counts.items())) or "ninguno", folder / "verdicts"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
