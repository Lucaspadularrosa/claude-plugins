#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista del indice de `.dev/`: genera `.dev/README.md`.

Un agente (o humano) nuevo se orienta leyendo este indice en vez de explorar
megabytes de artefactos: layout con una linea por archivo (que es, version vigente,
tamano), estado por feature FG-xx (incluidos los stubs del product-map, que explican
los huecos intencionales de numeracion) e INC/CR pendientes del changelog.

Derivado y determinista: mismo `.dev/` -> mismo README; sin tokens de modelo, sin
red, sin dependencias. Nunca se edita a mano — lo regenera el orquestador de cada
pipeline (requerimientos, planificacion, build, recovery) en su paso de cierre.

Ademas señala higiene del layout: archivos fuera del layout estandar de la suite y
vistas `.md` derivadas cuyo encabezado no coincide con la version del `.json`.

Solo stdlib, Python 3.8+. Solo escribe el README.

Uso:
  python render_index.py [carpeta-dev] [--salida ARCHIVO]
  python render_index.py --self-test

  carpeta-dev  por defecto .dev
  --salida     por defecto <carpeta-dev>/README.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ------------------------------------------------------- layout conocido

# Descripcion por archivo conocido, por subcarpeta de .dev/.
KNOWN = {
    "requirements": {
        "source-inventory.json": "inventario de secciones de las fuentes (acumulativo)",
        "lel-candidates.json": "candidatos a simbolos del LEL",
        "supporting-context.json": "contexto de soporte (no-LEL) para etapas posteriores",
        "lel.json": "Lexico Extendido del Lenguaje (canonico)",
        "lel-inspection.json": "inspeccion del LEL (veredicto)",
        "stakeholder-questions.json": "cuestionario al stakeholder",
        "stakeholder-answers.md": "respuestas del stakeholder (una por QST-xxx)",
        "product-map.json": "mapa del producto: features y stubs con estado (canonico)",
        "changelog.json": "historia de la linea de base: DSC/INC/CR/REC con veredictos y versiones",
        "scenarios.json": "escenarios elaborados (canonico, acumulativo)",
        "requirements.json": "requisitos funcionales y no funcionales (canonico, acumulativo)",
        "requirements-inspection.json": "inspeccion de los requisitos (veredicto)",
        "data-model.json": "modelo de datos (canonico, acumulativo)",
        "technical-design.json": "arquitectura, API, pantallas y ADRs (canonico, acumulativo)",
        "design-inspection.json": "inspeccion del diseno (veredicto)",
    },
    "plan": {
        "tasks.json": "tareas trazables a los requisitos (canonico)",
        "execution-plan.json": "ronda de contratos + lotes paralelos de features (canonico)",
        "plan-inspection.json": "inspeccion del plan (veredicto)",
        "progress.json": "estado de ejecucion del plan (lo actualiza el build)",
    },
    "build": {
        "stack-profile.json": "perfil de stack del proyecto (por evidencia)",
        "security-baseline.json": "base de seguridad del stack (superficie, OWASP, tooling)",
        "tech-debt.md": "deuda tecnica acumulada (TD-nnn: hallazgos low no corregidos)",
    },
    "audit": {
        "findings-bugs.json": "hallazgos crudos de correctitud",
        "findings-security.json": "hallazgos crudos de seguridad",
        "findings-improvements.json": "hallazgos crudos de mejoras",
        "audit-report.json": "reporte consolidado y verificado de la auditoria",
        "audit-report.md": "reporte de auditoria legible",
    },
    "recovery": {
        "code-inventory.json": "foto estructural de la app",
        "behavior-map.json": "que hace la app, con evidencia archivo:linea",
        "state-report.json": "estado real: completo / a medias / muerto + huecos",
        "owner-questions.json": "cuestionario para el dueño",
        "owner-answers.md": "respuestas del dueño (una por OWN-xxx)",
    },
    "manual": {
        "README.md": "indice del manual de usuario (derivado)",
    },
    "features": {},
    "cards": {
        "index.json": "contador de ids de tarjeta cuando no hay product-map",
    },
}

# .md derivados por script: gemelo legible de su .json canonico.
DERIVED_MD = {
    "requirements": ["lel", "product-map", "scenarios", "requirements", "data-model", "technical-design"],
    "plan": ["tasks", "execution-plan"],
}

# .md que escriben los propios subagentes (resumen legible del veredicto).
AGENT_MD = {
    "requirements": ["lel-inspection", "requirements-inspection", "design-inspection", "stakeholder-questions"],
    "plan": ["plan-inspection"],
    "recovery": ["code-inventory", "behavior-map", "state-report", "owner-questions"],
}

