#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desvios del brief -> `cr-input-{brief}.md`, y hallazgos low -> `tech-debt.md`.

Dos derivados que antes redactaba el orquestador a mano leyendo reportes en prosa:

1. `--cr-input`: toma los desvios estructurados que el implementador deja en
   `.dev/build/desvios/{brief_basename}.json` y escribe
   `.dev/build/cr-input-{brief_basename}.md`, listo para `/requerimientos:cambio`.
   Contrato de entrada:
     {"feature_id": "FG-05", "brief_basename": "FG-05-carrito", "desvios": [
        {"id": "DESVIO-1", "requirement_ref": "RF-012/AC-003", "brief_said": "...",
         "built": "...", "why": "...", "evidence": ["commit abc123", "src/x.py:10"]}]}

2. `--tech-debt`: toma los hallazgos `low` de `reviews/{brief}.json` y
   `security/{brief}.json` y los acumula en `.dev/build/tech-debt.md` como `TD-nnn`,
   deduplicando por (archivo de evidencia + categoria): un TD existente del mismo
   tema suma el review de origen en vez de duplicarse. Los `TD-nnn` son consecutivos
   y no se reciclan. Cada entrada lleva una clave oculta `<!-- td-key: ... -->` que
   es lo que permite el dedupe entre corridas.

Uso:
  python render_cr_input.py <raiz> --brief FG-05-carrito [--cr-input] [--tech-debt]
  python render_cr_input.py --self-test

Sin flags hace ambas cosas. Solo stdlib. Exit 0 ok; 2 error de uso/lectura.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

KEY_RE = re.compile(r"<!-- td-key: (.+?) -->")
TD_RE = re.compile(r"^## (TD-(\d+)) — ")


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------- cr-input

def render_cr_input(data):
    fid = data.get("feature_id", "")
    brief = data.get("brief_basename", "")
    lines = ["# Desvios del brief — %s (%s)" % (fid, brief), "",
             "Entrada para `/requerimientos:cambio`: cada desvio describe que decia la linea",
             "de base, que se construyo y por que. O el CR actualiza el requisito, o el desvio",
             "se revierte: codigo y requisitos no divergen en silencio.", ""]
    for d in data.get("desvios") or []:
        lines.append("## %s — %s" % (d.get("id", "DESVIO-?"), d.get("requirement_ref", "sin requisito")))
        lines.append("")
        lines.append("- **Feature**: %s" % fid)
        lines.append("- **Requisito afectado**: %s" % d.get("requirement_ref", ""))
        lines.append("- **Que decia el brief**: %s" % d.get("brief_said", ""))
        lines.append("- **Que se construyo**: %s" % d.get("built", ""))
        lines.append("- **Por que**: %s" % d.get("why", ""))
        ev = d.get("evidence") or []
        lines.append("- **Evidencia**: %s" % (", ".join(ev) if isinstance(ev, list) else ev))
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ tech-debt

def _key(finding):
    refs = finding.get("evidence_refs") or []
    first = str(refs[0]).split(":")[0] if refs else ""
    return "%s|%s" % (first.strip().lower(), str(finding.get("category", "")).strip().lower())


def parse_tech_debt(text):
    """Devuelve (max_num, {key: td_id})."""
    max_num = 0
    keys = {}
    current = None
    for line in text.splitlines():
        m = TD_RE.match(line)
        if m:
            current = m.group(1)
            max_num = max(max_num, int(m.group(2)))
            continue
        k = KEY_RE.search(line)
        if k and current:
            keys[k.group(1)] = current
    return max_num, keys


def append_origin(text, td_id, origin):
    """Suma una linea de origen a un TD existente si todavia no la tiene."""
    if origin in text:
        return text, False
    lines = text.splitlines()
    out = []
    inside = False
    done = False
    for line in lines:
        m = TD_RE.match(line)
        if m:
            if inside and not done:
                out.append("- **Review de origen**: %s" % origin)
                done = True
            inside = m.group(1) == td_id
        out.append(line)
    if inside and not done:
        out.append("- **Review de origen**: %s" % origin)
    return "\n".join(out) + "\n", True


def render_td(num, finding, origin):
    return "\n".join([
        "## TD-%03d — %s" % (num, (finding.get("description") or "").strip().split("\n")[0][:100]),
        "<!-- td-key: %s -->" % _key(finding),
        "- **Que es**: %s" % (finding.get("description") or "").strip(),
        "- **Riesgo**: %s" % (finding.get("impact") or "hallazgo low no corregido en la ronda"),
        "- **Resolucion sugerida**: %s" % (finding.get("proposed_correction") or finding.get("proposed_fix") or ""),
        "- **Review de origen**: %s" % origin,
        "- **Estado**: abierta (%s)" % date.today().isoformat(),
        "",
    ])


