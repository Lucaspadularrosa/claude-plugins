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
4. Donde un documento publica modelo por subagente (el `SKILL.md` de la skill o el
   `PIPELINE.md` de diseno), el `model` del frontmatter esta entre los que nombra.
   PIPELINE.md no lo carga ningun comando, pero declara modelos igual: si queda
   atras, el orquestador termina con dos fuentes en conflicto.
   Como AVISO (no bloquea), la prosa de esos documentos y de `modes/` que fije
   para un agente un modelo que ninguna tabla declara: es el hueco que dejaba el
   punto anterior, que solo lee filas de tabla.
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
warnings = []


def _rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def warn(path, msg):
    warnings.append(f"{_rel(path)}: {msg}")


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

def modelos_de_fila(fila):
    """Modelos que una fila de tabla markdown nombra para un agente.

    Las declaraciones calificadas son legitimas y frecuentes: `agente (opus)`,
    `opus (plan: sonnet)`, `sonnet (opus si A01/A02/A07)`,
    `(sonnet/opus/sonnet por modo)`. No se intenta adivinar cual es el primario:
    el invariante es que el `model` del frontmatter este ENTRE los que el
    documento nombra. Una fila que nombra solo 'sonnet' para un agente cuyo
    frontmatter dice 'opus' es la deriva que se quiere atrapar.
    """
    return set(re.findall(r"[a-z]+", fila.lower())) & MODELOS


def tabla_de_modelos(texto):
    """{agente: {modelos}} segun las filas `| `agente` ... |` de una tabla.

    Se mira la fila entera, no solo lo que sigue al nombre: hay tablas que meten
    el modelo en la misma celda del agente
    (`| `baseline-reconstruction` (sonnet/opus/sonnet por modo) | ...`).
    """
    out = {}
    for linea in texto.splitlines():
        m = re.match(r"^\|\s*`([a-z][\w-]+)`", linea)
        if not m:
            continue
        resto = linea[:m.start(1)] + linea[m.end():]
        modelos = modelos_de_fila(resto)
        if modelos:
            out[m.group(1)] = modelos
    return out


def docs_con_tabla():
    """(documento, carpeta del plugin) de todo lo que puede declarar modelos.

    PIPELINE.md no lo carga ningun comando, pero es el documento de diseno del
    pipeline y declara modelo por agente: si queda atras, el orquestador termina
    con dos fuentes en conflicto igual.
    """
    for skill in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        yield skill, skill.parent.parent.parent
    for pl in sorted(ROOT.glob("plugins/*/PIPELINE.md")):
        yield pl, pl.parent


def check_tabla_modelos():
    """El `model` del frontmatter tiene que estar entre los que el doc nombra."""
    filas = 0
    for doc, plugin_dir in docs_con_tabla():
        for agente, modelos in sorted(tabla_de_modelos(doc.read_text(encoding="utf-8")).items()):
            agente_md = plugin_dir / "agents" / (agente + ".md")
            if not agente_md.exists():
                continue  # la fila nombra algo que no es un agente de este plugin
            filas += 1
            real = str((parse_frontmatter(agente_md) or {}).get("model", "")).strip().lower()
            if real and real not in modelos:
                problem(doc, "nombra {} para `{}` y su frontmatter dice '{}'".format(
                    " y ".join("'%s'" % m for m in sorted(modelos)), agente, real))
    return filas


def mapa_declarado():
    """{agente: {modelos}} segun todas las tablas verificables de la suite."""
    out = {}
    for doc, plugin_dir in docs_con_tabla():
        for agente, modelos in tabla_de_modelos(doc.read_text(encoding="utf-8")).items():
            if (plugin_dir / "agents" / (agente + ".md")).exists():
                out.setdefault(agente, set()).update(modelos)
    return out


def docs_con_prosa():
    """Documentos donde la prosa puede fijar un modelo (no solo las tablas)."""
    for pat in ("plugins/*/skills/*/SKILL.md", "plugins/*/PIPELINE.md",
                "plugins/*/skills/*/modes/*.md"):
        for f in sorted(ROOT.glob(pat)):
            yield f


def check_prosa_modelos(declarado):
    """AVISO: prosa que fija para un agente un modelo que ninguna tabla declara.

    No bloquea. La prosa describe modos legitimos ("modo nucleo con sonnet") que
    una tabla puede no publicar todavia, asi que un aviso no es necesariamente un
    defecto. Pero si la tabla es el contrato, toda prosa que la contradiga es
    candidata a deriva y tiene que verse: el invariante de tablas no la cubre.
    """
    n = 0
    for doc in docs_con_prosa():
        for i, linea in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("|"):
                continue  # las filas de tabla las cubre check_tabla_modelos
            modelos = set(re.findall(r"[a-z]+", linea.lower())) & MODELOS
            if not modelos:
                continue
            for agente in sorted(set(re.findall(r"[`\[]([a-z][\w-]+)[`\]]", linea))):
                if agente in declarado and not (modelos & declarado[agente]):
                    warn(doc, "linea {}: la prosa fija {} para `{}`, y las tablas "
                              "declaran {}".format(i, "/".join(sorted(modelos)), agente,
                                                   "/".join(sorted(declarado[agente]))))
                    n += 1
    return n

