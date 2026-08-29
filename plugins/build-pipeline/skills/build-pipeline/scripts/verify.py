#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificacion determinista de una feature: test, lint y audit de dependencias.

Corre una sola vez los comandos del perfil de stack (`commands.test`, `commands.lint`)
y el `tooling.dependency_audit` de la base de seguridad, y deja el resultado en
`.dev/build/verification/{brief_basename}.json`. El reviewer y el gate consumen ese
JSON en vez de re-correr la suite y parsear logs con un modelo: la suite corre una
vez por ronda, el resultado es el mismo para todos los agentes y ningun agente
"cree" en un reporte, lee un exit code.

Contrato del artefacto:
  {
    "version": 1, "brief_basename": "FG-05-carrito", "generated_at": "...",
    "git_sha": "abc123", "branch": "feature/carrito",
    "commands": {
      "test":             {"command": "...", "exit_code": 0, "passed": true, "duration_s": 1.2, "tail": ["..."]},
      "lint":             {"command": "...", "exit_code": 0, "passed": true, ...},
      "dependency_audit": {"command": "...", "exit_code": 0, "passed": true,
                           "severities": {"critical": 0, "high": 0, "moderate": 0, "low": 0}, ...}
    },
    "passed": true
  }

Un comando ausente en el perfil queda como `{"command": null, "passed": null}` con un
aviso. El audit "pasa" si no reporta vulnerabilidades critical/high (el exit code de
los auditores varia por ecosistema, por eso se normaliza por severidad).

Solo stdlib, Python 3.8+. Solo ejecuta los comandos del perfil: nunca un comando
sugerido por el codigo del proyecto.

Uso:
  python verify.py <raiz-del-proyecto> --brief FG-05-carrito [--solo test lint audit]
                   [--timeout 900] [--cwd <worktree>]
  python verify.py --self-test

Exit 0: todo lo corrido paso. Exit 1: algo fallo. Exit 2: error de uso o perfil.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SEVERITIES = ("critical", "high", "moderate", "low")
TAIL_LINES = 40


def fail(msg):
    print("error: %s" % msg)
    return 2


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def run(command, cwd, timeout):
    start = time.time()
    try:
        proc = subprocess.run(command, shell=True, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")) \
            + "\n[timeout tras %ss]" % timeout
        code = 124
    lines = out.splitlines()
    return code, out, lines[-TAIL_LINES:], round(time.time() - start, 2)


def _walk(obj, found):
    """Recorre un JSON de auditoria y acumula conteos por severidad, sea cual sea el
    ecosistema (npm: metadata.vulnerabilities; pip-audit: vulns por dependencia;
    composer: advisories; cargo-audit: vulnerabilities.list)."""
    if isinstance(obj, dict):
        # npm audit --json (v7+): {"metadata": {"vulnerabilities": {"high": 2, ...}}}
        vul = obj.get("vulnerabilities")
        if isinstance(vul, dict) and all(isinstance(v, int) for v in vul.values()):
            for k, v in vul.items():
                if k in SEVERITIES:
                    found[k] += v
            return
        sev = obj.get("severity")
        if isinstance(sev, str) and sev.lower() in SEVERITIES and ("id" in obj or "title" in obj or "name" in obj or "via" in obj):
            found[sev.lower()] += 1
        for v in obj.values():
            _walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, found)


def normalize_audit(output):
    found = {k: 0 for k in SEVERITIES}
    parsed = None
    text = output.strip()
    # el JSON puede venir precedido de warnings del gestor: buscar la primera llave
    for start in (text.find("{"), text.find("[")):
        if start >= 0:
            try:
                parsed = json.loads(text[start:])
                break
            except ValueError:
                continue
    if parsed is not None:
        _walk(parsed, found)
        if sum(found.values()) == 0 and isinstance(parsed, list):
            # pip-audit: [{"name":..., "vulns":[{"id":..., "fix_versions":[...]}]}] sin severidad
            for dep in parsed:
                if isinstance(dep, dict):
                    found["high"] += len(dep.get("vulns") or [])
        return found, True
    # sin JSON: contar menciones textuales (npm audit sin --json, cargo audit, etc.)
    for sev in SEVERITIES:
        found[sev] += len(re.findall(r"\b%s\b" % sev, text, flags=re.IGNORECASE))
    return found, False


def git(cwd, *args):
    try:
        return subprocess.run(["git"] + list(args), cwd=str(cwd), capture_output=True,
                              text=True).stdout.strip()
    except OSError:
        return ""


