#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registra que extensiones del build estan habilitadas en un proyecto.

Las extensiones viven en `reference/extensions/<nombre>/` del plugin: `reglas.md`
(las reglas con id, verificacion, etapas y severidad) y, si es opt-in,
`reglas.opt-in.md` (cinco lineas: que es, que cuesta, la pregunta y el default).
Sin archivo opt-in la extension es siempre-on (hoy: seguridad-owasp).

La decision se guarda UNA vez por proyecto en `.dev/build/extensions.json` y la
escribe este script, nunca un agente. El stack-profiler lee ese archivo y carga solo
las `reglas.md` habilitadas (carga diferida); el implementer y el gate consumen lo que
el profiler vuelca al security-baseline.json, no las reglas.

Uso:
  python extensions_decide.py <raiz> --listar                 preguntas de los opt-in (para la pausa)
  python extensions_decide.py <raiz> --set resiliencia=on tests-de-propiedades=off [--fecha AAAA-MM-DD]
  python extensions_decide.py <raiz> --set-defaults           todo opt-in en off (modo lote sin decision)
  python extensions_decide.py <raiz> --estado                 que hay registrado
  python extensions_decide.py --self-test

`--plugin-root` apunta a la raiz del plugin (default: CLAUDE_PLUGIN_ROOT o la raiz
de este script). Exit 0; 1 ante error de IO o nombre desconocido; con --estado,
exit 2 si no hay decision registrada.
Solo stdlib, Python 3.8+.
"""
from __future__ import print_function

import argparse
import json
import os
import re
import sys
from pathlib import Path

FIELD = re.compile(r"^(Que es|Que cuesta|Pregunta|Default):\s*(.+)$", re.IGNORECASE)


def plugin_root(explicit=None):
    if explicit:
        return Path(explicit)
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]


def catalog(root):
    """{nombre: {"opt_in": bool, "pregunta", "default", "que_es", "que_cuesta"}} desde reference/extensions/."""
    base = Path(root) / "reference" / "extensions"
    out = {}
    if not base.is_dir():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if not (d / "reglas.md").is_file():
            continue
        entry = {"opt_in": False, "pregunta": None, "default": "on", "que_es": None, "que_cuesta": None}
        opt = d / "reglas.opt-in.md"
        if opt.is_file():
            entry["opt_in"] = True
            entry["default"] = "off"
            for line in opt.read_text(encoding="utf-8").splitlines():
                m = FIELD.match(line.strip())
                if m:
                    key = m.group(1).lower().replace(" ", "_")
                    entry[key] = m.group(2).strip()
        out[d.name] = entry
    return out


def decision_path(raiz):
    return Path(raiz) / ".dev" / "build" / "extensions.json"


def load_decision(raiz):
    p = decision_path(raiz)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_decision(raiz, cat, choices, source, fecha=None, previous=None):
    """choices: {nombre: bool} solo para opt-in; las siempre-on quedan enabled."""
    ext = {}
    prev = (previous or {}).get("extensions", {}) if previous else {}
    for name, meta in cat.items():
        if not meta["opt_in"]:
            ext[name] = {"enabled": True, "source": "always_on"}
        elif name in choices:
            ext[name] = {"enabled": bool(choices[name]), "source": source}
        elif name in prev:
            ext[name] = prev[name]
        else:
            ext[name] = {"enabled": meta["default"] == "on", "source": "default"}
    doc = {"version": (previous or {}).get("version", 0) + 1, "fecha": fecha, "extensions": ext}
    p = decision_path(raiz)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def parse_set(items, cat):
    choices = {}
    for it in items:
        if "=" not in it:
            raise ValueError("formato esperado nombre=on|off, recibi %r" % it)
        name, val = it.split("=", 1)
        name, val = name.strip(), val.strip().lower()
        if name not in cat:
            raise ValueError("extension desconocida: %s (hay: %s)" % (name, ", ".join(sorted(cat)) or "ninguna"))
        if not cat[name]["opt_in"]:
            raise ValueError("%s es siempre-on: no se puede apagar" % name)
        if val not in ("on", "off"):
            raise ValueError("%s: el valor tiene que ser on u off" % name)
        choices[name] = val == "on"
    return choices


def print_state(doc):
    for name, e in sorted(doc.get("extensions", {}).items()):
        print("extension: %s %s (%s)" % (name, "on" if e.get("enabled") else "off", e.get("source")))


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--plugin-root", default=None)
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--set", nargs="+", default=None, metavar="NOMBRE=on|off")
    ap.add_argument("--set-defaults", action="store_true")
    ap.add_argument("--estado", action="store_true")
    ap.add_argument("--fecha", default=None)
    args = ap.parse_args(argv)
    cat = catalog(plugin_root(args.plugin_root))
    if not cat:
        print("ERROR: no encuentro reference/extensions/ en el plugin")
        return 1
    if args.listar:
        for name, meta in sorted(cat.items()):
            if meta["opt_in"]:
                print("opt-in: %s" % name)
                print("  que es: %s" % (meta.get("que_es") or ""))
                print("  que cuesta: %s" % (meta.get("que_cuesta") or ""))
                print("  pregunta: %s" % (meta.get("pregunta") or ""))
                print("  default: %s" % meta["default"])
            else:
                print("siempre-on: %s" % name)
        return 0
    if args.set is not None or args.set_defaults:
        try:
            choices = parse_set(args.set or [], cat)
        except ValueError as exc:
            print("ERROR: %s" % exc)
            return 1
        source = "construir_pausa" if args.set else "default"
        doc = write_decision(args.raiz, cat, choices, source, args.fecha, load_decision(args.raiz))
        print_state(doc)
        print("decision -> %s (version %s)" % (decision_path(args.raiz), doc["version"]))
        return 0
    doc = load_decision(args.raiz)
    if not doc:
        print("sin decision registrada: corre --listar y despues --set, o --set-defaults")
        return 2
    print_state(doc)
    return 0


def self_test():
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="ext-"))
    failures = 0
    try:
        ref = tmp / "plugin" / "reference" / "extensions"
        (ref / "seguridad-owasp").mkdir(parents=True)
        (ref / "seguridad-owasp" / "reglas.md").write_text("# siempre on\n", encoding="utf-8")
        (ref / "resiliencia").mkdir()
        (ref / "resiliencia" / "reglas.md").write_text("# reglas\n", encoding="utf-8")
        (ref / "resiliencia" / "reglas.opt-in.md").write_text(
            "# resiliencia\n\nQue es: timeouts y reintentos.\nQue cuesta: poco.\nPregunta: ¿Activamos resiliencia?\nDefault: off\n",
            encoding="utf-8")
        cat = catalog(tmp / "plugin")
        proj = tmp / "proj"
        checks = [
            (set(cat) == {"seguridad-owasp", "resiliencia"}, "catalogo"),
            (cat["seguridad-owasp"]["opt_in"] is False and cat["resiliencia"]["opt_in"] is True, "opt-in por presencia del archivo"),
            (cat["resiliencia"]["pregunta"] == "¿Activamos resiliencia?" and cat["resiliencia"]["default"] == "off", "campos del opt-in"),
        ]
        doc = write_decision(proj, cat, {}, "default", "2026-10-07")
        checks.append((doc["extensions"]["resiliencia"]["enabled"] is False and doc["extensions"]["seguridad-owasp"]["enabled"] is True, "defaults"))
        doc2 = write_decision(proj, cat, parse_set(["resiliencia=on"], cat), "construir_pausa", "2026-10-08", load_decision(proj))
        checks.append((doc2["version"] == 2 and doc2["extensions"]["resiliencia"] == {"enabled": True, "source": "construir_pausa"}, "set on y version"))
        try:
            parse_set(["seguridad-owasp=off"], cat)
            checks.append((False, "apagar siempre-on rechazado"))
        except ValueError:
            checks.append((True, "apagar siempre-on rechazado"))
        try:
            parse_set(["nada=on"], cat)
            checks.append((False, "desconocida rechazada"))
        except ValueError:
            checks.append((True, "desconocida rechazada"))
        for cond, label in checks:
            print("self-test %s: %s" % ("ok" if cond else "FALLO", label))
            failures += 0 if cond else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
