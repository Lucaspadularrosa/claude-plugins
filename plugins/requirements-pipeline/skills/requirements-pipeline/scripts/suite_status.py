#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado de la suite en un proyecto: que hay, que falta y que conviene hacer.

Deriva todo de los artefactos en disco, sin estado propio: no hay archivo de
estado que mantener ni que pueda quedar desincronizado. Reusa la lectura que ya
hace `render_index.py` (mapa x plan x build por feature, INC/CR pendientes) en
vez de reimplementarla.

**Es una fuente, no una autoridad.** `siguiente_sugerido` es una recomendacion
derivada de condiciones verificables, no una orden: el orquestador la cita y
decide. Un script no puede saber que quiere hacer el usuario ahora.

Solo stdlib, Python 3.8+. No modifica nada.

Uso:
  python suite_status.py [carpeta-dev] [--json]
  python suite_status.py --self-test

  carpeta-dev  por defecto .dev
  --json       contrato `suite.status/v1` para consumo por script
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_index import estado_changelog, estado_features, load_json, project_name  # noqa: E402

SCHEMA = "suite.status/v1"


def _contar(items, clave, valores):
    out = {v: 0 for v in valores}
    for it in items or []:
        st = it.get(clave)
        if st in out:
            out[st] += 1
    return out


def estado_tarjetas(dev):
    """Tarjetas del camino rapido (.dev/cards/): la deuda de documentacion, visible.

    Una feature construida por tarjeta y nunca promovida es documentacion que se
    posterga sola. Si nadie la cuenta, el atajo se vuelve el camino por defecto.
    """
    carpeta = dev / "cards"
    tarjetas = []
    if carpeta.is_dir():
        for path in sorted(carpeta.glob("FG-*.json")):
            doc = load_json(path) or {}
            if not doc.get("id"):
                continue
            tarjetas.append({"id": doc["id"], "slug": doc.get("slug") or path.stem,
                             "status": doc.get("status") or "drafted",
                             "archivo": path.name})
    por_estado = _contar(tarjetas, "status", ("drafted", "built", "promoted"))
    return {"presente": bool(tarjetas), "tarjetas": tarjetas, "por_estado": por_estado,
            "sin_promover": [t["id"] for t in tarjetas if t["status"] in ("drafted", "built")]}


def estado(dev):
    """El estado completo, como datos."""
    req, plan = dev / "requirements", dev / "plan"
    pmap = load_json(req / "product-map.json")
    tasks = load_json(plan / "tasks.json")
    exec_plan = load_json(plan / "execution-plan.json")
    progress = load_json(plan / "progress.json")

    features = estado_features(dev)
    changelog = estado_changelog(dev) or {"pendientes": [], "no_absorbidos": [], "postergados": []}

    pipelines = {
        "requirements": {
            "presente": bool(pmap),
            "features": _contar((pmap or {}).get("features"), "status",
                                ("stub", "elaborated", "baselined", "deprecated")),
        },
        "plan": {
            "presente": bool(tasks),
            "tareas": len((tasks or {}).get("tasks") or []),
            "lotes": len((exec_plan or {}).get("batches") or []),
        },
        "build": {
            "presente": bool(progress),
            "features": _contar((progress or {}).get("features"), "status",
                                ("pending", "in_progress", "done")),
        },
        "recovery": {"presente": (dev / "recovery" / "behavior-map.json").is_file()},
        "audit": {"presente": (dev / "audit" / "audit-report.json").is_file()},
        "fast_track": estado_tarjetas(dev),
    }

    bloqueos = []
    if changelog["pendientes"]:
        bloqueos.append("%d INC/CR sin aplicar a la linea de base: %s" % (
            len(changelog["pendientes"]),
            ", ".join(e.get("id", "?") for e in changelog["pendientes"])))
    if changelog["no_absorbidos"]:
        bloqueos.append("%d cambio(s) aplicado(s) a los requisitos que el plan no absorbio: %s" % (
            len(changelog["no_absorbidos"]),
            ", ".join(e.get("id", "?") for e in changelog["no_absorbidos"])))
    sin_tareas = [f["id"] for f in features if f["mapa"] == "baselined" and not f["plan"]]
    if sin_tareas:
        bloqueos.append("%d feature(s) baselineada(s) sin tareas en el plan: %s" % (
            len(sin_tareas), ", ".join(sin_tareas)))
    huerfanas = [f["id"] for f in features if f["plan"] and f["mapa"] is None]
    if huerfanas:
        bloqueos.append("%d feature(s) en el plan que no estan en el mapa: %s" % (
            len(huerfanas), ", ".join(huerfanas)))

    reanudable = []
    for e in changelog["pendientes"]:
        if e.get("status") in ("in_progress", "deferred"):
            reanudable.append({"que": e.get("id"), "donde": "changelog", "status": e.get("status")})
    for f in features:
        if f["build"] == "in_progress":
            reanudable.append({"que": f["id"], "donde": "build", "status": "in_progress"})

    return {
        "schema": SCHEMA,
        "project": project_name(dev) or None,
        "pipelines": pipelines,
        "features": features,
        "changelog": {
            "pendientes": [e.get("id") for e in changelog["pendientes"]],
            "no_absorbidos": [e.get("id") for e in changelog["no_absorbidos"]],
            "postergados": changelog["postergados"],
        },
        "bloqueos": bloqueos,
        "siguiente_sugerido": sugerencia(pipelines, features, changelog),
        "reanudable_desde": reanudable,
    }