def verify(root, brief, only, timeout, cwd):
    root = Path(root)
    cwd = Path(cwd) if cwd else root
    dev = root / ".dev" / "build"
    profile = load_json(dev / "stack-profile.json")
    if profile is None:
        return None, "no se pudo leer %s" % (dev / "stack-profile.json")
    baseline = load_json(dev / "security-baseline.json") or {}
    cmds = profile.get("commands") or {}
    wanted = {
        "test": (cmds.get("test") or {}).get("command"),
        "lint": (cmds.get("lint") or {}).get("command"),
        "dependency_audit": ((baseline.get("tooling") or {}).get("dependency_audit") or {}).get("command"),
    }
    aliases = {"audit": "dependency_audit"}
    selected = set(aliases.get(o, o) for o in only) if only else set(wanted)

    result = {
        "version": 1,
        "brief_basename": brief,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": git(cwd, "rev-parse", "--short", "HEAD") or None,
        "branch": git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or None,
        "commands": {},
        "warnings": [],
        "passed": True,
    }
    for name, command in wanted.items():
        entry = {"command": command, "exit_code": None, "passed": None, "duration_s": None, "tail": []}
        if name not in selected:
            entry["skipped"] = True
        elif not command:
            result["warnings"].append("sin comando de %s en el perfil" % name)
        else:
            code, out, tail, dur = run(command, cwd, timeout)
            entry.update({"exit_code": code, "duration_s": dur, "tail": tail})
            if name == "dependency_audit":
                sev, structured = normalize_audit(out)
                entry["severities"] = sev
                entry["structured_output"] = structured
                entry["passed"] = (sev["critical"] + sev["high"]) == 0 and code != 124
            else:
                entry["passed"] = code == 0
            if entry["passed"] is False:
                result["passed"] = False
        result["commands"][name] = entry

    outdir = dev / "verification"
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / (brief + ".json")
    outpath.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return outpath, result


def summarize(result):
    parts = []
    for name, e in result["commands"].items():
        if e.get("skipped"):
            continue
        state = "sin comando" if e["passed"] is None else ("ok" if e["passed"] else "FALLO exit %s" % e["exit_code"])
        if name == "dependency_audit" and e.get("severities"):
            s = e["severities"]
            state += " (critical %d, high %d, moderate %d, low %d)" % (s["critical"], s["high"], s["moderate"], s["low"])
        parts.append("%s: %s" % (name, state))
    return "; ".join(parts)


# ------------------------------------------------------------------ self-test

def self_test():
    import shutil
    import tempfile

    py = sys.executable.replace("\\", "/")
    failures = 0
    for lint_ok in (True, False):
        tmp = Path(tempfile.mkdtemp(prefix="verify-"))
        try:
            build = tmp / ".dev" / "build"
            build.mkdir(parents=True)
            (build / "stack-profile.json").write_text(json.dumps({
                "version": 1,
                "commands": {
                    "test": {"command": '"%s" -c "print(\'1 passed\')"' % py},
                    "lint": {"command": '"%s" -c "import sys; sys.exit(%d)"' % (py, 0 if lint_ok else 1)},
                },
            }), encoding="utf-8")
            audit_json = json.dumps({"metadata": {"vulnerabilities": {"info": 0, "low": 1, "moderate": 0, "high": 0, "critical": 0}}})
            audit_script = tmp / "audit.py"
            audit_script.write_text("print(%r)\n" % audit_json, encoding="utf-8")
            (build / "security-baseline.json").write_text(json.dumps({
                "tooling": {"dependency_audit": {"command": '"%s" "%s"' % (py, str(audit_script).replace("\\", "/"))}},
            }), encoding="utf-8")
            path, res = verify(tmp, "FG-01-demo", [], 60, None)
            ok = path is not None and res["passed"] == lint_ok \
                and res["commands"]["dependency_audit"]["severities"]["low"] == 1 \
                and res["commands"]["dependency_audit"]["passed"] is True \
                and res["commands"]["test"]["passed"] is True \
                and json.loads(path.read_text(encoding="utf-8"))["brief_basename"] == "FG-01-demo"
            label = "lint ok" if lint_ok else "lint falla"
            if ok:
                print("self-test ok (%s): passed=%s" % (label, res["passed"]))
            else:
                print("SELF-TEST FALLO (%s): %s" % (label, json.dumps(res)))
                failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # normalizacion textual
    sev, structured = normalize_audit("found 2 vulnerabilities (1 high, 1 critical)")
    if structured or sev["high"] != 1 or sev["critical"] != 1:
        print("SELF-TEST FALLO (audit textual): %s" % sev)
        failures += 1
    else:
        print("self-test ok (audit textual)")
    return 1 if failures else 0


# ------------------------------------------------------------------------ main

def main(argv):
    if "--self-test" in argv:
        return self_test()
    root = None
    brief = None
    only = []
    timeout = 900
    cwd = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--brief":
            i += 1
            brief = argv[i]
        elif a == "--solo":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                only.append(argv[i])
                i += 1
            continue
        elif a == "--timeout":
            i += 1
            timeout = int(argv[i])
        elif a == "--cwd":
            i += 1
            cwd = argv[i]
        elif a.startswith("--"):
            return fail("opcion desconocida %s" % a)
        else:
            root = a
        i += 1
    if not root or not brief:
        return fail("uso: verify.py <raiz> --brief <brief_basename> [--solo test lint audit] [--cwd <worktree>]")
    path, result = verify(root, brief, only, timeout, cwd)
    if path is None:
        return fail(result)
    print("verificacion: %s" % path)
    print(summarize(result))
    for w in result["warnings"]:
        print("aviso: %s" % w)
    print("RESULTADO: %s" % ("PASSED" if result["passed"] else "FAILED"))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