# Prefijos de archivo conocidos (nombre variable).
PREFIXES = {
    "build": [("cr-input-", "desvios del brief declarados, listos para /requerimientos:cambio")],
    "audit": [("cr-input-", "hallazgos elegidos, listos para /requerimientos:cambio")],
    "requirements": [],
}

SUBDIRS = {
    ("requirements", "sources"): "fuentes archivadas (documentos, vision, entrevistas, CRs)",
    ("build", "reviews"): "veredictos de review por feature (unica fuente de verdad)",
    ("build", "security"): "veredictos de seguridad (piso OWASP) por feature",
    ("audit", "history"): "corridas de auditoria anteriores archivadas",
    ("cards", "sources"): "fuente archivada de cada tarjeta del camino rapido",
}

DIR_ORDER = ["requirements", "plan", "cards", "features", "build", "manual", "recovery", "audit"]

_HEADER_RE = re.compile(r"Derivado de `?([\w.\-]+\.json)`? version (\S+)")


def kb(path):
    try:
        return "%d KB" % max(1, path.stat().st_size // 1024)
    except OSError:
        return "? KB"


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def json_version(path, cache):
    if path not in cache:
        data = load_json(path)
        cache[path] = data.get("version") if isinstance(data, dict) else None
    return cache[path]


def card_status(path):
    """`status` de una tarjeta del camino rapido (drafted|built|promoted)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        return "ilegible"
    return data.get("status") or "drafted" if isinstance(data, dict) else "ilegible"


def md_header_version(path):
    """Version declarada en el encabezado 'Derivado de <json> version N' (o None)."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
    except OSError:
        return None
    m = _HEADER_RE.search(head)
    return m.group(2) if m else None


def describe(dirname, path, vcache):
    """(descripcion, aviso) para un archivo de una subcarpeta de .dev."""
    name = path.name
    stem = path.stem
    if name in KNOWN.get(dirname, {}):
        return KNOWN[dirname][name], None
    for prefix, desc in PREFIXES.get(dirname, []):
        if name.startswith(prefix):
            return desc, None
    if dirname == "features" and path.suffix == ".md":
        return "brief de feature para el pipeline de build", None
    if dirname == "cards" and path.suffix == ".json":
        estado = card_status(path)
        pendiente = estado in ("drafted", "built")
        return ("tarjeta del camino rapido (%s)" % estado,
                "PENDIENTE DE PROMOVER: construida sin linea de base — /requerimientos:promover"
                if pendiente else None)
    if dirname == "manual" and path.suffix == ".md":
        return "guia de usuario final (Markdown)", None
    if path.suffix == ".md" and stem in DERIVED_MD.get(dirname, []):
        desc = "vista legible derivada de %s.json — no editar a mano" % stem
        jv = json_version(path.parent / (stem + ".json"), vcache)
        hv = md_header_version(path)
        if jv is not None and str(hv) != str(jv):
            detalle = "encabezado v%s" % hv if hv is not None else "sin encabezado de derivacion"
            return desc, "DESINCRONIZADO: %s vs json v%s — re-correr el script de derivacion" % (detalle, jv)
        return desc, None
    if path.suffix == ".md" and stem in AGENT_MD.get(dirname, []):
        return "resumen legible de %s.json" % stem, None
    return None, "fuera del layout estandar de la suite"


def render_layout(dev, out, vcache):
    out.append("## Layout")
    out.append("")
    dirs = [d for d in DIR_ORDER if (dev / d).is_dir()]
    dirs += sorted(d.name for d in dev.iterdir() if d.is_dir() and d.name not in DIR_ORDER)
    for dirname in dirs:
        droot = dev / dirname
        files = sorted(p for p in droot.iterdir() if p.is_file())
        subdirs = sorted(p for p in droot.iterdir() if p.is_dir())
        out.append("### .dev/%s/" % dirname)
        out.append("")
        if not files and not subdirs:
            out.append("(vacia)")
        for p in files:
            desc, aviso = describe(dirname, p, vcache)
            v = json_version(p, vcache) if p.suffix == ".json" else None
            bits = ["v%s" % v] if v is not None else []
            bits.append(kb(p))
            line = "- `%s` (%s)" % (p.name, ", ".join(bits))
            if desc:
                line += " — %s" % desc
            if aviso:
                line += " — **%s**" % aviso
            out.append(line)
        for p in subdirs:
            count = sum(1 for f in p.rglob("*") if f.is_file())
            desc = SUBDIRS.get((dirname, p.name))
            line = "- `%s/` (%d archivos)" % (p.name, count)
            line += " — %s" % desc if desc else " — **fuera del layout estandar de la suite**"
            out.append(line)
        out.append("")
    loose = sorted(p for p in dev.iterdir() if p.is_file() and p.name.lower() != "readme.md")
    if loose:
        out.append("### .dev/ (raiz)")
        out.append("")
        for p in loose:
            out.append("- `%s` (%s) — **fuera del layout estandar de la suite**" % (p.name, kb(p)))
        out.append("")


NOTAS_MAPA = {
    "stub": "hueco intencional: sin elaborar ni baselinear todavia",
    "elaborated": "elaborada, aun sin baselinear",
    "proposed": "propuesta pendiente de confirmacion",
    "deprecated": "deprecada: no se construye",
}


def estado_features(dev):
    """Estado de cada FG cruzando mapa, plan y build. Datos, sin formato.

    Lo consume la tabla de este indice y tambien `suite_status.py`: es la misma
    lectura de `product-map.json` x `tasks.json` x `progress.json`, y tenerla dos
    veces seria justo la clase de duplicacion que la suite viene cerrando.
    """
    pmap = load_json(dev / "requirements" / "product-map.json")
    tasks = load_json(dev / "plan" / "tasks.json")
    progress = load_json(dev / "plan" / "progress.json")
    if not any((pmap, tasks, progress)):
        return []
    map_feats = {f.get("id"): f for f in (pmap or {}).get("features", []) or []}
    plan_feats = {f.get("id"): f for f in (tasks or {}).get("features", []) or []}
    build_state = {f.get("feature_id"): f.get("status") for f in (progress or {}).get("features", []) or []}
    filas = []
    for fid in sorted(set(map_feats) | set(plan_feats) | set(build_state), key=str):
        mf, pf = map_feats.get(fid), plan_feats.get(fid)
        nota = ""
        if mf and not pf:
            nota = NOTAS_MAPA.get(mf.get("status"), "sin tareas en el plan")
            if mf.get("status") == "baselined":
                nota = "baselineada sin tareas en el plan: replanificar?"
        elif pf and not mf and pf.get("synthetic"):
            nota = "feature sintetica del plan (bootstrap)"
        elif pf and not mf:
            nota = "en el plan pero no en el mapa: revisar"
        filas.append({
            "id": fid,
            "name": (mf or pf or {}).get("name", ""),
            "mapa": mf.get("status", "?") if mf else None,
            "plan": bool(pf),
            "build": build_state.get(fid),
            "nota": nota,
        })
    return filas


def render_fg(dev, out):
    filas = estado_features(dev)
    if not filas:
        return
    out.append("## Estado por feature (FG)")
    out.append("")
    out.append("| FG | Feature | Mapa | Plan | Build | Nota |")
    out.append("|---|---|---|---|---|---|")
    for f in filas:
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            f["id"], (f["name"] or "").replace("|", "\\|"),
            f["mapa"] or "—", "planificada" if f["plan"] else "—",
            f["build"] or "—", f["nota"]))
    out.append("")


