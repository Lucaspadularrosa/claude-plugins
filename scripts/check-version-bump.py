#!/usr/bin/env python3
"""Compuerta de release: un plugin que cambia tiene que subir su version.

El cache de plugins de Claude Code se indexa por version
(`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`). Un fix que no sube
la version no le llega a quien ya tiene esa version instalada: `plugin update` no
ve nada nuevo. Este chequeo falla si un commit toca `plugins/X/**` sin cambiar la
`version` de `plugins/X/.claude-plugin/plugin.json`.

Se compara contra el **merge-base** con la rama base, no contra el commit previo,
para que un PR de varios commits se juzgue como un todo.

Quedan exentos los archivos que Claude Code no carga (documentacion del repo):
README.md y PIPELINE.md en la raiz del plugin.

Solo stdlib, Python 3.8+. No modifica nada.

Uso:
  python scripts/check-version-bump.py [--base <ref>]
  python scripts/check-version-bump.py --self-test

Salida: exit 1 si algun plugin cambio sin subir version.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Archivos del directorio de un plugin que no forman parte de lo que se instala.
EXENTOS = {"README.md", "PIPELINE.md"}


def plugins_tocados(changed):
    """plugins/X/... -> {X: [rutas no exentas]}. Logica pura, testeable."""
    out = {}
    for path in changed:
        parts = path.split("/")
        if len(parts) < 3 or parts[0] != "plugins":
            continue
        plugin, resto = parts[1], parts[2:]
        if len(resto) == 1 and resto[0] in EXENTOS:
            continue
        out.setdefault(plugin, []).append(path)
    return out


def faltan_bump(tocados, ver_base, ver_head):
    """Plugins con cambios cuya version no se movio. `ver_*`: {plugin: version}."""
    faltan = []
    for plugin in sorted(tocados):
        antes, ahora = ver_base.get(plugin), ver_head.get(plugin)
        if ahora is None:
            continue  # plugin eliminado: no aplica
        if antes is not None and antes == ahora:
            faltan.append((plugin, ahora, tocados[plugin]))
    return faltan


# --------------------------------------------------------------- plomeria git

def git(*args):
    return subprocess.run(["git"] + list(args), cwd=str(ROOT),
                          capture_output=True, text=True, check=False)


def resolver_base(explicito):
    if explicito:
        return explicito
    import os
    base_ref = os.environ.get("GITHUB_BASE_REF")
    candidatos = ([("origin/" + base_ref)] if base_ref else []) + ["origin/main", "main"]
    for cand in candidatos:
        if git("rev-parse", "--verify", "--quiet", cand).returncode == 0:
            r = git("merge-base", cand, "HEAD")
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
    return None


def version_en(ref, plugin):
    r = git("show", "{}:plugins/{}/.claude-plugin/plugin.json".format(ref, plugin))
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout).get("version")
    except json.JSONDecodeError:
        return None


def version_head(plugin):
    pj = ROOT / "plugins" / plugin / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return None
    try:
        return json.loads(pj.read_text(encoding="utf-8")).get("version")
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ self-test

def self_test():
    fallos = 0

    def check(nombre, got, want):
        nonlocal_ = got == want
        print(("self-test ok (%s)" if nonlocal_ else "SELF-TEST FALLO (%s): %r != %r")
              % ((nombre,) if nonlocal_ else (nombre, got, want)))
        return 0 if nonlocal_ else 1

    cambios = [
        "plugins/a/agents/x.md",          # cuenta
        "plugins/a/README.md",            # exento
        "plugins/b/PIPELINE.md",          # exento (unico cambio de b)
        "plugins/c/skills/s/SKILL.md",    # cuenta
        "scripts/validate.py",            # fuera de plugins/
        "README.md",                      # fuera de plugins/
    ]
    tocados = plugins_tocados(cambios)
    fallos += check("solo plugins con cambios no exentos",
                    sorted(tocados), ["a", "c"])
    fallos += check("README del plugin no cuenta",
                    tocados["a"], ["plugins/a/agents/x.md"])

    base = {"a": "1.0.0", "c": "2.0.0"}
    head = {"a": "1.0.0", "c": "2.1.0"}
    faltan = faltan_bump(tocados, base, head)
    fallos += check("detecta el que no subio version",
                    [f[0] for f in faltan], ["a"])
    fallos += check("no marca el que si subio",
                    [f[0] for f in faltan_bump({"c": ["plugins/c/x"]}, base, head)], [])
    fallos += check("plugin nuevo (sin version base) no falla",
                    faltan_bump({"z": ["plugins/z/x"]}, {}, {"z": "0.1.0"}), [])
    fallos += check("plugin eliminado no falla",
                    faltan_bump({"z": ["plugins/z/x"]}, {"z": "1.0.0"}, {}), [])
    return 1 if fallos else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()

    base = None
    if "--base" in argv:
        i = argv.index("--base")
        base = argv[i + 1] if i + 1 < len(argv) else None
    base = resolver_base(base)
    if not base:
        print("No pude resolver la rama base (proba --base <ref>). No bloqueo.")
        return 0

    r = git("diff", "--name-only", base, "HEAD")
    if r.returncode != 0:
        print("git diff fallo contra {}: {}. No bloqueo.".format(base, r.stderr.strip()))
        return 0
    changed = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    tocados = plugins_tocados(changed)
    if not tocados:
        print("Ningun plugin tocado contra {} ({} archivo(s) cambiado(s)).".format(
            base[:8], len(changed)))
        return 0

    ver_base = {p: version_en(base, p) for p in tocados}
    ver_head = {p: version_head(p) for p in tocados}
    faltan = faltan_bump(tocados, ver_base, ver_head)

    for plugin in sorted(tocados):
        estado = "sin cambio" if any(f[0] == plugin for f in faltan) else "{} -> {}".format(
            ver_base.get(plugin), ver_head.get(plugin))
        print("  {:<22} {:>2} archivo(s)   version: {}".format(
            plugin, len(tocados[plugin]), estado))

    if not faltan:
        print("OK: todo plugin tocado subio su version.")
        return 0

    print("\n{} plugin(s) cambiaron sin subir version:".format(len(faltan)))
    for plugin, ver, archivos in faltan:
        print("  - {} (sigue en {}): {}{}".format(
            plugin, ver, ", ".join(archivos[:3]),
            " y {} mas".format(len(archivos) - 3) if len(archivos) > 3 else ""))
    print("\nSubi la version en plugins/<X>/.claude-plugin/plugin.json y la entrada")
    print("correspondiente de .claude-plugin/marketplace.json (tienen que coincidir).")
    print("Sin bump, el fix no le llega a quien ya tiene esa version instalada.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
