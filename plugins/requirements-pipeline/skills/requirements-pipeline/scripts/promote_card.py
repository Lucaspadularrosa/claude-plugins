#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cierre mecanico de la promocion de una tarjeta del camino rapido.

Cuando una feature se construye por el camino rapido, sus requisitos viven como ids
PROVISIONALES (`RF-FT07#1`) en tres lugares: el plan (`tasks.json`), los desvios que
dejo el build (`.dev/build/desvios/*.json` y sus `cr-input-*.md`) y la propia tarjeta.
Al promoverla, los agentes de requisitos escriben deltas con esos mismos ids y
`apply_delta.py --mapa-salida` los renumera a la secuencia global, dejando la tabla
{provisional: global}. Este script aplica esa tabla al resto, que ningun agente toca:

  .dev/plan/tasks.json        requirement_ids, trazabilidad, summary; version +1,
                              requirements_version_ref y applied_changelog_ids al dia
  .dev/build/desvios/*.json   requirement_ref de cada desvio ya registrado
  .dev/build/cr-input-*.md    la vista del desvio (si existe)
  .dev/cards/FG-xx-*.json     status -> promoted y la tabla de ids aplicada

Sin esto, un `/cambio` posterior sobre un desvio citaria un id que no existe, y el
plan seguiria apuntando a requisitos provisionales para siempre.

Solo stdlib, Python 3.8+.

Uso:
  python promote_card.py [raiz] --card FG-07 --mapa .dev/cards/.map.json
                         [--changelog-id CR-003] [--dry-run]
  python promote_card.py --self-test

Exit 0 si aplico (o no habia nada que aplicar); 1 si falta un archivo obligatorio, la
tabla no parsea, o quedaron ids provisionales de la tarjeta sin renumerar (promocion
incompleta: faltan deltas de algun agente).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# Un token provisional completo, con sus digitos: matchear el token entero evita que
# `RF-FT07#1` se coma el prefijo de `RF-FT07#10`.
TOKEN = re.compile(r"(?:[A-Z]+-)*[A-Z]+-[A-Za-z0-9]+#\d+")


def fail(msg):
    print("ERROR: %s" % msg)
    sys.exit(1)


def load(path, required=True):
    path = Path(path)
    if not path.is_file():
        if required:
            fail("no existe %s" % path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        fail("%s ilegible: %s" % (path, exc))


def substitute(text, mapping):
    """Reemplaza cada token provisional por su id global. Devuelve (texto, cambios)."""
    hits = []

    def repl(m):
        new = mapping.get(m.group(0))
        if new is None:
            return m.group(0)
        hits.append(m.group(0))
        return new

    return TOKEN.sub(repl, text), hits


def remaining(text, tag):
    """Tokens provisionales de esta tarjeta que quedaron sin renumerar."""
    return sorted({t for t in TOKEN.findall(text) if "-%s#" % tag in t})


def tag_of(feature_id):
    return "FT%s" % str(feature_id).split("-")[-1]


def recompute_summary(tasks_doc, reqs_doc):
    active = [t for t in tasks_doc.get("tasks") or [] if t.get("status", "pending") != "cancelled"]
    covered = sorted({r for t in active for r in t.get("requirement_ids") or []})
    summary = tasks_doc.setdefault("summary", {})
    summary["covered_requirement_ids"] = covered
    if reqs_doc is not None:
        active_reqs = {r.get("id") for r in (reqs_doc.get("functional_requirements") or [])
                       + (reqs_doc.get("non_functional_requirements") or [])
                       if r.get("status") == "active"}
        summary["uncovered_requirement_ids"] = sorted(active_reqs - set(covered))
    return summary


def promote(root, feature, mapa_path, changelog_id, dry_run):
    root = Path(root).resolve()
    mapping = load(mapa_path)
    if not isinstance(mapping, dict):
        fail("%s no es una tabla {provisional: global}" % mapa_path)
    tag = tag_of(feature)
    escrituras = []
    total = 0

    # ---------------------------------------------------------------- tasks.json
    tasks_path = root / ".dev" / "plan" / "tasks.json"
    raw = tasks_path.read_text(encoding="utf-8-sig") if tasks_path.is_file() else fail(
        "no existe %s: sin plan no hay nada que promover" % tasks_path)
    nuevo, hits = substitute(raw, mapping)
    total += len(hits)
    pendientes = remaining(nuevo, tag)
    if pendientes:
        fail("quedaron ids provisionales de %s sin renumerar en tasks.json: %s\n"
             "       la promocion esta incompleta: falta el delta del agente que los define"
             % (feature, ", ".join(pendientes)))
    doc = json.loads(nuevo)
    doc["version"] = int(doc.get("version", 0)) + 1
    meta = doc.setdefault("metadata", {})
    reqs_doc = load(root / ".dev" / "requirements" / "requirements.json", required=False)
    if reqs_doc is not None and reqs_doc.get("version") is not None:
        meta["requirements_version_ref"] = str(reqs_doc["version"])
    if changelog_id:
        aplicados = meta.setdefault("applied_changelog_ids", [])
        if changelog_id not in aplicados:
            aplicados.append(changelog_id)
        meta["deferred_changelog_ids"] = [d for d in meta.get("deferred_changelog_ids") or []
                                          if d != changelog_id]
    recompute_summary(doc, reqs_doc)
    escrituras.append((tasks_path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                       "%d id(s), version -> %d" % (len(hits), doc["version"])))

    # -------------------------------------------- desvios y vistas del build
    build_dir = root / ".dev" / "build"
    for path in sorted(list((build_dir / "desvios").glob("*.json"))
                       + list(build_dir.glob("cr-input-*.md"))):
        raw = path.read_text(encoding="utf-8-sig")
        nuevo, hits = substitute(raw, mapping)
        if hits:
            total += len(hits)
            escrituras.append((path, nuevo, "%d id(s)" % len(hits)))

    # ------------------------------------------------------------- la tarjeta
    cards = sorted((root / ".dev" / "cards").glob("%s-*.json" % feature))
    if not cards:
        fail("no hay tarjeta de %s en %s" % (feature, root / ".dev" / "cards"))
    card_path = cards[0]
    card = load(card_path)
    card["status"] = "promoted"
    card["promotion"] = {
        "date": date.today().isoformat(),
        "changelog_id": changelog_id,
        "ids": {k: v for k, v in sorted(mapping.items()) if "-%s#" % tag in k},
    }
    escrituras.append((card_path, json.dumps(card, ensure_ascii=False, indent=2) + "\n",
                       "status -> promoted, %d id(s) registrados" % len(card["promotion"]["ids"])))

    for path, contenido, nota in escrituras:
        if not dry_run:
            path.write_text(contenido, encoding="utf-8")
        print("%s%s: %s" % ("[dry-run] " if dry_run else "", path.relative_to(root), nota))
    print("promocion de %s: %d referencia(s) renumerada(s)%s"
          % (feature, total, " (dry-run, nada escrito)" if dry_run else ""))
    if not card["promotion"]["ids"]:
        print("aviso: la tabla no traia ningun id de %s; revisa que los deltas hayan usado el tag %s"
              % (feature, tag))
    return 0


def self_test():
    import shutil
    import tempfile

    failures = 0

    def check(cond, label):
        nonlocal failures
        if not cond:
            failures += 1
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))

    check(substitute("cubre RF-FT07#1 y RF-FT07#10",
                     {"RF-FT07#1": "RF-012", "RF-FT07#10": "RF-021"})[0]
          == "cubre RF-012 y RF-021", "el token se reemplaza entero (#1 no se come #10)")

    tmp = Path(tempfile.mkdtemp(prefix="promote-card-"))
    try:
        (tmp / ".dev" / "plan").mkdir(parents=True)
        (tmp / ".dev" / "cards").mkdir(parents=True)
        (tmp / ".dev" / "build" / "desvios").mkdir(parents=True)
        (tmp / ".dev" / "requirements").mkdir(parents=True)
        (tmp / ".dev" / "plan" / "tasks.json").write_text(json.dumps({
            "version": 4,
            "metadata": {"applied_changelog_ids": ["INC-001"], "deferred_changelog_ids": ["CR-003"],
                         "requirements_version_ref": "5"},
            "summary": {"covered_requirement_ids": ["RF-001", "RF-FT07#1"],
                        "uncovered_requirement_ids": []},
            "features": [{"id": "FG-07", "requirement_ids": ["RF-FT07#1"], "task_ids": ["T-009"]}],
            "tasks": [{"id": "T-009", "feature_group": "FG-07", "status": "pending",
                       "requirement_ids": ["RF-FT07#1"],
                       "acceptance_criteria": [{"id": "AC-FT07#1"}]}],
            "traceability_links": [{"source": {"kind": "task", "id": "T-009"},
                                    "target": {"kind": "requirement", "id": "RF-FT07#1"}}],
        }), encoding="utf-8")
        (tmp / ".dev" / "requirements" / "requirements.json").write_text(json.dumps({
            "version": 6,
            "functional_requirements": [{"id": "RF-012", "status": "active"},
                                        {"id": "RF-013", "status": "active"}],
            "non_functional_requirements": []}), encoding="utf-8")
        (tmp / ".dev" / "cards" / "FG-07-alta.json").write_text(json.dumps({
            "id": "FG-07", "slug": "alta", "status": "built"}), encoding="utf-8")
        (tmp / ".dev" / "build" / "desvios" / "FG-07-alta.json").write_text(json.dumps({
            "desvios": [{"id": "DESVIO-1", "requirement_ref": "RF-FT07#1/AC-FT07#1"}]}), encoding="utf-8")
        (tmp / ".dev" / "build" / "cr-input-FG-07-alta.md").write_text(
            "# Desvios\n\nDESVIO-1 - RF-FT07#1/AC-FT07#1\n", encoding="utf-8")
        mapa = tmp / ".dev" / "cards" / ".map.json"
        mapa.write_text(json.dumps({"RF-FT07#1": "RF-012", "AC-FT07#1": "AC-030"}), encoding="utf-8")

        check(promote(tmp, "FG-07", mapa, "CR-003", dry_run=False) == 0, "promocion corre")
        doc = json.loads((tmp / ".dev" / "plan" / "tasks.json").read_text(encoding="utf-8"))
        check(doc["tasks"][0]["requirement_ids"] == ["RF-012"], "requirement_ids renumerados")
        check(doc["tasks"][0]["acceptance_criteria"][0]["id"] == "AC-030", "criterios renumerados")
        check(doc["traceability_links"][0]["target"]["id"] == "RF-012", "trazabilidad renumerada")
        check(doc["version"] == 5 and doc["metadata"]["requirements_version_ref"] == "6",
              "version del plan y version_ref al dia")
        check(doc["metadata"]["applied_changelog_ids"] == ["INC-001", "CR-003"]
              and doc["metadata"]["deferred_changelog_ids"] == [],
              "el CR pasa de diferido a aplicado")
        check(doc["summary"]["covered_requirement_ids"] == ["RF-012"]
              and doc["summary"]["uncovered_requirement_ids"] == ["RF-013"],
              "summary recalculado contra la linea de base")
        desvio = json.loads((tmp / ".dev" / "build" / "desvios" / "FG-07-alta.json").read_text(encoding="utf-8"))
        check(desvio["desvios"][0]["requirement_ref"] == "RF-012/AC-030",
              "los desvios del build dejan de citar ids que no existen")
        check("RF-012/AC-030" in (tmp / ".dev" / "build" / "cr-input-FG-07-alta.md").read_text(encoding="utf-8"),
              "la vista del desvio tambien queda renumerada")
        card = json.loads((tmp / ".dev" / "cards" / "FG-07-alta.json").read_text(encoding="utf-8"))
        check(card["status"] == "promoted" and card["promotion"]["ids"]["RF-FT07#1"] == "RF-012",
              "la tarjeta queda promovida y con su tabla de ids")

        # promocion incompleta: un id provisional que ningun delta definio
        doc["tasks"][0]["requirement_ids"] = ["RF-FT07#9"]
        (tmp / ".dev" / "plan" / "tasks.json").write_text(json.dumps(doc), encoding="utf-8")
        try:
            promote(tmp, "FG-07", mapa, None, dry_run=False)
            check(False, "id sin renumerar deberia frenar")
        except SystemExit as exc:
            check(exc.code == 1, "id provisional sin renumerar frena la promocion")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--card", required=True, help="id de la feature promovida (FG-07)")
    ap.add_argument("--mapa", required=True, help="tabla de apply_delta.py --mapa-salida")
    ap.add_argument("--changelog-id", default=None, help="CR-xxx de la promocion")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    return promote(args.raiz, args.card, args.mapa, args.changelog_id, args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