def estado_changelog(dev):
    """INC/CR pendientes, aplicados sin absorber y postergados. Datos, sin formato."""
    changelog = load_json(dev / "requirements" / "changelog.json")
    if not changelog:
        return None
    entries = changelog.get("entries", []) or []
    tasks = load_json(dev / "plan" / "tasks.json") or {}
    meta = tasks.get("metadata", {}) or {}
    absorbed = set(meta.get("applied_changelog_ids") or []) | set(meta.get("deferred_changelog_ids") or [])
    aplicados = [e for e in entries
                 if e.get("status") == "applied"
                 and e.get("kind") in ("increment", "change_request", "recovery")]
    return {
        "pendientes": [e for e in entries if e.get("status") not in ("applied", "rejected")],
        "no_absorbidos": [e for e in aplicados if e.get("id") not in absorbed] if tasks else [],
        "postergados": list(meta.get("deferred_changelog_ids") or []),
    }


def render_changelog(dev, out):
    est = estado_changelog(dev)
    if est is None:
        return
    out.append("## INC / CR")
    out.append("")
    if est["pendientes"]:
        out.append("Pendientes (no aplicados a la linea de base):")
        out.append("")
        for e in est["pendientes"]:
            note = ((e.get("notes") or "").splitlines() or [""])[0].strip()
            out.append("- `%s` (%s, **%s**, %s)%s" % (
                e.get("id", "?"), e.get("kind", "?"), e.get("status", "?"),
                e.get("date", "?"), ": %s" % note if note else ""))
        out.append("")
    if est["no_absorbidos"]:
        out.append("Aplicados a los requisitos pero NO absorbidos por el plan (correr `/replanificar`):")
        out.append("")
        for e in est["no_absorbidos"]:
            out.append("- `%s` (%s, %s)" % (e.get("id", "?"), e.get("kind", "?"), e.get("date", "?")))
        out.append("")
    if est["postergados"]:
        out.append("Postergados a proposito en la replanificacion: %s." % ", ".join(est["postergados"]))
        out.append("")
    if not any((est["pendientes"], est["no_absorbidos"], est["postergados"])):
        out.append("Nada pendiente: todo lo aplicado esta absorbido por el plan (o no hay plan aun).")
        out.append("")