def sugerencia(pipelines, features, changelog):
    """Primera condicion que aplica. Recomendacion, no enrutado."""
    req, plan, build = pipelines["requirements"], pipelines["plan"], pipelines["build"]

    if not req["presente"]:
        if pipelines["recovery"]["presente"]:
            return {"comando": "/comprender",
                    "porque": "hay diagnostico de recovery pero no linea de base: "
                              "reconstruila (paso opt-in) o arranca con /requerimientos:descubrir"}
        return {"comando": "/requerimientos:descubrir",
                "porque": "no hay mapa del producto todavia"}

    if changelog["no_absorbidos"]:
        return {"comando": "/replanificar",
                "porque": "los requisitos cambiaron y el plan no absorbio esos cambios"}
    if changelog["pendientes"]:
        return {"comando": "/requerimientos:cambio",
                "porque": "hay INC/CR registrados sin aplicar a la linea de base"}

    f = req["features"]
    if f["baselined"] == 0:
        return {"comando": "/requerimientos:incremento",
                "porque": "el mapa tiene %d feature(s) sin baselinear" % (f["stub"] + f["elaborated"])}
    if not plan["presente"]:
        return {"comando": "/planificar",
                "porque": "hay %d feature(s) baselineada(s) y no hay plan" % f["baselined"]}
    if any(x["mapa"] == "baselined" and not x["plan"] for x in features):
        return {"comando": "/replanificar",
                "porque": "hay features baselineadas sin tareas en el plan"}

    b = build["features"]
    if not build["presente"] or b["pending"] or b["in_progress"]:
        pend = b["pending"] + b["in_progress"]
        return {"comando": "/construir-lote",
                "porque": "quedan %d feature(s) por construir" % pend if pend
                          else "el plan esta listo y no arranco el build"}
    if f["stub"] or f["elaborated"]:
        return {"comando": "/requerimientos:incremento",
                "porque": "lo planificado esta construido; quedan %d feature(s) sin baselinear"
                          % (f["stub"] + f["elaborated"])}
    sin_promover = pipelines["fast_track"]["sin_promover"]
    if sin_promover:
        return {"comando": "/requerimientos:promover %s" % " ".join(sin_promover),
                "porque": "%d feature(s) del camino rapido siguen sin linea de base"
                          % len(sin_promover)}
    return {"comando": "/auditar",
            "porque": "no hay trabajo pendiente en el plan: auditar o documentar"}


