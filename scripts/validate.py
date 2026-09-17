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

3. Todo agente lleva los bloques que el contrato de la suite da por sentados:
   "Frontera de confianza" y "Respuesta al orquestador".
4. Donde una skill publica una tabla de modelo por subagente, la tabla coincide con
   el `model` del frontmatter de cada agente.
5. Todo prefijo de id que los prompts prometen (`"id": "XXX-001"`) lo acepta alguna
   expresion de `scripts/check-artifacts.py`, o esta declarado como no verificado.
   Sin esto, renombrar un id en los prompts deja al verificador atras en silencio
   (fue el caso de SYM-nnn -> LEL-nnn).

`archive/` se ignora. Salida: lista de problemas y exit code 1 si hay alguno.
Uso: python scripts/validate.py [raiz-del-repo]
     python scripts/validate.py --self-test
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

_args = [a for a in sys.argv[1:] if not a.startswith("--")]
ROOT = Path(_args[0] if _args else Path(__file__).resolve().parent.parent).resolve()

REQUIRED_KEYS = {
    "agents": {"name", "description", "tools", "model"},
    "commands": {"description"},
    "skills": {"name", "description"},
}

# Bloques que el resto de la suite da por sentados en CADA agente.
BLOQUES_AGENTE = ("frontera de confianza", "respuesta al orquestador")

MODELOS = {"opus", "sonnet", "haiku"}

# Prefijos de id que los prompts usan y que check-artifacts.py NO verifica (a
# proposito: no cruzan plugins o no viven en los artefactos que revisa). Agregar
# uno aca es una decision consciente; el chequeo existe para que renombrar un id
# no pase inadvertido.
PREFIJOS_NO_VERIFICADOS = {
    "ACT", "ADR", "API", "BUG", "CAP", "CHK", "CTX", "DEF", "DESVIO", "ENT",
    "ENTRY", "EP", "EXC", "GAP", "IMP", "K", "L", "MOD", "NOT", "OWN", "PBC",
    "PROP", "Q", "QST", "REL", "RENT", "RES", "RMOD", "SCR", "SEC", "SPQ", "SRC",
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


# ---------------------------------------------------- invariantes de contenido

def modelo_de_fila(fila):
    """Modelo declarado en una fila de tabla markdown, o None."""
    for celda in fila.split("|"):
        c = celda.strip().strip("*").strip("`").lower()
        if c in MODELOS:
            return c
    return None


def tabla_de_modelos(texto):
    """{agente: modelo} segun las filas `| `agente` | ... | modelo |` de una skill."""
    out = {}
    for linea in texto.splitlines():
        m = re.match(r"^\|\s*`([a-z][\w-]*)`\s*\|", linea)
        if not m:
            continue
        modelo = modelo_de_fila(linea[m.end():])
        if modelo:
            out[m.group(1)] = modelo
    return out


def prefijos_de_id(texto):
    """Prefijos de id que un prompt promete: `"id": "RF-001"` -> RF."""
    return set(re.findall(r'"id":\s*"([A-Z]+)-\d', texto))


def id_regexes():
    """ID_RE de scripts/check-artifacts.py, sin duplicar la fuente."""
    import importlib.util
    ruta = ROOT / "scripts" / "check-artifacts.py"
    if not ruta.exists():
        return None
    spec = importlib.util.spec_from_file_location("check_artifacts", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "ID_RE", {}).values())


def check_bloques_agentes():
    for f in sorted(ROOT.glob("plugins/*/agents/*.md")):
        bajo = f.read_text(encoding="utf-8").lower()
        faltan = [b for b in BLOQUES_AGENTE if b not in bajo]
        if faltan:
            problem(f, "al agente le falta el bloque obligatorio: {}".format(
                ", ".join('"{}"'.format(b) for b in faltan)))


def check_tabla_modelos():
    """Donde una skill publica modelo por subagente, tiene que coincidir."""
    filas = 0
    for skill in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        plugin_dir = skill.parent.parent.parent
        tabla = tabla_de_modelos(skill.read_text(encoding="utf-8"))
        for agente, modelo in sorted(tabla.items()):
            agente_md = plugin_dir / "agents" / (agente + ".md")
            if not agente_md.exists():
                continue  # la fila nombra algo que no es un agente de este plugin
            filas += 1
            data = parse_frontmatter(agente_md) or {}
            real = str(data.get("model", "")).strip().lower()
            if real and real != modelo:
                problem(skill, "la tabla dice '{}' para `{}` y su frontmatter dice '{}'".format(
                    modelo, agente, real))
    return filas


def check_prefijos_de_id():
    """Todo prefijo prometido en los prompts lo acepta el verificador, o esta declarado."""
    regexes = id_regexes()
    if regexes is None:
        problem(ROOT / "scripts" / "check-artifacts.py", "no existe: no pude verificar los prefijos de id")
        return 0
    vistos = set()
    for f in sorted(list(ROOT.glob("plugins/*/agents/*.md"))
                    + list(ROOT.glob("plugins/*/reference/*.md"))):
        vistos |= prefijos_de_id(f.read_text(encoding="utf-8"))
    for prefijo in sorted(vistos - PREFIJOS_NO_VERIFICADOS):
        muestra = "{}-001".format(prefijo)
        if not any(rx.match(muestra) for rx in regexes):
            problem(ROOT / "scripts" / "check-artifacts.py",
                    "los prompts producen ids '{}' y ninguna expresion de ID_RE los acepta "
                    "(agregala, o declara el prefijo en PREFIJOS_NO_VERIFICADOS)".format(muestra))
    return len(vistos)


def self_test():
    fallos = []

    def check(nombre, got, want):
        if got != want:
            fallos.append("{}: {!r} != {!r}".format(nombre, got, want))

    check("tabla con columna de correccion",
          tabla_de_modelos("| `scenario-modeling` | Elabora | opus | opus |"),
          {"scenario-modeling": "opus"})
    check("tabla con modelo en negrita",
          tabla_de_modelos("| `product-mapping` | Mapa | **opus** | opus |"),
          {"product-mapping": "opus"})
    check("tabla con el modelo en la segunda columna",
          tabla_de_modelos("| `stack-profiler` | sonnet | Perfil |"),
          {"stack-profiler": "sonnet"})
    check("fila sin modelo se ignora",
          tabla_de_modelos("| `algo` | Rol | descripcion |"), {})
    check("prefijos de id", prefijos_de_id('{"id": "LEL-001", "x": 1} y "id": "RF-007"'),
          {"LEL", "RF"})

    for f in fallos:
        print("SELF-TEST FALLO ({})".format(f))
    if not fallos:
        print("self-test ok (5 casos: tabla de modelos y prefijos de id).")
    return 1 if fallos else 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()
    n_entries = check_marketplace()
    n_files = check_frontmatters()
    check_bloques_agentes()
    n_filas = check_tabla_modelos()
    n_pref = check_prefijos_de_id()
    mode = "pyyaml" if HAVE_YAML else "reglas de escalar plano (sin pyyaml)"
    print(f"Validados {n_entries} plugins del marketplace y {n_files} frontmatters ({mode}).")
    print(f"Invariantes: bloques obligatorios, {n_filas} fila(s) de tabla de modelos, "
          f"{n_pref} prefijo(s) de id.")
    if problems:
        print(f"\n{len(problems)} problema(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Todo OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
