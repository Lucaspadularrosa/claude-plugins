#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge determinista de deltas (`*.delta.json`) al artefacto canonico, sin tokens.

Los subagentes que corren en paralelo (un intake por fuente, un scenario-modeling o
requirements-specification por feature) o que no pudieron editar un canonico grande
escriben un delta en vez de reescribir el archivo entero. Este script los mergea al
canonico, renumera los ids provisionales a la secuencia global, recalcula el
`summary`, sube `version` una sola vez, valida el resultado y BORRA los deltas. El
orquestador nunca carga el canonico en su contexto para mergear a mano.

Nombres de delta que reconoce, en `.dev/requirements/`:
  <canonico>.delta.json            un unico delta (fallback de un agente solo)
  <canonico>.<tag>.delta.json      un delta por agente paralelo (tag = FG-03, src2, ...)
Ejemplos: scenarios.FG-03.delta.json, source-inventory.vision.delta.json.

Formato del delta:
  {
    "base_version": 3,                      version del canonico sobre la que se armo
    "set": {"project": {...}, "metadata": {...}},   campos raiz a sobreescribir (merge superficial)
    "adds": {"scenarios": [ {...}, ... ]},   items nuevos por lista raiz (por id)
    "updates": {"scenarios": [ {"id": "SCN-004", ...campos...} ]},   reemplazo parcial por id
    "removes": {"open_questions": ["Q-003"]}   (o una lista plana de ids, se buscan en todas las listas)
  }
Si el canonico no existe todavia (creacion inicial en paralelo), `base_version` es 0
o se omite, y el script lo crea desde los deltas.

Ids provisionales: un agente paralelo no conoce la secuencia global, asi que emite
ids con la forma `PREFIJO-<tag>#<n>` (ej. `SCN-FG03#1`, `RF-FG03#2`, `AC-FG03#7`,
`SRC-SEC-src2#4`) y los cita asi en todo el delta, incluidas las formas compuestas
(`RF-FG03#2/AC-FG03#7`). El merge les asigna el siguiente numero libre del prefijo y
reescribe todas las citas dentro del delta. Los ids ya globales (`SCN-004`) se
respetan tal cual. Todos los deltas de un mismo canonico deben tener el mismo
`base_version` (= la version actual): si difieren, el script no mergea nada.

Solo stdlib, Python 3.8+.

Uso:
  python apply_delta.py [carpeta] [--solo scenarios requirements] [--dry-run]
  python apply_delta.py --self-test

Exit 0 si no habia deltas o se mergearon todos; exit 1 ante cualquier error (nada
se escribe a medias: cada canonico se mergea completo o no se toca).
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

PROVISIONAL = re.compile(r"((?:[A-Z]+-)*[A-Z]+)-([A-Za-z0-9]+)#(\d+)")
GLOBAL_ID = re.compile(r"^((?:[A-Z]+-)*[A-Z]+)-(\d+)$")
DEFAULT_WIDTH = {"FG": 2, "SCN": 3}

SKELETON = {
    "source-inventory": {"version": 0, "summary": {}, "sections": []},
    "lel-candidates": {"version": 0, "candidates": [], "gaps": []},
    "supporting-context": {"version": 0, "items": []},
    "lel": {"version": 0, "symbols": [], "alias_map": [], "open_questions": [], "traceability_links": [], "assumptions": [], "warnings": []},
    "product-map": {"version": 0, "features": [], "pending_proposals": [], "warnings": []},
    "scenarios": {"version": 0, "summary": {}, "scenarios": [], "open_questions": [], "traceability_links": [], "assumptions": [], "warnings": []},
    "requirements": {"version": 0, "summary": {}, "feature_groups": [], "functional_requirements": [], "non_functional_requirements": [],
                     "business_rules": [], "open_questions": [], "proposed_baseline_changes": [], "traceability_links": [], "assumptions": [], "warnings": []},
    "data-model": {"version": 0, "summary": {}, "entities": [], "relationships": [], "open_questions": [], "traceability_links": [], "assumptions": [], "warnings": []},
    "technical-design": {"version": 0, "summary": {}, "stack": [], "modules": [], "api_contracts": [], "screens": [], "decisions": [],
                         "open_questions": [], "traceability_links": [], "assumptions": [], "warnings": []},
}


