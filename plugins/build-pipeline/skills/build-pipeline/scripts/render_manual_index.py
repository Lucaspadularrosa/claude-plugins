#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Indice del manual de usuario (`.dev/manual/README.md`), derivado y determinista.

Lee el frontmatter (`feature`, `fg`, `titulo`, `resumen`) de cada guia en
`.dev/manual/*.md` y regenera el indice desde cero: nombre del producto como titulo
(de `.dev/requirements/product-map.json` o el nombre del directorio del proyecto) y
una entrada por guia. Nunca se edita a mano; un conflicto se resuelve regenerando.

Con `--cobertura` cruza ademas las guias contra `.dev/plan/progress.json` e imprime
que features `done` no tienen guia (lo que el modo DOCUMENTAR necesita saber sin leer
ningun archivo con el modelo).

Uso:
  python render_manual_index.py <raiz> [--titulo "Nombre"] [--cobertura] [--solo-cobertura]
  python render_manual_index.py --self-test

Solo stdlib. Exit 0 siempre que pudo escribir (o listar); 2 en error de uso.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def parse_frontmatter(text):
    meta = {}
    if not text.startswith("---"):
        return meta
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            return meta
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip("\"'")
    return {}


def product_name(root):
    pm = root / ".dev" / "requirements" / "product-map.json"
    try:
        data = json.loads(pm.read_text(encoding="utf-8-sig"))
        for key in ("product_name", "name", "product"):
            v = data.get(key) or (data.get("metadata") or {}).get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    except (OSError, ValueError):
        pass
    return root.resolve().name


def collect(manual_dir):
    guides = []
    for page in sorted(manual_dir.glob("*.md")):
        if page.name.lower() == "readme.md":
            continue
        meta = parse_frontmatter(page.read_text(encoding="utf-8"))
        guides.append({
            "archivo": page.name,
            "feature": meta.get("feature") or page.stem,
            "fg": meta.get("fg", ""),
            "titulo": meta.get("titulo") or page.stem,
            "resumen": meta.get("resumen", ""),
            "sin_frontmatter": not meta,
        })
    return guides


def render(titulo, guides):
    lines = ["# %s — Manual de usuario" % titulo, ""]
    if not guides:
        lines.append("_Todavia no hay guias._")
    for g in sorted(guides, key=lambda g: (g["fg"], g["titulo"])):
        lines.append("- [%s](%s)%s" % (g["titulo"], g["archivo"], (" — " + g["resumen"]) if g["resumen"] else ""))
    lines.append("")
    return "\n".join(lines)


def cobertura(root, guides):
    progress_path = root / ".dev" / "plan" / "progress.json"
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    with_guide = {g["fg"] for g in guides if g["fg"]}
    done = [f["feature_id"] for f in progress.get("features") or [] if f.get("status") == "done"]
    sin_guia = [fid for fid in done if fid not in with_guide]
    notes = {f["feature_id"]: f.get("notes", "") for f in progress.get("features") or []}
    declared = [fid for fid in sin_guia if "SIN GUIA" in (notes.get(fid) or "")]
    return {"done": done, "sin_guia": sin_guia, "sin_guia_declarada": declared,
            "guias_sin_feature_done": sorted(with_guide - set(done))}


# ------------------------------------------------------------------ self-test

def self_test():
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="manual-index-"))
    failures = 0
    try:
        manual = tmp / ".dev" / "manual"
        manual.mkdir(parents=True)
        (manual / "carrito.md").write_text("---\nfeature: carrito\nfg: FG-02\ntitulo: Carrito de compras\nresumen: Comprar cosas\n---\n# Carrito\n", encoding="utf-8")
        (manual / "alta.md").write_text("---\nfeature: alta\nfg: FG-01\ntitulo: Alta de socios\nresumen: Dar de alta\n---\n", encoding="utf-8")
        (manual / "README.md").write_text("viejo", encoding="utf-8")
        plan = tmp / ".dev" / "plan"
        plan.mkdir(parents=True)
        (plan / "progress.json").write_text(json.dumps({"features": [
            {"feature_id": "FG-01", "status": "done"}, {"feature_id": "FG-02", "status": "done"},
            {"feature_id": "FG-03", "status": "done", "notes": "SIN GUIA: sin superficie"},
            {"feature_id": "FG-04", "status": "in_progress"}]}), encoding="utf-8")
        guides = collect(manual)
        out = render("Demo", guides)
        if "[Alta de socios](alta.md)" not in out or out.index("alta.md") > out.index("carrito.md"):
            print("SELF-TEST FALLO (render): %s" % out)
            failures += 1
        else:
            print("self-test ok (render ordenado por FG)")
        cov = cobertura(tmp, guides)
        if cov["sin_guia"] != ["FG-03"] or cov["sin_guia_declarada"] != ["FG-03"]:
            print("SELF-TEST FALLO (cobertura): %s" % cov)
            failures += 1
        else:
            print("self-test ok (cobertura)")
        if product_name(tmp) != tmp.resolve().name:
            print("SELF-TEST FALLO (nombre por defecto)")
            failures += 1
        else:
            print("self-test ok (nombre del producto por defecto)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failures else 0


# ------------------------------------------------------------------------ main

def main(argv):
    if "--self-test" in argv:
        return self_test()
    root = None
    titulo = None
    cov = False
    solo_cov = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--titulo":
            i += 1
            titulo = argv[i]
        elif a == "--cobertura":
            cov = True
        elif a == "--solo-cobertura":
            cov = True
            solo_cov = True
        elif a.startswith("--"):
            print("error: opcion desconocida %s" % a)
            return 2
        else:
            root = a
        i += 1
    if not root:
        print(__doc__)
        return 2
    root = Path(root)
    manual = root / ".dev" / "manual"
    guides = collect(manual) if manual.is_dir() else []
    for g in guides:
        if g["sin_frontmatter"]:
            print("aviso: %s sin frontmatter (queda fuera del indice con datos por defecto)" % g["archivo"])
    if not solo_cov:
        manual.mkdir(parents=True, exist_ok=True)
        (manual / "README.md").write_text(render(titulo or product_name(root), guides), encoding="utf-8")
        print("indice: %s (%d guia(s))" % (manual / "README.md", len(guides)))
    if cov:
        c = cobertura(root, guides)
        if c is None:
            print("cobertura: sin progress.json legible")
        else:
            print("cobertura: %d features done, %d sin guia%s" % (
                len(c["done"]), len(c["sin_guia"]),
                (": " + ", ".join(c["sin_guia"])) if c["sin_guia"] else ""))
            if c["sin_guia_declarada"]:
                print("  declaradas SIN GUIA en progress: %s" % ", ".join(c["sin_guia_declarada"]))
            if c["guias_sin_feature_done"]:
                print("  guias de features no done: %s" % ", ".join(c["guias_sin_feature_done"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
