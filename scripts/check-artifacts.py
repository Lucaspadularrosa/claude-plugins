#!/usr/bin/env python3
"""Verificador de artefactos de la suite (.dev/ de un proyecto).

Comprueba que los artefactos que la suite genero en un proyecto respetan sus
contratos: JSON valido, formatos de id, enums de estado y referencias cruzadas
(requisitos que citan escenarios existentes, lotes que citan tareas existentes,
etc.). Es la mitad automatizable del test dorado (tests/golden/): los prompts
prometen estos contratos; esto verifica que una corrida real los cumplio.

Solo stdlib, Python 3.8+. No modifica nada.

Uso:
  python scripts/check-artifacts.py <raiz-del-proyecto> [--stage requirements|plan|build|all]
  python scripts/check-artifacts.py --self-test

Salida: problemas (rompen el contrato: exit 1) y avisos (senales, exit 0).
"""

import json
import re
import sys
from pathlib import Path

ID_RE = {
    "FG": re.compile(r"^FG-\d+$"),
    "SYM": re.compile(r"^SYM-\d+$"),
    "SCN": re.compile(r"^SCN-\d+$"),
    "RF": re.compile(r"^RF-\d+$"),
    "RNF": re.compile(r"^RNF-\d+$"),
    "REQ": re.compile(r"^R(F|NF)-\d+$"),
    "AC": re.compile(r"^AC-\d+$"),
    "T": re.compile(r"^T-\d+$"),
    "BATCH": re.compile(r"^BATCH-\d+$"),
    "CHG": re.compile(r"^(DSC|INC|CR|REC)-\d+$"),
    "BR": re.compile(r"^BR-\d+$"),
}

MAP_STATUSES = {"stub", "elaborated", "baselined", "deprecated"}
ITEM_STATUSES = {"active", "proposed", "deprecated"}
TASK_STATUSES = {"pending", "cancelled"}
PROGRESS_FEATURE_STATUSES = {"pending", "in_progress", "done"}
PROGRESS_TASK_STATUSES = {"pending", "in_progress", "done", "blocked", "cancelled"}
CHANGELOG_STATUSES = {"in_progress", "applied", "rejected"}

problems = []
warnings = []


def problem(where, msg):
    problems.append("{}: {}".format(where, msg))


def warn(where, msg):
    warnings.append("{}: {}".format(where, msg))


