#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Version del plugin cargado y avisos de desfase, en una linea y sin tokens.

Script transversal de la suite (vive en requirements-pipeline; los plugins hermanos
lo invocan por la ruta `${CLAUDE_PLUGIN_ROOT}/../requirements-pipeline/...`).
Reemplaza el "Paso 0" que cada skill hacia a mano: leer plugin.json, comparar con
el pipeline_version de los artefactos previos y mirar si el marketplace local tiene
una version mas nueva que la cargada.

Salida (stdout):
  pipeline_version: X.Y.Z                  siempre, primera linea: pasasela a los subagentes
  aviso: ...                                 cero o mas lineas, informativas (nunca compuerta)

Avisos que emite:
  - artefacto previo generado con otra version (o sin version = anterior al versionado)
  - marketplace local con una version mas nueva que la cargada: reiniciar la sesion

Solo stdlib, Python 3.8+. Exit 0 siempre, salvo que no pueda leer plugin.json (exit 1).

Uso:
  python check_pipeline_version.py --plugin-root "${CLAUDE_PLUGIN_ROOT}" \
      [--artefacto .dev/requirements/changelog.json .dev/requirements/lel.json ...]
  python check_pipeline_version.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        return None


def artifact_version(path):
    """pipeline_version de un artefacto: raiz, metadata, o ultima entrada del changelog."""
    doc = load(path)
    if not isinstance(doc, dict):
        return None, False
    if "entries" in doc and isinstance(doc.get("entries"), list):
        entries = doc["entries"]
        if not entries:
            return None, False
        return entries[-1].get("pipeline_version"), True
    if "pipeline_version" in doc:
        return doc.get("pipeline_version"), True
    meta = doc.get("metadata") or {}
    if "pipeline_version" in meta:
        return meta.get("pipeline_version"), True
    return None, True


def marketplace_version(plugin_root, plugin_name, known_path):
    """Version del plugin en su marketplace local, si es un directorio accesible."""
    known = load(known_path) if known_path else None
    if not isinstance(known, dict):
        return None
    candidates = []
    for entry in known.values():
        src = (entry or {}).get("source") or {}
        path = src.get("path") if isinstance(src, dict) else None
        if not path:
            continue
        mp = Path(path).expanduser() / ".claude-plugin" / "marketplace.json"
        candidates.append(mp)
    for mp in candidates:
        doc = load(mp)
        if not isinstance(doc, dict):
            continue
        for p in doc.get("plugins") or []:
            if p.get("name") == plugin_name:
                return p.get("version")
    return None


def run(plugin_root, artifacts, known_path, quiet=False):
    manifest = load(Path(plugin_root) / ".claude-plugin" / "plugin.json")
    if not isinstance(manifest, dict) or not manifest.get("version"):
        if not quiet:
            print("ERROR: no se pudo leer %s/.claude-plugin/plugin.json" % plugin_root)
        return 1, None, []
    loaded = str(manifest["version"])
    name = manifest.get("name")
    avisos = []
    for art in artifacts or []:
        if not Path(art).is_file():
            continue
        ver, present = artifact_version(art)
        if not present:
            continue
        if ver in (None, "null", ""):
            avisos.append("%s no tiene pipeline_version (anterior al versionado): revisa que los contratos no hayan cambiado" % art)
        elif str(ver) != loaded:
            avisos.append("%s se genero con v%s y estas corriendo v%s: revisa que los contratos no hayan cambiado antes de seguir" % (art, ver, loaded))
    mv = marketplace_version(plugin_root, name, known_path)
    if mv and str(mv) != loaded:
        avisos.append("el marketplace local tiene %s v%s y la sesion cargo v%s: el update requiere REINICIAR la sesion" % (name, mv, loaded))
    if not quiet:
        print("pipeline_version: %s" % loaded)
        for a in avisos:
            print("aviso: %s" % a)
    return 0, loaded, avisos


def self_test():
    import shutil
    import tempfile
    failures = 0

    def check(cond, label):
        nonlocal failures
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))
        if not cond:
            failures += 1

    tmp = Path(tempfile.mkdtemp(prefix="check-version-"))
    try:
        root = tmp / "plugin"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "demo", "version": "2.5.0"}), encoding="utf-8")
        (tmp / "lel.json").write_text(json.dumps({"version": 1, "metadata": {"pipeline_version": "2.4.0"}}), encoding="utf-8")
        (tmp / "changelog.json").write_text(json.dumps({"entries": [{"id": "DSC-001", "pipeline_version": "2.5.0"}]}), encoding="utf-8")
        (tmp / "viejo.json").write_text(json.dumps({"version": 1, "pipeline_version": None}), encoding="utf-8")
        mk = tmp / "market"
        (mk / ".claude-plugin").mkdir(parents=True)
        (mk / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"plugins": [{"name": "demo", "version": "2.6.0"}]}), encoding="utf-8")
        known = tmp / "known.json"
        known.write_text(json.dumps({"mk": {"source": {"source": "directory", "path": str(mk)}}}), encoding="utf-8")

        code, loaded, avisos = run(root, [str(tmp / "lel.json"), str(tmp / "changelog.json"), str(tmp / "viejo.json"), str(tmp / "no-existe.json")], known, quiet=True)
        check(code == 0 and loaded == "2.5.0", "lee la version cargada")
        text = " | ".join(avisos)
        check("lel.json se genero con v2.4.0" in text, "detecta artefacto con otra version")
        check("changelog.json" not in text, "changelog con la misma version no avisa")
        check("no tiene pipeline_version" in text, "detecta artefacto sin version")
        check("REINICIAR" in text, "detecta marketplace local mas nuevo")
        code, _, _ = run(tmp / "nada", [], None, quiet=True)
        check(code == 1, "sin plugin.json -> exit 1")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plugin-root", default=None, help="raiz del plugin (default: CLAUDE_PLUGIN_ROOT o la raiz de este script)")
    ap.add_argument("--artefacto", nargs="*", default=[], help="artefactos previos a comparar (changelog.json, lel.json, tasks.json...)")
    ap.add_argument("--known-marketplaces", default=str(Path.home() / ".claude" / "plugins" / "known_marketplaces.json"))
    args = ap.parse_args(argv)
    import os
    root = args.plugin_root or os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[3])
    code, _, _ = run(root, args.artefacto, args.known_marketplaces)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
