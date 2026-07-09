#!/usr/bin/env python3
"""Validador del marketplace de plugins.

Chequea lo que Claude Code necesita para cargar los plugins, sin dependencias
externas (usa pyyaml si esta instalado, si no aplica las reglas del escalar plano):

1. `.claude-plugin/marketplace.json` parsea; cada entrada apunta a un directorio
   existente cuyo `plugin.json` parsea y coincide en `name` y `version`.
2. Todo frontmatter YAML de `plugins/*/agents/*.md`, `plugins/*/commands/*.md` y
   `plugins/*/skills/*/SKILL.md` es valido y trae las claves requeridas:
   - agentes: name, description, tools, model
   - comandos: description
   - skills:  name, description
   Regla critica: un valor sin comillas no puede contener `: ` (dos puntos +
   espacio) ni ` #`, ni empezar con un caracter especial de YAML — eso invalida el
   frontmatter completo y el comando/agente no se registra (o pierde sus tools).

`archive/` se ignora. Salida: lista de problemas y exit code 1 si hay alguno.
Uso: python scripts/validate.py [raiz-del-repo]
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore

    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()

REQUIRED_KEYS = {
    "agents": {"name", "description", "tools", "model"},
    "commands": {"description"},
    "skills": {"name", "description"},
}

problems = []


def problem(path, msg):
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path
    problems.append(f"{rel}: {msg}")


def parse_frontmatter(path):
    """Devuelve las claves del frontmatter, o None si es invalido (ya reportado)."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---(\r?\n|$)", text, re.DOTALL)
    if not m:
        problem(path, "sin frontmatter YAML (el archivo no se registra en Claude Code)")
        return None
    fm = m.group(1)

    if HAVE_YAML:
        try:
            data = yaml.safe_load(fm)
        except yaml.YAMLError as e:
            problem(path, f"frontmatter YAML invalido: {str(e).splitlines()[0]}")
            return None
        if not isinstance(data, dict):
            problem(path, "frontmatter YAML no es un mapa clave: valor")
            return None
        return {str(k): v for k, v in data.items()}

    # Sin pyyaml: parser minimo linea a linea con las reglas del escalar plano.
    data = {}
    for i, line in enumerate(fm.splitlines(), start=2):
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue  # continuaciones, listas anidadas o comentarios: fuera de alcance
        lm = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not lm:
            problem(path, f"linea {i}: no es 'clave: valor' ni continuacion valida")
            continue
        key, val = lm.group(1), lm.group(2).strip()
        data[key] = val
        if val.startswith(('"', "'")):
            continue  # escalar citado: seguro
        if ": " in val or val.endswith(":"):
            problem(path, f"linea {i}: ':' + espacio dentro de un valor sin comillas ({key}) — YAML invalido; encerra el valor entre comillas")
        if " #" in val:
            problem(path, f"linea {i}: ' #' dentro de un valor sin comillas ({key}) — YAML lo corta como comentario")
        if val[:1] in "[{&*!|>%@`":
            problem(path, f"linea {i}: el valor de {key} empieza con un caracter especial de YAML; encerralo entre comillas")
    return data


def check_frontmatters():
    count = 0
    for kind, pattern in (
        ("agents", "plugins/*/agents/*.md"),
        ("commands", "plugins/*/commands/*.md"),
        ("skills", "plugins/*/skills/*/SKILL.md"),
    ):
        for f in sorted(ROOT.glob(pattern)):
            count += 1
            data = parse_frontmatter(f)
            if data is None:
                continue
            missing = REQUIRED_KEYS[kind] - set(data)
            if missing:
                problem(f, f"frontmatter sin las claves requeridas: {', '.join(sorted(missing))}")
    return count


def check_marketplace():
    mp_path = ROOT / ".claude-plugin" / "marketplace.json"
    if not mp_path.exists():
        problem(mp_path, "no existe")
        return 0
    try:
        mp = json.loads(mp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        problem(mp_path, f"JSON invalido: {e}")
        return 0

    entries = mp.get("plugins", [])
    for entry in entries:
        name = entry.get("name", "<sin name>")
        src = entry.get("source", "")
        src_dir = (ROOT / src).resolve()
        if not src_dir.is_dir():
            problem(mp_path, f"entrada '{name}': source '{src}' no existe")
            continue
        pj_path = src_dir / ".claude-plugin" / "plugin.json"
        if not pj_path.exists():
            problem(pj_path, f"entrada '{name}': falta plugin.json")
            continue
        try:
            pj = json.loads(pj_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problem(pj_path, f"JSON invalido: {e}")
            continue
        if pj.get("name") != name:
            problem(pj_path, f"name '{pj.get('name')}' no coincide con la entrada del marketplace '{name}'")
        if entry.get("version") and pj.get("version") != entry.get("version"):
            problem(pj_path, f"version '{pj.get('version')}' no coincide con el marketplace ('{entry.get('version')}')")
    return len(entries)


def main():
    n_entries = check_marketplace()
    n_files = check_frontmatters()
    mode = "pyyaml" if HAVE_YAML else "reglas de escalar plano (sin pyyaml)"
    print(f"Validados {n_entries} plugins del marketplace y {n_files} frontmatters ({mode}).")
    if problems:
        print(f"\n{len(problems)} problema(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Todo OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