def project_name(dev):
    for rel in ("requirements/product-map.json", "requirements/lel.json", "requirements/requirements.json", "plan/tasks.json"):
        data = load_json(dev / rel)
        if isinstance(data, dict):
            name = (data.get("project") or {}).get("name")
            if name:
                return name
    return ""


# ------------------------------------------------------------------ self-test

def self_test():
    """Corre el render sobre un `.dev` embebido y verifica lo que promete el
    docstring: indice generado, estado por feature (incluidos los stubs del
    product-map), aviso de vista desincronizada, y determinismo."""
    import shutil
    import tempfile

    fallos = 0

    def check(nombre, ok, detalle=""):
        nonlocal fallos
        if ok:
            print("self-test ok (%s)" % nombre)
        else:
            print("SELF-TEST FALLO (%s)%s" % (nombre, ": " + detalle if detalle else ""))
            fallos += 1

    tmp = Path(tempfile.mkdtemp(prefix="render-index-"))
    try:
        req = tmp / ".dev" / "requirements"
        req.mkdir(parents=True)
        (req / "product-map.json").write_text(json.dumps({
            "version": 1,
            "project": {"name": "demo"},
            "features": [
                {"id": "FG-01", "name": "Turnos", "status": "baselined"},
                {"id": "FG-02", "name": "Recordatorios", "status": "stub"},
            ],
        }), encoding="utf-8")
        (req / "lel.json").write_text(json.dumps({"version": 2, "symbols": []}), encoding="utf-8")
        # vista derivada que quedo atras: el encabezado cita v1 y el json va en v2
        (req / "lel.md").write_text(
            "# LEL\n\n> Derivado de `lel.json` version 1 - no editar a mano.\n", encoding="utf-8")
        (req / "changelog.json").write_text(json.dumps({
            "version": 1, "entries": [{"id": "INC-001", "status": "in_progress"}],
        }), encoding="utf-8")
        cards = tmp / ".dev" / "cards"
        cards.mkdir(parents=True)
        (cards / "FG-07-alta.json").write_text(json.dumps({
            "id": "FG-07", "slug": "alta", "status": "built"}), encoding="utf-8")

        dev = tmp / ".dev"
        code = main([str(dev)])
        readme = dev / "README.md"
        check("genera el indice", code == 0 and readme.is_file(), "exit %s" % code)

        texto = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        check("lleva el encabezado de generado", "no editar a mano" in texto)
        check("la tarjeta sin promover se ve como deuda en el indice",
              "PENDIENTE DE PROMOVER" in texto)
        check("lista la feature baselineada", "FG-01" in texto)
        check("lista el stub (explica el hueco de numeracion)", "FG-02" in texto)
        check("avisa la vista desincronizada", "DESINCRONIZADO" in texto,
              "el aviso de lel.md v1 vs lel.json v2 no aparece")

        # determinismo: mismo .dev -> mismo README, byte a byte
        primero = readme.read_bytes()
        main([str(dev)])
        check("es determinista", readme.read_bytes() == primero)

        check("carpeta inexistente da exit 1", main([str(tmp / "no-existe")]) == 1)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return 1 if fallos else 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default=".dev", help="carpeta .dev del proyecto (default: .dev)")
    ap.add_argument("--salida", default=None, help="archivo de salida (default: <carpeta>/README.md)")
    ap.add_argument("--self-test", action="store_true", help="corre el self-test sobre un .dev embebido y sale")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    dev = Path(args.carpeta)
    if not dev.is_dir():
        print("No existe la carpeta: %s" % dev)
        return 1
    dest = Path(args.salida) if args.salida else dev / "README.md"

    name = project_name(dev)
    out = ["# Indice de `.dev`%s" % (" — %s" % name if name else ""), ""]
    out.append("> Generado por `render_index.py` — no editar a mano. Cada pipeline lo regenera en su cierre.")
    out.append("")
    vcache = {}
    render_layout(dev, out, vcache)
    render_fg(dev, out)
    render_changelog(dev, out)
    while out and out[-1] == "":
        out.pop()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("indice: %s (%d lineas)" % (dest, len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