def update_tech_debt(build, brief):
    path = build / "tech-debt.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Deuda tecnica\n\n"
    max_num, keys = parse_tech_debt(text)
    added, merged = [], []
    for sub in ("reviews", "security"):
        verdict = load(build / sub / (brief + ".json"))
        if not verdict:
            continue
        for f in verdict.get("findings") or []:
            if f.get("severity") != "low":
                continue
            origin = "%s/%s.json + %s" % (sub, brief, f.get("id", "?"))
            k = _key(f)
            if k in keys:
                text, changed = append_origin(text, keys[k], origin)
                if changed:
                    merged.append((keys[k], f.get("id")))
                continue
            max_num += 1
            td = "TD-%03d" % max_num
            keys[k] = td
            if not text.endswith("\n"):
                text += "\n"
            text += render_td(max_num, f, origin)
            added.append((td, f.get("id")))
    path.write_text(text, encoding="utf-8")
    return path, added, merged


# ------------------------------------------------------------------ self-test

def self_test():
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="cr-input-"))
    failures = 0
    try:
        build = tmp / ".dev" / "build"
        (build / "desvios").mkdir(parents=True)
        (build / "reviews").mkdir()
        (build / "security").mkdir()
        (build / "desvios" / "FG-01-demo.json").write_text(json.dumps({
            "feature_id": "FG-01", "brief_basename": "FG-01-demo",
            "desvios": [{"id": "DESVIO-1", "requirement_ref": "RF-001/AC-002", "brief_said": "a",
                         "built": "b", "why": "c", "evidence": ["commit abc"]}]}), encoding="utf-8")
        out = render_cr_input(load(build / "desvios" / "FG-01-demo.json"))
        if "DESVIO-1 — RF-001/AC-002" not in out or "commit abc" not in out:
            print("SELF-TEST FALLO (cr-input): %s" % out)
            failures += 1
        else:
            print("self-test ok (cr-input)")
        low = {"id": "FG-01/FIND-003", "severity": "low", "category": "convention", "description": "nombre raro",
               "evidence_refs": ["src/a.py:3"], "proposed_correction": "renombrar"}
        (build / "reviews" / "FG-01-demo.json").write_text(json.dumps({"findings": [low, dict(low, id="FG-01/FIND-004", severity="high")]}), encoding="utf-8")
        (build / "security" / "FG-01-demo.json").write_text(json.dumps({"findings": [
            {"id": "FG-01/SGATE-002", "severity": "low", "category": "logging", "description": "log verboso",
             "evidence_refs": ["src/b.py:9"], "proposed_fix": "bajar nivel", "impact": "ruido"}]}), encoding="utf-8")
        path, added, merged = update_tech_debt(build, "FG-01-demo")
        text = path.read_text(encoding="utf-8")
        if len(added) != 2 or "TD-001" not in text or "TD-002" not in text or "FIND-004" in text:
            print("SELF-TEST FALLO (tech-debt alta): %s / %s" % (added, text))
            failures += 1
        else:
            print("self-test ok (tech-debt: 2 TD nuevos, high ignorado)")
        # segunda corrida con el mismo hallazgo desde otro brief: dedupe
        (build / "reviews" / "FG-02-otro.json").write_text(json.dumps({"findings": [dict(low, id="FG-02/FIND-001")]}), encoding="utf-8")
        path, added, merged = update_tech_debt(build, "FG-02-otro")
        text = path.read_text(encoding="utf-8")
        if added or len(merged) != 1 or text.count("## TD-") != 2 or "FG-02/FIND-001" not in text:
            print("SELF-TEST FALLO (dedupe): added=%s merged=%s\n%s" % (added, merged, text))
            failures += 1
        else:
            print("self-test ok (tech-debt: dedupe suma origen)")
        path, added, merged = update_tech_debt(build, "FG-02-otro")
        if added or merged:
            print("SELF-TEST FALLO (idempotencia): added=%s merged=%s" % (added, merged))
            failures += 1
        else:
            print("self-test ok (tech-debt idempotente)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


# ------------------------------------------------------------------------ main

def main(argv):
    if "--self-test" in argv:
        return self_test()
    root = None
    brief = None
    do_cr = "--cr-input" in argv
    do_td = "--tech-debt" in argv
    if not do_cr and not do_td:
        do_cr = do_td = True
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--brief":
            i += 1
            brief = argv[i]
        elif a in ("--cr-input", "--tech-debt"):
            pass
        elif a.startswith("--"):
            print("error: opcion desconocida %s" % a)
            return 2
        else:
            root = a
        i += 1
    if not root or not brief:
        print(__doc__)
        return 2
    build = Path(root) / ".dev" / "build"
    if do_cr:
        data = load(build / "desvios" / (brief + ".json"))
        if data is None:
            print("cr-input: sin desvios declarados (%s no existe)" % (build / "desvios" / (brief + ".json")))
        elif not data.get("desvios"):
            print("cr-input: 0 desvios, no se genera archivo")
        else:
            out = build / ("cr-input-%s.md" % brief)
            out.write_text(render_cr_input(data), encoding="utf-8")
            print("cr-input: %s (%d desvio(s)) -> sugerir /requerimientos:cambio %s" % (out, len(data["desvios"]), out))
    if do_td:
        path, added, merged = update_tech_debt(build, brief)
        print("tech-debt: %s (+%d nuevos, %d fusionados)" % (path, len(added), len(merged)))
        for td, fid in added:
            print("  %s <- %s" % (td, fid))
        for td, fid in merged:
            print("  %s += %s" % (td, fid))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