# `model: X` fija un modelo concreto. En un SKILL.md es correcto (la skill es el
# orquestador: da la orden en la llamada Task). En un PIPELINE.md, que es diseno y
# no se carga en runtime, es como nace una copia que despues deriva: fue
# exactamente el caso de requirements-pipeline/PIPELINE.md, que quedo mandando el
# lazo de correccion a sonnet cuando la tabla ya decia opus.
MODELO_LITERAL = re.compile(r"`model:\s*(opus|sonnet|haiku)`")


def check_modelo_fijado_en_diseno():
    """AVISO: un PIPELINE.md que fija un modelo concreto en vez de citar la tabla."""
    n = 0
    for doc in sorted(ROOT.glob("plugins/*/PIPELINE.md")):
        for i, linea in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            m = MODELO_LITERAL.search(linea)
            if m:
                warn(doc, "linea {}: fija `model: {}` en el documento de diseno; "
                          "cita la tabla de la skill en vez de copiar el modelo".format(
                              i, m.group(1)))
                n += 1
    return n

# Un plugin no alcanza los archivos de otro por ruta relativa: en una instalacion
# normal cada plugin vive en `.../cache/<marketplace>/<nombre>/<version>/`, asi que
# `${CLAUDE_PLUGIN_ROOT}/../<otro>` no resuelve (falta el nivel de version y el
# directorio se llama por el NOMBRE del plugin, no por la carpeta del repo). Solo
# funciona cuando el marketplace es un directorio local, que es como lo ve quien
# desarrolla la suite: falla justo para todos los demas. Lo compartido se expone
# como ejecutable en `bin/`, que Claude Code pone en el PATH.
RUTA_CRUZADA = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/\.\./")


def check_rutas_cruzadas():
    for pat in ("plugins/*/skills/*/SKILL.md", "plugins/*/skills/*/modes/*.md",
                "plugins/*/agents/*.md", "plugins/*/commands/*.md"):
        for f in sorted(ROOT.glob(pat)):
            for i, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if RUTA_CRUZADA.search(linea):
                    problem(f, "linea {}: alcanza otro plugin por ruta relativa "
                               "(${{CLAUDE_PLUGIN_ROOT}}/../); solo resuelve con un "
                               "marketplace de directorio local. Expone lo compartido "
                               "como ejecutable en bin/ del plugin que lo provee".format(i))

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

    check("columna de correccion", tabla_de_modelos(
          "| `scenario-modeling` | Elabora | opus | opus |"), {"scenario-modeling": {"opus"}})
    check("modelo en negrita", tabla_de_modelos(
          "| `product-mapping` | Mapa | **opus** | opus |"), {"product-mapping": {"opus"}})
    check("modelo suelto en una celda", tabla_de_modelos(
          "| `stack-profiler` | sonnet | Perfil |"), {"stack-profiler": {"sonnet"}})
    check("declaracion calificada", tabla_de_modelos(
          "| `feature-implementer` | opus (plan: sonnet) | Construye |"),
          {"feature-implementer": {"opus", "sonnet"}})
    check("modelo entre parentesis tras una palabra", tabla_de_modelos(
          "| `bug-hunter` | agente (opus) | correctitud |"), {"bug-hunter": {"opus"}})
    check("multi-modo en la celda del nombre", tabla_de_modelos(
          "| `baseline-reconstruction` (sonnet/opus/sonnet por modo) | Emite |"),
          {"baseline-reconstruction": {"opus", "sonnet"}})
    check("fila sin modelo se ignora", tabla_de_modelos(
          "| `algo` | Rol | descripcion |"), {})
    check("modelo fijado en prosa de diseno",
          bool(MODELO_LITERAL.search("(invocado con `model: sonnet`), con tope de 3")), True)
    check("mencion de modelo sin fijarlo no cuenta",
          bool(MODELO_LITERAL.search("el lazo de correccion va en opus")), False)
    check("prefijos de id", prefijos_de_id('{"id": "LEL-001", "x": 1} y "id": "RF-007"'),
          {"LEL", "RF"})

    for f in fallos:
        print("SELF-TEST FALLO ({})".format(f))
    if not fallos:
        print("self-test ok (10 casos: tablas, prosa de diseno y prefijos de id).")
    return 1 if fallos else 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()
    n_entries = check_marketplace()
    n_files = check_frontmatters()
    check_bloques_agentes()
    n_filas = check_tabla_modelos()
    n_prosa = check_prosa_modelos(mapa_declarado())
    check_modelo_fijado_en_diseno()
    check_rutas_cruzadas()
    n_pref = check_prefijos_de_id()
    mode = "pyyaml" if HAVE_YAML else "reglas de escalar plano (sin pyyaml)"
    print(f"Validados {n_entries} plugins del marketplace y {n_files} frontmatters ({mode}).")
    print(f"Invariantes: bloques obligatorios, {n_filas} fila(s) de tabla de modelos, "
          f"{n_pref} prefijo(s) de id.")
    if warnings:
        print("")
        print(f"{len(warnings)} aviso(s) — prosa que fija un modelo fuera de las "
              f"tablas (no bloquea; revisa si es un modo legitimo o deriva):")
        for w in warnings:
            print(f"  ! {w}")
    if problems:
        print(f"\n{len(problems)} problema(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Todo OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
