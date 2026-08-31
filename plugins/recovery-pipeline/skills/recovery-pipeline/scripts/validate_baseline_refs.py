#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validacion determinista de referencias cruzadas de la linea de base reconstruida.

Lo que `baseline-reconstruction` verificaba a mano "antes de terminar" (que cada
FG, SCN, RF/RNF, LEL, ENT y MOD citado exista) es un cruce de ids: lo hace este
script con exit code, sin tokens. Tambien chequea que los JSON parseen y que las
reglas propias de la reconstruccion se cumplan:
  - toda feature del product-map tiene `capability_refs` (los usa el backfill);
  - ningun requisito `active` sale de una feature `stub`;
  - `feature_groups` de requirements y `features` del product-map comparten ids.

Referencias que valida (si el artefacto existe):
  product-map     features[].lel_symbol_ids -> LEL; scenario_stubs[].id vs scenarios
  scenarios       scenarios[].evidence_refs -> LEL|NOT|IMP|OWN|code_ref
  requirements    feature_groups[].scenario_ids -> SCN; requirement_ids -> RF|RNF;
                  RF/RNF.feature_group -> FG; evidence_refs -> SCN|LEL|OWN|code_ref
  data-model      entities[].lel_symbol_id -> LEL; source_requirement_ids -> RF|RNF;
                  relationships from/to -> ENT
  technical-design modules[].feature_group -> FG; requirement_ids -> RF|RNF;
                  entity_ids -> ENT; depends_on -> MOD; api/screens requirement_ids

Un `code_ref` (contiene `:` seguido de digitos, o una ruta con `/` o `.`) siempre es
valido: es la traza al codigo.

Solo stdlib, Python 3.8+. No modifica nada.

Uso:
  python validate_baseline_refs.py [carpeta-requirements] [--json]
  python validate_baseline_refs.py --self-test

Salida: problemas (uno por linea) y resumen. Exit 1 si hay problemas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CODE_REF = re.compile(r"^[^\s]+:\d+(-\d+)?$|/|\.[a-zA-Z0-9]{1,6}$")
FILES = ["product-map", "lel", "scenarios", "requirements", "data-model", "technical-design"]


def load_all(folder):
    docs, problems = {}, []
    for name in FILES:
        p = folder / ("%s.json" % name)
        if not p.exists():
            continue
        try:
            docs[name] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append("%s.json: JSON invalido (%s)" % (name, e))
    return docs, problems


def collect_ids(docs):
    ids = {"FG": set(), "SCN": set(), "RF": set(), "RNF": set(), "LEL": set(), "NOT": set(), "IMP": set(), "ENT": set(), "MOD": set(), "BR": set()}
    pm = docs.get("product-map") or {}
    for f in pm.get("features") or []:
        ids["FG"].add(f.get("id"))
        for s in f.get("scenario_stubs") or []:
            ids["SCN"].add(s.get("id"))
    for s in (docs.get("lel") or {}).get("symbols") or []:
        ids["LEL"].add(s.get("id"))
        for n in s.get("notions") or []:
            ids["NOT"].add(n.get("id"))
        for i in s.get("impacts") or []:
            ids["IMP"].add(i.get("id"))
    for s in (docs.get("scenarios") or {}).get("scenarios") or []:
        ids["SCN"].add(s.get("id"))
    rq = docs.get("requirements") or {}
    for fg in rq.get("feature_groups") or []:
        ids["FG"].add(fg.get("id"))
    for r in rq.get("functional_requirements") or []:
        ids["RF"].add(r.get("id"))
    for r in rq.get("non_functional_requirements") or []:
        ids["RNF"].add(r.get("id"))
    for r in rq.get("business_rules") or []:
        ids["BR"].add(r.get("id"))
    for e in (docs.get("data-model") or {}).get("entities") or []:
        ids["ENT"].add(e.get("id"))
    for m in (docs.get("technical-design") or {}).get("modules") or []:
        ids["MOD"].add(m.get("id"))
    return ids