def texto(est):
    out = ["Estado de la suite%s" % (" - %s" % est["project"] if est["project"] else ""), ""]
    p = est["pipelines"]
    out.append("  requisitos  %s  features: %s" % (
        "si" if p["requirements"]["presente"] else "no ",
        ", ".join("%s %d" % (k, v) for k, v in p["requirements"]["features"].items() if v)or "-"))
    out.append("  plan        %s  %d tarea(s), %d lote(s)" % (
        "si" if p["plan"]["presente"] else "no ", p["plan"]["tareas"], p["plan"]["lotes"]))
    out.append("  build       %s  features: %s" % (
        "si" if p["build"]["presente"] else "no ",
        ", ".join("%s %d" % (k, v) for k, v in p["build"]["features"].items() if v) or "-"))
    out.append("  recovery    %s" % ("si" if p["recovery"]["presente"] else "no"))
    out.append("  audit       %s" % ("si" if p["audit"]["presente"] else "no"))
    ft = p.get("fast_track") or {"presente": False}
    if ft["presente"]:
        out.append("  tarjetas    si  %s" % (
            ", ".join("%s %d" % (k, v) for k, v in ft["por_estado"].items() if v) or "-"))
    out.append("")
    if ft.get("sin_promover"):
        out.append("Deuda del camino rapido: %d feature(s) construida(s) sin linea de base (%s)"
                   % (len(ft["sin_promover"]), ", ".join(ft["sin_promover"])))
        out.append("  se salda con /requerimientos:promover")
        out.append("")
    if est["bloqueos"]:
        out.append("Bloqueos:")
        for b in est["bloqueos"]:
            out.append("  - %s" % b)
        out.append("")
    if est["reanudable_desde"]:
        out.append("Reanudable: %s" % ", ".join(
            "%s (%s, %s)" % (r["que"], r["donde"], r["status"]) for r in est["reanudable_desde"]))
        out.append("")
    s = est["siguiente_sugerido"]
    out.append("Sugerido: %s" % s["comando"])
    out.append("  %s" % s["porque"])
    out.append("")
    out.append("(Sugerencia derivada de los artefactos, no una orden: decidi vos.)")
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default=".dev")
    ap.add_argument("--json", action="store_true", help="emite el contrato suite.status/v1")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    dev = Path(args.carpeta)
    if not dev.is_dir():
        if args.json:
            print(json.dumps({"schema": SCHEMA, "project": None, "pipelines": {}, "features": [],
                              "changelog": {"pendientes": [], "no_absorbidos": [], "postergados": []},
                              "bloqueos": ["no existe %s" % dev], "reanudable_desde": [],
                              "siguiente_sugerido": {
                                  "comando": "/requerimientos:descubrir",
                                  "porque": "el proyecto no tiene .dev/: la suite no corrio aca"}},
                             ensure_ascii=False, indent=2))
        else:
            print("No existe %s: la suite no corrio en este proyecto." % dev)
            print("Arranca con /requerimientos:descubrir, o /comprender si ya hay codigo.")
        return 0

    est = estado(dev)
    print(json.dumps(est, ensure_ascii=False, indent=2) if args.json else texto(est))
    return 0


# ------------------------------------------------------------------ self-test