class DeltaError(Exception):
    pass


# ----------------------------------------------------------------- ids


def walk_strings(obj, fn):
    """Aplica fn a cada string del arbol y devuelve el arbol reescrito."""
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [walk_strings(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: walk_strings(v, fn) for k, v in obj.items()}
    return obj


def collect_max_ids(obj, maxes, widths):
    def see(s):
        m = GLOBAL_ID.match(s)
        if m:
            prefix, num = m.group(1), m.group(2)
            maxes[prefix] = max(maxes.get(prefix, 0), int(num))
            widths[prefix] = max(widths.get(prefix, 0), len(num))
        return s
    walk_strings(obj, see)


def renumber(delta, maxes, widths):
    """Asigna numeros globales a los ids provisionales del delta, en orden (tag, n)."""
    found = set()

    def see(s):
        for m in PROVISIONAL.finditer(s):
            found.add((m.group(1), m.group(2), int(m.group(3))))
        return s
    walk_strings(delta, see)
    mapping = {}
    for prefix, tag, n in sorted(found, key=lambda t: (t[0], t[1], t[2])):
        maxes[prefix] = maxes.get(prefix, 0) + 1
        width = widths.get(prefix) or DEFAULT_WIDTH.get(prefix, 3)
        mapping["%s-%s#%d" % (prefix, tag, n)] = "%s-%0*d" % (prefix, width, maxes[prefix])

    def rewrite(s):
        return PROVISIONAL.sub(lambda m: mapping.get(m.group(0), m.group(0)), s)
    return walk_strings(delta, rewrite), mapping


# --------------------------------------------------------------- merge


def all_ids(doc):
    out = set()
    for key, lst in doc.items():
        if isinstance(lst, list):
            for item in lst:
                if isinstance(item, dict) and item.get("id"):
                    out.add(item["id"])
    return out


def merge_one(doc, delta):
    for key, val in (delta.get("set") or {}).items():
        if isinstance(val, dict) and isinstance(doc.get(key), dict):
            doc[key].update(val)
        else:
            doc[key] = val
    existing = all_ids(doc)
    for key, items in (delta.get("adds") or {}).items():
        if not isinstance(items, list):
            raise DeltaError("adds.%s no es una lista" % key)
        doc.setdefault(key, [])
        if not isinstance(doc[key], list):
            raise DeltaError("adds.%s: el canonico no tiene una lista en esa clave" % key)
        for item in items:
            iid = item.get("id") if isinstance(item, dict) else None
            if iid and iid in existing:
                raise DeltaError("adds.%s: el id %s ya existe en el canonico" % (key, iid))
            doc[key].append(item)
            if iid:
                existing.add(iid)
    for key, items in (delta.get("updates") or {}).items():
        target = doc.get(key)
        if not isinstance(target, list):
            raise DeltaError("updates.%s: el canonico no tiene una lista en esa clave" % key)
        by_id = {it.get("id"): it for it in target if isinstance(it, dict)}
        for item in items:
            iid = item.get("id")
            if iid not in by_id:
                raise DeltaError("updates.%s: el id %s no existe en el canonico" % (key, iid))
            by_id[iid].update(item)
    removes = delta.get("removes") or {}
    if isinstance(removes, list):
        removes = {key: removes for key in doc if isinstance(doc.get(key), list)}
    for key, ids in removes.items():
        target = doc.get(key)
        if not isinstance(target, list):
            continue
        doc[key] = [it for it in target if not (isinstance(it, dict) and it.get("id") in set(ids))]
    return doc


# -------------------------------------------------------------- summary


def recompute_summary(name, doc, folder):
    s = doc.setdefault("summary", {}) if name not in ("lel",) else None
    if name == "scenarios":
        scn = doc.get("scenarios") or []
        s.update({
            "total_scenarios": len(scn),
            "current_scenarios": sum(1 for x in scn if x.get("scenario_type") == "current"),
            "future_scenarios": sum(1 for x in scn if x.get("scenario_type") == "future"),
            "total_episodes": sum(len(x.get("episodes") or []) for x in scn),
            "total_exceptions": sum(len(x.get("exceptions") or []) for x in scn),
            "blocking_questions": sum(1 for q in doc.get("open_questions") or [] if q.get("blocking")),
        })
        used = sorted({sid for x in scn for sid in x.get("lel_symbol_ids") or []})
        s["covered_symbol_ids"] = used
        lel = load_optional(folder / "lel.json")
        if lel:
            active = [x.get("id") for x in lel.get("symbols") or [] if x.get("status", "active") == "active"]
            s["uncovered_symbol_ids"] = [i for i in active if i not in set(used)]
    elif name == "requirements":
        rf = doc.get("functional_requirements") or []
        rnf = doc.get("non_functional_requirements") or []
        allr = rf + rnf
        s.update({
            "total_requirements": len(allr), "functional_count": len(rf), "non_functional_count": len(rnf),
            "high_priority": sum(1 for r in allr if r.get("priority") == "high"),
            "medium_priority": sum(1 for r in allr if r.get("priority") == "medium"),
            "low_priority": sum(1 for r in allr if r.get("priority") == "low"),
            "feature_count": len(doc.get("feature_groups") or []),
            "business_rule_count": len(doc.get("business_rules") or []),
            "blocking_questions": sum(1 for q in doc.get("open_questions") or [] if q.get("blocking")),
        })
        covered = sorted({sid for r in allr if r.get("status", "active") != "deprecated" for sid in r.get("source_scenario_ids") or []})
        s["covered_scenario_ids"] = covered
        scn = load_optional(folder / "scenarios.json")
        if scn:
            active = [x.get("id") for x in scn.get("scenarios") or [] if x.get("status", "active") == "active"]
            s["uncovered_scenario_ids"] = [i for i in active if i not in set(covered)]
        # requirement_ids de cada feature group = los que la referencian
        for g in doc.get("feature_groups") or []:
            g["requirement_ids"] = [r.get("id") for r in allr if r.get("feature_group") == g.get("id")]
    elif name == "product-map":
        feats = doc.get("features") or []
        s.update({"feature_count": len(feats)})
        for st in ("stub", "elaborated", "baselined", "deprecated"):
            s["%s_count" % st] = sum(1 for f in feats if f.get("status") == st)
        s["pending_proposal_count"] = sum(1 for p in doc.get("pending_proposals") or [] if p.get("status", "pending") == "pending")
    elif name == "data-model":
        s.update({"entity_count": len(doc.get("entities") or []), "relationship_count": len(doc.get("relationships") or [])})
        used = sorted({e.get("lel_symbol_id") for e in doc.get("entities") or [] if e.get("lel_symbol_id")})
        s["covered_symbol_ids"] = used
    elif name == "technical-design":
        s.update({"module_count": len(doc.get("modules") or []), "api_contract_count": len(doc.get("api_contracts") or []),
                  "screen_count": len(doc.get("screens") or []), "decision_count": len(doc.get("decisions") or [])})
    elif name == "source-inventory":
        s["section_count"] = len(doc.get("sections") or [])
        cand = load_optional(folder / "lel-candidates.json")
        ctx = load_optional(folder / "supporting-context.json")
        if cand:
            s["lel_candidate_count"] = len(cand.get("candidates") or [])
            s["gap_count"] = len(cand.get("gaps") or [])
        if ctx:
            s["supporting_context_item_count"] = len(ctx.get("items") or [])
    elif name == "lel-candidates" or name == "supporting-context":
        doc.pop("summary", None) if not doc.get("summary") else None


def load_optional(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None
    except (ValueError, OSError):
        return None


# ------------------------------------------------------------------ run


def find_deltas(folder, only):
    groups = {}
    for p in sorted(folder.glob("*.delta.json")):
        parts = p.name[:-len(".delta.json")].split(".")
        name = parts[0]
        if only and name not in only:
            continue
        groups.setdefault(name, []).append(p)
    return groups


def apply(folder, only=None, dry_run=False, quiet=False):
    folder = Path(folder)
    groups = find_deltas(folder, only)
    if not groups:
        if not quiet:
            print("sin deltas en %s" % folder)
        return 0, {}
    report = {}
    for name, paths in sorted(groups.items()):
        canonical = folder / ("%s.json" % name)
        doc = load_optional(canonical)
        created = doc is None
        if created:
            doc = json.loads(json.dumps(SKELETON.get(name, {"version": 0})))
        current = int(doc.get("version") or 0)
        deltas = []
        for p in paths:
            try:
                d = json.loads(p.read_text(encoding="utf-8-sig"))
            except (ValueError, OSError) as exc:
                print("ERROR: %s ilegible: %s" % (p, exc))
                return 1, report
            base = int(d.get("base_version") or 0)
            if base != current:
                print("ERROR: %s tiene base_version %s pero %s esta en version %s — nada mergeado para %s"
                      % (p.name, base, canonical.name, current, name))
                return 1, report
            deltas.append((p, d))
        maxes, widths = {}, {}
        collect_max_ids(doc, maxes, widths)
        mapping_all = {}
        try:
            for p, d in deltas:
                d, mapping = renumber(d, maxes, widths)
                mapping_all.update(mapping)
                doc = merge_one(doc, d)
                collect_max_ids(d, maxes, widths)
        except DeltaError as exc:
            print("ERROR en %s: %s — nada mergeado para %s" % (name, exc, name))
            return 1, report
        ids = []
        for key, lst in doc.items():
            if isinstance(lst, list):
                ids += [it.get("id") for it in lst if isinstance(it, dict) and it.get("id")]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            print("ERROR en %s: ids duplicados tras el merge: %s" % (name, ", ".join(dupes)))
            return 1, report
        doc["version"] = current + 1
        meta = doc.get("metadata")
        if isinstance(meta, dict):
            meta["updated_at"] = datetime.date.today().isoformat()
        recompute_summary(name, doc, folder)
        report[name] = {"deltas": [p.name for p, _ in deltas], "version": doc["version"], "renumbered": mapping_all, "created": created}
        if not dry_run:
            canonical.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            for p, _ in deltas:
                p.unlink()
        if not quiet:
            print("%s: %d delta(s) mergeados -> version %d%s%s" % (
                canonical.name, len(deltas), doc["version"], " (creado)" if created else "",
                " [dry-run]" if dry_run else ""))
            for old, new in sorted(mapping_all.items()):
                print("  id %s -> %s" % (old, new))
    return 0, report


# ------------------------------------------------------------ self-test


def self_test():
    import shutil
    import tempfile
    failures = 0

    def check(cond, label):
        nonlocal failures
        print("self-test %s: %s" % ("ok" if cond else "FALLO", label))
        if not cond:
            failures += 1

    tmp = Path(tempfile.mkdtemp(prefix="apply-delta-"))
    try:
        (tmp / "scenarios.json").write_text(json.dumps({
            "version": 3, "metadata": {"updated_at": "2000-01-01"}, "summary": {},
            "scenarios": [{"id": "SCN-001", "scenario_type": "current", "status": "active", "episodes": [{"id": "EP-001"}], "exceptions": [], "lel_symbol_ids": ["LEL-001"]}],
            "open_questions": [{"id": "Q-001", "blocking": True}]}), encoding="utf-8")
        (tmp / "scenarios.FG-02.delta.json").write_text(json.dumps({
            "base_version": 3,
            "adds": {"scenarios": [{"id": "SCN-FG02#1", "scenario_type": "future", "status": "active",
                                    "episodes": [{"id": "EP-FG02#1", "referenced_scenario_id": "SCN-FG02#2"}], "exceptions": []},
                                   {"id": "SCN-FG02#2", "scenario_type": "current", "status": "active", "episodes": [], "exceptions": [{"id": "EXC-FG02#1"}]}]},
            "updates": {"scenarios": [{"id": "SCN-001", "goal": "actualizado"}]},
            "removes": {"open_questions": ["Q-001"]}}), encoding="utf-8")
        (tmp / "scenarios.FG-03.delta.json").write_text(json.dumps({
            "base_version": 3,
            "adds": {"scenarios": [{"id": "SCN-FG03#1", "scenario_type": "current", "status": "active", "episodes": [], "exceptions": []}]}}), encoding="utf-8")
        code, report = apply(tmp, quiet=True)
        check(code == 0, "merge de dos deltas paralelos (exit 0)")
        doc = json.loads((tmp / "scenarios.json").read_text(encoding="utf-8"))
        ids = [s["id"] for s in doc["scenarios"]]
        check(ids == ["SCN-001", "SCN-002", "SCN-003", "SCN-004"], "ids provisionales renumerados en secuencia: %s" % ids)
        check(doc["scenarios"][1]["episodes"][0]["referenced_scenario_id"] == "SCN-003", "citas internas reescritas")
        check(doc["scenarios"][1]["episodes"][0]["id"] == "EP-002", "prefijos anidados renumerados (EP)")
        check(doc["scenarios"][0]["goal"] == "actualizado", "updates aplicado por id")
        check(doc["open_questions"] == [], "removes aplicado")
        check(doc["version"] == 4, "version sube una sola vez con dos deltas")
        check(doc["summary"]["total_scenarios"] == 4 and doc["summary"]["total_exceptions"] == 1, "summary recalculado")
        check(not list(tmp.glob("*.delta.json")), "deltas borrados")

        (tmp / "requirements.delta.json").write_text(json.dumps({"base_version": 7, "adds": {}}), encoding="utf-8")
        code, _ = apply(tmp, quiet=True)
        check(code == 1, "base_version distinta de la actual rechaza el merge")
        (tmp / "requirements.delta.json").unlink()

        (tmp / "source-inventory.a.delta.json").write_text(json.dumps({
            "adds": {"sections": [{"id": "SRC-SEC-a#1", "source": "sources/a.txt"}]}, "set": {"pipeline_version": "1.0"}}), encoding="utf-8")
        (tmp / "source-inventory.b.delta.json").write_text(json.dumps({
            "adds": {"sections": [{"id": "SRC-SEC-b#1", "source": "sources/b.txt"}, {"id": "SRC-SEC-b#2", "source": "sources/b.txt"}]}}), encoding="utf-8")
        code, _ = apply(tmp, quiet=True)
        inv = json.loads((tmp / "source-inventory.json").read_text(encoding="utf-8"))
        check(code == 0 and [s["id"] for s in inv["sections"]] == ["SRC-SEC-001", "SRC-SEC-002", "SRC-SEC-003"],
              "creacion inicial desde deltas paralelos con prefijo compuesto")
        check(inv["version"] == 1 and inv["summary"]["section_count"] == 3, "version 1 y summary en la creacion")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST: %d fallo(s)" % failures)
    return 1 if failures else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default=".dev/requirements")
    ap.add_argument("--solo", nargs="+", default=None, help="mergear solo estos canonicos (por nombre sin extension)")
    ap.add_argument("--dry-run", action="store_true", help="mostrar que se haria sin escribir ni borrar")
    args = ap.parse_args(argv)
    folder = Path(args.carpeta)
    if not folder.is_dir():
        print("No existe la carpeta: %s" % folder)
        return 1
    code, _ = apply(folder, args.solo, args.dry_run)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