def check_refs(problems, refs, allowed, ids, where):
    for r in refs or []:
        if r is None:
            continue
        r = str(r)
        if r.startswith("OWN-") or CODE_REF.search(r):
            continue
        prefix = r.split("-")[0]
        if prefix in allowed and r in ids.get(prefix, set()):
            continue
        problems.append("%s: referencia rota `%s` (esperado %s)" % (where, r, "|".join(allowed)))


def validate(docs):
    problems = []
    ids = collect_ids(docs)
    pm = docs.get("product-map")
    status_by_fg = {}
    if pm:
        for f in pm.get("features") or []:
            status_by_fg[f.get("id")] = f.get("status")
            if not f.get("capability_refs"):
                problems.append("product-map %s: sin `capability_refs` (los necesita el backfill del state-report)" % f.get("id"))
            check_refs(problems, f.get("lel_symbol_ids"), ["LEL"], ids, "product-map %s.lel_symbol_ids" % f.get("id"))
            check_refs(problems, f.get("evidence_refs"), ["LEL"], ids, "product-map %s.evidence_refs" % f.get("id"))
    if docs.get("scenarios"):
        for s in docs["scenarios"].get("scenarios") or []:
            check_refs(problems, s.get("evidence_refs"), ["LEL", "NOT", "IMP"], ids, "scenarios %s.evidence_refs" % s.get("id"))
            for ep in s.get("episodes") or []:
                check_refs(problems, ep.get("referenced_symbol_ids"), ["LEL"], ids, "scenarios %s/%s.referenced_symbol_ids" % (s.get("id"), ep.get("id")))
    rq = docs.get("requirements")
    if rq:
        fg_ids_req = {fg.get("id") for fg in rq.get("feature_groups") or []}
        if pm:
            for fg in fg_ids_req - {f.get("id") for f in pm.get("features") or []}:
                problems.append("requirements feature_group %s no existe en product-map" % fg)
        for fg in rq.get("feature_groups") or []:
            check_refs(problems, fg.get("scenario_ids"), ["SCN"], ids, "requirements %s.scenario_ids" % fg.get("id"))
            check_refs(problems, fg.get("requirement_ids"), ["RF", "RNF"], ids, "requirements %s.requirement_ids" % fg.get("id"))
        for r in (rq.get("functional_requirements") or []) + (rq.get("non_functional_requirements") or []):
            check_refs(problems, [r.get("feature_group")], ["FG"], ids, "requirements %s.feature_group" % r.get("id"))
            check_refs(problems, r.get("evidence_refs"), ["SCN", "LEL", "OWN"], ids, "requirements %s.evidence_refs" % r.get("id"))
            if r.get("status") == "active" and status_by_fg.get(r.get("feature_group")) == "stub":
                problems.append("requirements %s: `active` dentro de la feature stub %s" % (r.get("id"), r.get("feature_group")))
    dm = docs.get("data-model")
    if dm:
        for e in dm.get("entities") or []:
            check_refs(problems, [e.get("lel_symbol_id")] if e.get("lel_symbol_id") else [], ["LEL"], ids, "data-model %s.lel_symbol_id" % e.get("id"))
            check_refs(problems, e.get("source_requirement_ids"), ["RF", "RNF"], ids, "data-model %s.source_requirement_ids" % e.get("id"))
        for rel in dm.get("relationships") or []:
            check_refs(problems, [rel.get("from_entity_id"), rel.get("to_entity_id")], ["ENT"], ids, "data-model %s" % rel.get("id"))
    td = docs.get("technical-design")
    if td:
        for m in td.get("modules") or []:
            check_refs(problems, [m.get("feature_group")] if m.get("feature_group") else [], ["FG"], ids, "technical-design %s.feature_group" % m.get("id"))
            check_refs(problems, m.get("requirement_ids"), ["RF", "RNF"], ids, "technical-design %s.requirement_ids" % m.get("id"))
            check_refs(problems, m.get("entity_ids"), ["ENT"], ids, "technical-design %s.entity_ids" % m.get("id"))
            check_refs(problems, m.get("depends_on"), ["MOD"], ids, "technical-design %s.depends_on" % m.get("id"))
        for key in ("api_contracts", "screens", "decisions"):
            for x in td.get(key) or []:
                check_refs(problems, x.get("requirement_ids"), ["RF", "RNF"], ids, "technical-design %s.requirement_ids" % x.get("id"))
    counts = {k: len(v) for k, v in ids.items() if v}
    return problems, counts