def load_json(path):
    """Devuelve el dict parseado, o None (reportando el problema)."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        problem(path.name, "JSON invalido: {}".format(e))
        return None
    if not isinstance(data, dict):
        problem(path.name, "el contenido no es un objeto JSON")
        return None
    return data


def unique_ids(items, key, pattern, where):
    """Valida formato y unicidad de ids; devuelve el set de ids validos."""
    seen = set()
    for item in items:
        iid = item.get(key)
        if not isinstance(iid, str) or not pattern.match(iid):
            problem(where, "id invalido o ausente: {!r}".format(iid))
            continue
        if iid in seen:
            problem(where, "id duplicado: {}".format(iid))
        seen.add(iid)
    return seen


def check_refs(refs, valid, where, what):
    for ref in refs or []:
        if ref not in valid:
            problem(where, "{} cita {} que no existe".format(what, ref))


# ---------------------------------------------------------------- requirements

def check_requirements_stage(dev):
    reqdir = dev / "requirements"
    if not reqdir.is_dir():
        problem(".dev/requirements", "no existe")
        return {}

    ctx = {}

    lel = load_json(reqdir / "lel.json")
    if lel is not None:
        symbols = lel.get("symbols", [])
        ctx["symbols"] = unique_ids(symbols, "id", ID_RE["SYM"], "lel.json/symbols")
        for s in symbols:
            if s.get("status") not in ITEM_STATUSES | {None}:
                problem("lel.json", "{}: status invalido {!r}".format(s.get("id"), s.get("status")))
            check_refs(s.get("related_symbol_ids"), ctx["symbols"], "lel.json", str(s.get("id")))
        ctx["lel_version"] = str(lel.get("version", ""))
    elif (reqdir / "product-map.json").exists():
        problem("lel.json", "no existe (el mapa del producto lo requiere)")

    pmap = load_json(reqdir / "product-map.json")
    elaborated = False
    if pmap is not None:
        features = pmap.get("features", [])
        ctx["map_features"] = unique_ids(features, "id", ID_RE["FG"], "product-map.json/features")
        for f in features:
            fid = f.get("id")
            if f.get("status") not in MAP_STATUSES:
                problem("product-map.json", "{}: status invalido {!r}".format(fid, f.get("status")))
            elif f.get("status") in {"elaborated", "baselined"}:
                elaborated = True
            if f.get("value") not in {"high", "medium", "low", None}:
                problem("product-map.json", "{}: value invalido {!r}".format(fid, f.get("value")))
            if "symbols" in ctx:
                check_refs(f.get("lel_symbol_ids"), ctx["symbols"], "product-map.json", str(fid))
        counts = {s: sum(1 for f in features if f.get("status") == s) for s in MAP_STATUSES}
        summary = pmap.get("summary", {})
        for status, n in counts.items():
            declared = summary.get(status + "_count")
            if declared is not None and declared != n:
                problem("product-map.json", "summary.{}_count={} pero hay {}".format(status, declared, n))

    scn = load_json(reqdir / "scenarios.json")
    if scn is not None:
        scenarios = scn.get("scenarios", [])
        ctx["scenarios"] = unique_ids(scenarios, "id", ID_RE["SCN"], "scenarios.json")
        for s in scenarios:
            sid = s.get("id")
            if s.get("status") not in ITEM_STATUSES:
                problem("scenarios.json", "{}: status invalido {!r}".format(sid, s.get("status")))
            if "symbols" in ctx:
                check_refs(s.get("lel_symbol_ids"), ctx["symbols"], "scenarios.json", str(sid))
                for actor in s.get("actors", []):
                    ref = actor.get("lel_symbol_id")
                    if ref and ref not in ctx["symbols"]:
                        problem("scenarios.json", "{}: actor cita {} que no existe en el LEL".format(sid, ref))
        if ctx.get("lel_version") and str(scn.get("metadata", {}).get("lel_version_ref")) != ctx["lel_version"]:
            warn("scenarios.json", "lel_version_ref desactualizado (LEL en version {})".format(ctx["lel_version"]))
    elif elaborated:
        problem("scenarios.json", "no existe pero el mapa tiene features elaboradas/baselineadas")

    reqs = load_json(reqdir / "requirements.json")
    if reqs is not None:
        groups = reqs.get("feature_groups", [])
        group_ids = unique_ids(groups, "id", ID_RE["FG"], "requirements.json/feature_groups")
        all_reqs = list(reqs.get("functional_requirements", [])) + list(reqs.get("non_functional_requirements", []))
        ctx["requirements"] = unique_ids(all_reqs, "id", ID_RE["REQ"], "requirements.json")
        for g in groups:
            check_refs(g.get("requirement_ids"), ctx["requirements"], "requirements.json", str(g.get("id")))
            if "scenarios" in ctx:
                check_refs(g.get("scenario_ids"), ctx["scenarios"], "requirements.json", str(g.get("id")))
        for r in all_reqs:
            rid = r.get("id")
            if r.get("feature_group") not in group_ids:
                problem("requirements.json", "{}: feature_group {!r} no existe".format(rid, r.get("feature_group")))
            if r.get("status") not in ITEM_STATUSES:
                problem("requirements.json", "{}: status invalido {!r}".format(rid, r.get("status")))
            acs = r.get("acceptance_criteria", [])
            if not acs:
                problem("requirements.json", "{}: sin criterios de aceptacion".format(rid))
            unique_ids(acs, "id", ID_RE["AC"], "requirements.json/{}".format(rid))
            for ac in acs:
                if not all(isinstance(ac.get(k), str) and ac.get(k) for k in ("given", "when", "then")):
                    problem("requirements.json", "{}/{}: criterio sin given/when/then completos".format(rid, ac.get("id")))
            check_refs(r.get("depends_on"), ctx["requirements"], "requirements.json", str(rid))
            if "scenarios" in ctx:
                check_refs(r.get("source_scenario_ids"), ctx["scenarios"], "requirements.json", str(rid))
            if "symbols" in ctx:
                check_refs(r.get("lel_symbol_ids"), ctx["symbols"], "requirements.json", str(rid))
        ac_by_req = {r.get("id"): {ac.get("id") for ac in r.get("acceptance_criteria", [])} for r in all_reqs}
        rules = reqs.get("business_rules", [])
        unique_ids(rules, "id", ID_RE["BR"], "requirements.json/business_rules")
        for br in rules:
            bid = br.get("id")
            if br.get("kind") not in {"invariant", "constraint", "derivation"}:
                problem("requirements.json", "{}: kind invalido {!r}".format(bid, br.get("kind")))
            for ref in br.get("enforced_by", []):
                parts = ref.split("/", 1)
                if len(parts) != 2 or parts[0] not in ac_by_req or parts[1] not in ac_by_req[parts[0]]:
                    problem("requirements.json", "{}: enforced_by cita {} que no existe".format(bid, ref))
            if not br.get("enforced_by") and not br.get("open_questions"):
                warn("requirements.json", "{}: regla sin criterio que la demuestre ni pregunta abierta".format(bid))
    elif elaborated:
        problem("requirements.json", "no existe pero el mapa tiene features elaboradas/baselineadas")

    chlog = load_json(reqdir / "changelog.json")
    if chlog is not None:
        entries = chlog.get("entries", [])
        unique_ids(entries, "id", ID_RE["CHG"], "changelog.json")
        for e in entries:
            if e.get("status") not in CHANGELOG_STATUSES:
                problem("changelog.json", "{}: status invalido {!r}".format(e.get("id"), e.get("status")))
    elif pmap is not None:
        warn("changelog.json", "no existe (toda corrida deberia registrar su DSC/INC/CR/REC)")

    return ctx


# ------------------------------------------------------------------------ plan

def check_plan_stage(dev, ctx):
    plandir = dev / "plan"
    if not plandir.is_dir():
        warn(".dev/plan", "no existe (etapa de planificacion no corrida)")
        return

    tasks_doc = load_json(plandir / "tasks.json")
    task_ids = set()
    feature_ids = set()
    active_task_ids = set()
    if tasks_doc is None:
        problem("tasks.json", "no existe o no parsea")
    else:
        features = tasks_doc.get("features", [])
        feature_ids = unique_ids(features, "id", ID_RE["FG"], "tasks.json/features")
        tasks = tasks_doc.get("tasks", [])
        task_ids = unique_ids(tasks, "id", ID_RE["T"], "tasks.json/tasks")
        for t in tasks:
            tid = t.get("id")
            if t.get("feature_group") not in feature_ids:
                problem("tasks.json", "{}: feature_group {!r} no existe".format(tid, t.get("feature_group")))
            if t.get("status") not in TASK_STATUSES:
                problem("tasks.json", "{}: status invalido {!r}".format(tid, t.get("status")))
            elif t.get("status") != "cancelled":
                active_task_ids.add(tid)
            for dep in t.get("depends_on", []):
                if not isinstance(dep, dict) or dep.get("kind") not in {"hard", "contract"}:
                    problem("tasks.json", "{}: depends_on con formato viejo o kind invalido: {!r}".format(tid, dep))
                elif dep.get("task_id") not in task_ids:
                    problem("tasks.json", "{}: depende de {} que no existe".format(tid, dep.get("task_id")))
            if ctx.get("requirements"):
                check_refs(t.get("requirement_ids"), ctx["requirements"], "tasks.json", str(tid))
        for f in features:
            check_refs(f.get("task_ids"), task_ids, "tasks.json", str(f.get("id")))

    plan = load_json(plandir / "execution-plan.json")
    if plan is None:
        problem("execution-plan.json", "no existe o no parsea")
    else:
        placed = []
        contract = plan.get("contract_round") or {}
        placed += [t for t in contract.get("task_ids", [])]
        batch_ids = {contract.get("id", "BATCH-0")}
        for b in plan.get("batches", []):
            bid = b.get("id")
            if not isinstance(bid, str) or not ID_RE["BATCH"].match(bid):
                problem("execution-plan.json", "lote con id invalido: {!r}".format(bid))
                continue
            if bid in batch_ids:
                problem("execution-plan.json", "lote duplicado: {}".format(bid))
            batch_ids.add(bid)
            for fentry in b.get("features", []):
                fid = fentry.get("feature_id")
                if feature_ids and fid not in feature_ids:
                    problem("execution-plan.json", "{}: feature {} no existe en tasks.json".format(bid, fid))
                ftasks = fentry.get("task_ids", [])
                forder = fentry.get("task_order", [])
                if sorted(ftasks) != sorted(forder):
                    problem("execution-plan.json", "{}/{}: task_order no es una permutacion de task_ids".format(bid, fid))
                if task_ids:
                    check_refs(ftasks, task_ids, "execution-plan.json", "{}/{}".format(bid, fid))
                placed += list(ftasks)
        for b in plan.get("batches", []):
            for prev in b.get("unlocks_after", []):
                if prev not in batch_ids:
                    problem("execution-plan.json", "{}: unlocks_after cita {} que no existe".format(b.get("id"), prev))
        dupes = {t for t in placed if placed.count(t) > 1}
        for t in sorted(dupes):
            problem("execution-plan.json", "la tarea {} aparece en mas de un lote".format(t))
        if active_task_ids:
            missing = active_task_ids - set(placed)
            for t in sorted(missing):
                problem("execution-plan.json", "la tarea activa {} no cae en ningun lote: no la construye nadie".format(t))

    progress = load_json(plandir / "progress.json")
    if progress is not None:
        for f in progress.get("features", []):
            if feature_ids and f.get("feature_id") not in feature_ids:
                problem("progress.json", "feature {} no existe en el plan".format(f.get("feature_id")))
            if f.get("status") not in PROGRESS_FEATURE_STATUSES:
                problem("progress.json", "{}: status invalido {!r}".format(f.get("feature_id"), f.get("status")))
        for t in progress.get("tasks", []):
            if task_ids and t.get("task_id") not in task_ids:
                problem("progress.json", "tarea {} no existe en el plan".format(t.get("task_id")))
            if t.get("status") not in PROGRESS_TASK_STATUSES:
                problem("progress.json", "{}: status invalido {!r}".format(t.get("task_id"), t.get("status")))

    featdir = dev.parent / ".dev" / "features"
    briefs = list(featdir.glob("*.md")) if featdir.is_dir() else []
    if feature_ids and len(briefs) < len(feature_ids):
        warn(".dev/features", "hay {} briefs para {} features del plan".format(len(briefs), len(feature_ids)))


# ----------------------------------------------------------------------- build

def check_build_stage(dev):
    builddir = dev / "build"
    if not builddir.is_dir():
        warn(".dev/build", "no existe (etapa de build no corrida)")
        return

    profile = load_json(builddir / "stack-profile.json")
    if profile is not None:
        cmds = profile.get("commands", {})
        if not (cmds.get("test") or {}).get("command"):
            warn("stack-profile.json", "sin comando de test (deberia ser open_question)")
        if not profile.get("integration_branch"):
            warn("stack-profile.json", "sin rama de integracion")
        if "ci" not in profile:
            warn("stack-profile.json", "sin campo ci (perfil anterior a los checks independientes)")

    baseline = load_json(builddir / "security-baseline.json")
    if baseline is not None:
        applicable = set(baseline.get("applicable_categories", []))
        declared = {c.get("owasp_id") for c in baseline.get("controls", [])}
        if "A04" in applicable:
            problem("security-baseline.json", "A04 no va en applicable_categories: llega como RNF/criterios del brief")
        for cat in sorted(applicable - declared):
            problem("security-baseline.json", "categoria aplicable {} sin control declarado".format(cat))
        if profile is not None:
            ref = str(baseline.get("metadata", {}).get("stack_profile_version_ref"))
            if ref != str(profile.get("version")):
                warn("security-baseline.json", "stack_profile_version_ref desactualizado")

    for sub, key in (("reviews", "passed"), ("security", "passed")):
        d = builddir / sub
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                verdict = load_json(f)
                if verdict is not None and not isinstance(verdict.get(key), bool):
                    problem("{}/{}".format(sub, f.name), "veredicto sin campo {} booleano".format(key))


# ------------------------------------------------------------------- self-test

def self_test():
    """Corre los chequeos sobre una mini linea de base embebida: una consistente
    (0 problemas) y una rota (referencias cruzadas invalidas: >0 problemas)."""
    import shutil
    import tempfile

    def fixture(root, break_it):
        req = root / ".dev" / "requirements"
        req.mkdir(parents=True)
        (req / "lel.json").write_text(json.dumps({
            "version": 1,
            "symbols": [{"id": "SYM-001", "canonical_name": "turno", "status": "active"}],
        }), encoding="utf-8")
        (req / "product-map.json").write_text(json.dumps({
            "version": 1,
            "summary": {"stub_count": 0, "elaborated_count": 0, "baselined_count": 1, "deprecated_count": 0},
            "features": [{"id": "FG-01", "status": "baselined", "lel_symbol_ids": ["SYM-001"]}],
        }), encoding="utf-8")
        (req / "scenarios.json").write_text(json.dumps({
            "version": 1, "metadata": {"lel_version_ref": "1"},
            "scenarios": [{"id": "SCN-001", "status": "active", "lel_symbol_ids": ["SYM-001"]}],
        }), encoding="utf-8")
        (req / "requirements.json").write_text(json.dumps({
            "version": 1, "metadata": {"lel_version_ref": "1"},
            "feature_groups": [{"id": "FG-01", "scenario_ids": ["SCN-001"], "requirement_ids": ["RF-001"]}],
            "functional_requirements": [{
                "id": "RF-001", "feature_group": "FG-01", "status": "active",
                "acceptance_criteria": [{"id": "AC-001", "given": "g", "when": "w", "then": "t"}],
                "source_scenario_ids": ["SCN-999" if break_it else "SCN-001"],
            }],
            "non_functional_requirements": [],
        }), encoding="utf-8")
        (req / "changelog.json").write_text(json.dumps({
            "version": 1, "entries": [{"id": "DSC-001", "status": "applied"}],
        }), encoding="utf-8")
        plan = root / ".dev" / "plan"
        plan.mkdir(parents=True)
        (plan / "tasks.json").write_text(json.dumps({
            "version": 1,
            "features": [{"id": "FG-01", "task_ids": ["T-001"]}],
            "tasks": [{"id": "T-001", "feature_group": "FG-01", "status": "pending",
                       "depends_on": [], "requirement_ids": ["RF-001"]}],
        }), encoding="utf-8")
        (plan / "execution-plan.json").write_text(json.dumps({
            "version": 1,
            "contract_round": {"id": "BATCH-0", "task_ids": []},
            "batches": [{"id": "BATCH-1", "unlocks_after": ["BATCH-0"], "features": [
                {"feature_id": "FG-01", "task_ids": [] if break_it else ["T-001"],
                 "task_order": [] if break_it else ["T-001"]}]}],
        }), encoding="utf-8")

    failures = 0
    for break_it, expect_problems in ((False, False), (True, True)):
        tmp = Path(tempfile.mkdtemp(prefix="check-artifacts-"))
        try:
            fixture(tmp, break_it)
            del problems[:]
            del warnings[:]
            ctx = check_requirements_stage(tmp / ".dev")
            check_plan_stage(tmp / ".dev", ctx)
            got = bool(problems)
            label = "fixture rota" if break_it else "fixture consistente"
            if got != expect_problems:
                print("SELF-TEST FALLO ({}): problemas={}".format(label, problems or "ninguno"))
                failures += 1
            else:
                print("self-test ok ({}): {} problema(s)".format(label, len(problems)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    del problems[:]
    del warnings[:]
    return 1 if failures else 0


# ------------------------------------------------------------------------ main

def main():
    args = [a for a in sys.argv[1:]]
    if "--self-test" in args:
        return self_test()

    stage = "all"
    if "--stage" in args:
        i = args.index("--stage")
        stage = args[i + 1] if i + 1 < len(args) else "all"
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 2
    root = Path(args[0]).resolve()
    dev = root / ".dev"
    if not dev.is_dir():
        print("{}: no tiene .dev/ (nada que verificar)".format(root))
        return 1

    ctx = {}
    if stage in ("requirements", "plan", "all"):
        ctx = check_requirements_stage(dev)
    if stage in ("plan", "all"):
        check_plan_stage(dev, ctx)
    if stage in ("build", "all"):
        check_build_stage(dev)

    if warnings:
        print("{} aviso(s):".format(len(warnings)))
        for w in warnings:
            print("  ~ {}".format(w))
    if problems:
        print("{} problema(s) de contrato:".format(len(problems)))
        for p in problems:
            print("  - {}".format(p))
        return 1
    print("Contratos OK (etapa: {}).".format(stage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