def self_test():
    import shutil
    import tempfile

    fallos = 0

    def check(nombre, got, want):
        nonlocal fallos
        if got == want:
            print("self-test ok (%s)" % nombre)
        else:
            print("SELF-TEST FALLO (%s): %r != %r" % (nombre, got, want))
            fallos += 1

    def escenario(tmp, **archivos):
        dev = tmp / ".dev"
        for rel, doc in archivos.items():
            p = dev / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc), encoding="utf-8")
        return dev

    tmp = Path(tempfile.mkdtemp(prefix="suite-status-"))
    try:
        # 1. solo mapa con stubs -> elaborar
        dev = escenario(tmp / "a", **{"requirements/product-map.json": {
            "version": 1, "features": [{"id": "FG-01", "status": "stub"}]}})
        check("mapa con stubs sugiere elaborar",
              estado(dev)["siguiente_sugerido"]["comando"], "/requerimientos:incremento")

        # 2. baselineado sin plan -> planificar
        dev = escenario(tmp / "b", **{"requirements/product-map.json": {
            "version": 1, "features": [{"id": "FG-01", "status": "baselined"}]}})
        est = estado(dev)
        check("baselineado sin plan sugiere planificar",
              est["siguiente_sugerido"]["comando"], "/planificar")
        check("y lo reporta como bloqueo", len(est["bloqueos"]), 1)

        # 3. cambio aplicado que el plan no absorbio -> replanificar
        dev = escenario(tmp / "c", **{
            "requirements/product-map.json": {"version": 1, "features": [{"id": "FG-01", "status": "baselined"}]},
            "requirements/changelog.json": {"version": 1, "entries": [
                {"id": "INC-002", "kind": "increment", "status": "applied"}]},
            "plan/tasks.json": {"version": 1, "features": [{"id": "FG-01"}], "tasks": [{"id": "T-001"}]},
        })
        est = estado(dev)
        check("cambio no absorbido sugiere replanificar",
              est["siguiente_sugerido"]["comando"], "/replanificar")
        check("lo lista en changelog.no_absorbidos", est["changelog"]["no_absorbidos"], ["INC-002"])

        # 4. build a medias -> construir, y reanudable
        dev = escenario(tmp / "d", **{
            "requirements/product-map.json": {"version": 1, "features": [{"id": "FG-01", "status": "baselined"}]},
            "plan/tasks.json": {"version": 1, "features": [{"id": "FG-01"}], "tasks": [{"id": "T-001"}]},
            "plan/progress.json": {"version": 1, "features": [{"feature_id": "FG-01", "status": "in_progress"}]},
        })
        est = estado(dev)
        check("build a medias sugiere construir",
              est["siguiente_sugerido"]["comando"], "/construir-lote")
        check("marca la feature como reanudable",
              [r["que"] for r in est["reanudable_desde"]], ["FG-01"])

        # 5. todo hecho -> auditar, sin bloqueos
        dev = escenario(tmp / "e", **{
            "requirements/product-map.json": {"version": 1, "features": [{"id": "FG-01", "status": "baselined"}]},
            "plan/tasks.json": {"version": 1, "features": [{"id": "FG-01"}], "tasks": [{"id": "T-001"}]},
            "plan/progress.json": {"version": 1, "features": [{"feature_id": "FG-01", "status": "done"}]},
        })
        est = estado(dev)
        check("todo construido sugiere auditar", est["siguiente_sugerido"]["comando"], "/auditar")

        # 6. camino rapido: una tarjeta construida y nunca promovida es deuda visible
        dev = escenario(tmp / "f", **{
            "requirements/product-map.json": {"version": 1, "features": [{"id": "FG-01", "status": "baselined"}]},
            "plan/tasks.json": {"version": 1, "features": [{"id": "FG-01"}], "tasks": [{"id": "T-001"}]},
            "plan/progress.json": {"version": 1, "features": [{"feature_id": "FG-01", "status": "done"}]},
            "cards/FG-07-alta.json": {"id": "FG-07", "slug": "alta", "status": "built"},
            "cards/FG-08-baja.json": {"id": "FG-08", "slug": "baja", "status": "promoted"},
        })
        est = estado(dev)
        check("tarjeta sin promover sugiere promoverla",
              est["siguiente_sugerido"]["comando"], "/requerimientos:promover FG-07")
        check("cuenta las tarjetas por estado",
              est["pipelines"]["fast_track"]["por_estado"], {"drafted": 0, "built": 1, "promoted": 1})
        check("la deuda aparece en el texto",
              "Deuda del camino rapido" in texto(est), True)
        check("sin bloqueos", est["bloqueos"], [])
        check("el contrato lleva schema", est["schema"], SCHEMA)

        # 6. proyecto sin .dev
        check("sin .dev no explota", main([str(tmp / "no-existe"), "--json"]), 0)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