def self_test():
    checks = []
    docs = {
        "product-map": {"features": [{"id": "FG-01", "status": "stub", "capability_refs": ["CAP-001"], "lel_symbol_ids": ["LEL-001"], "evidence_refs": ["LEL-001"], "scenario_stubs": [{"id": "SCN-001"}]},
                                     {"id": "FG-02", "status": "baselined", "capability_refs": [], "lel_symbol_ids": ["LEL-999"]}]},
        "lel": {"symbols": [{"id": "LEL-001", "notions": [{"id": "NOT-001"}], "impacts": [{"id": "IMP-001"}]}]},
        "scenarios": {"scenarios": [{"id": "SCN-001", "evidence_refs": ["LEL-001", "IMP-001", "src/a.js:12"], "episodes": [{"id": "EP-001", "referenced_symbol_ids": ["LEL-001"]}]}]},
        "requirements": {"feature_groups": [{"id": "FG-01", "scenario_ids": ["SCN-001"], "requirement_ids": ["RF-001"]}, {"id": "FG-03", "scenario_ids": [], "requirement_ids": []}],
                         "functional_requirements": [{"id": "RF-001", "feature_group": "FG-01", "status": "active", "evidence_refs": ["SCN-001", "OWN-003"]}]},
        "data-model": {"entities": [{"id": "ENT-001", "lel_symbol_id": "LEL-001", "source_requirement_ids": ["RF-001"]}], "relationships": [{"id": "REL-001", "from_entity_id": "ENT-001", "to_entity_id": "ENT-002"}]},
        "technical-design": {"modules": [{"id": "MOD-001", "feature_group": "FG-01", "requirement_ids": ["RF-001"], "entity_ids": ["ENT-001"], "depends_on": ["MOD-002"]}]},
    }
    problems, counts = validate(docs)
    joined = "\n".join(problems)
    checks.append(("LEL-999 rota", "LEL-999" in joined))
    checks.append(("FG-02 sin capability_refs", "FG-02: sin `capability_refs`" in joined))
    checks.append(("FG-03 no existe", "FG-03 no existe" in joined))
    checks.append(("active en stub", "`active` dentro de la feature stub FG-01" in joined))
    checks.append(("ENT-002 rota", "ENT-002" in joined))
    checks.append(("MOD-002 rota", "MOD-002" in joined))
    checks.append(("code_ref y OWN validos", "src/a.js" not in joined and "OWN-003" not in joined))
    checks.append(("conteos", counts.get("LEL") == 1 and counts.get("SCN") == 1))
    checks.append(("exactamente 6 problemas", len(problems) == 6))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s\n%s" % (failed, joined))
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("carpeta", nargs="?", default=".dev/requirements")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    folder = Path(args.carpeta)
    if not folder.exists():
        print("error: no existe %s" % folder)
        return 1
    docs, problems = load_all(folder)
    if not docs:
        print("error: no hay artefactos JSON en %s" % folder)
        return 1
    more, counts = validate(docs)
    problems += more
    for p in problems:
        print("problema: %s" % p)
    print("validacion: %d artefactos, ids %s, %d problemas" % (len(docs), ", ".join("%s %d" % kv for kv in sorted(counts.items())), len(problems)))
    if args.json:
        print(json.dumps({"problems": problems, "counts": counts}, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
