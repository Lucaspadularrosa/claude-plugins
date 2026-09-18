#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica que una etapa dejo lo que prometio antes de seguir con la siguiente.

Un subagente puede terminar sin reporte (un 429, un corte, un Task que devuelve
solo el resultado de una herramienta) y el orquestador no se entera: el contrato
de retorno es prosa, nadie lo valida. Lo que si se puede verificar sin modelo es
el rastro en disco. Este script es esa compuerta: cada artefacto esperado existe,
no esta vacio y parsea.

No reemplaza a `check-artifacts.py`, que verifica el CONTENIDO contra los
contratos de la suite (ids, enums, referencias cruzadas). Este mira antes y mas
barato: que la etapa haya producido algo utilizable.

Acepta comodines (`*`, `?`): el patron tiene que resolver al menos un archivo.
Un `.json` que parsea pero esta vacio (`{}` / `[]`) cuenta como vacio: es
exactamente lo que deja un agente que no hizo nada.

Solo stdlib, Python 3.8+. No modifica nada.

Uso:
  python check_stage_result.py --esperado <ruta|patron> [<ruta|patron> ...]
                               [--etapa NOMBRE]
  python check_stage_result.py --self-test

Salida: una linea por artefacto y un resumen. Exit 1 si alguno falla.
"""

import argparse
import glob
import json
import sys
from pathlib import Path

OK, FALTA, VACIO, ILEGIBLE = "OK", "FALTA", "VACIO", "ILEGIBLE"


def revisar_archivo(path):
    """(estado, detalle) de UN archivo concreto."""
    p = Path(path)
    if not p.exists():
        return FALTA, "no existe"
    if p.is_dir():
        return ILEGIBLE, "es un directorio"
    try:
        datos = p.read_bytes()
    except OSError as e:
        return ILEGIBLE, str(e)
    if not datos.strip():
        return VACIO, "0 bytes utiles"
    if p.suffix == ".json":
        try:
            doc = json.loads(datos.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as e:
            return ILEGIBLE, "JSON invalido: %s" % e
        if doc in ({}, [], "", None):
            return VACIO, "parsea pero no tiene contenido"
    return OK, "%d bytes" % len(datos)


def revisar(patron):
    """(estado, detalle, ruta_mostrada) de una ruta o patron con comodines."""
    if any(c in patron for c in "*?["):
        encontrados = sorted(glob.glob(patron))
        if not encontrados:
            return FALTA, "ningun archivo coincide con el patron", patron
        peor = (OK, "", patron)
        for ruta in encontrados:
            estado, detalle = revisar_archivo(ruta)
            if estado != OK:
                return estado, detalle, ruta
        return OK, "%d archivo(s)" % len(encontrados), patron
    estado, detalle = revisar_archivo(patron)
    return estado, detalle, patron


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--esperado", nargs="+", default=None, metavar="RUTA",
                    help="artefactos que la etapa tenia que dejar (acepta comodines)")
    ap.add_argument("--etapa", default=None, help="nombre de la etapa, solo para el mensaje")
    ap.add_argument("--self-test", action="store_true",
                    help="corre el self-test sobre fixtures embebidas y sale")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.esperado:
        ap.error("falta --esperado (o --self-test)")

    fallas = []
    for patron in args.esperado:
        estado, detalle, mostrado = revisar(patron)
        print("  %-9s %s (%s)" % (estado, mostrado, detalle))
        if estado != OK:
            fallas.append((mostrado, estado, detalle))

    etiqueta = "la etapa %s" % args.etapa if args.etapa else "la etapa"
    if not fallas:
        print("%s dejo los %d artefacto(s) esperados." % (etiqueta.capitalize(), len(args.esperado)))
        return 0
    print("")
    print("%s NO cerro: %d de %d artefacto(s) con problema." % (
        etiqueta.capitalize(), len(fallas), len(args.esperado)))
    for mostrado, estado, detalle in fallas:
        print("  - %s: %s (%s)" % (mostrado, estado, detalle))
    print("")
    print("No sigas con la etapa siguiente. Relanza el subagente que la produce; si")
    print("vuelve a fallar, deteni e informa al usuario con estas rutas.")
    return 1


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

    tmp = Path(tempfile.mkdtemp(prefix="check-stage-"))
    try:
        (tmp / "bien.json").write_text('{"version": 1}', encoding="utf-8")
        (tmp / "bien.md").write_text("# algo\n", encoding="utf-8")
        (tmp / "vacio.json").write_text("{}", encoding="utf-8")
        (tmp / "blanco.md").write_text("   \n\n", encoding="utf-8")
        (tmp / "roto.json").write_text("{no es json", encoding="utf-8")
        (tmp / "sub").mkdir()
        (tmp / "sub" / "a.json").write_text('{"a": 1}', encoding="utf-8")
        (tmp / "sub" / "b.json").write_text('{"b": 2}', encoding="utf-8")

        def estado(nombre):
            return revisar(str(tmp / nombre))[0]

        check("json con contenido", estado("bien.json"), OK)
        check("markdown con contenido", estado("bien.md"), OK)
        check("json que parsea pero esta vacio", estado("vacio.json"), VACIO)
        check("markdown solo con espacios", estado("blanco.md"), VACIO)
        check("json invalido", estado("roto.json"), ILEGIBLE)
        check("archivo que no existe", estado("no-esta.json"), FALTA)
        check("directorio pasado como artefacto", estado("sub"), ILEGIBLE)
        check("patron que resuelve", revisar(str(tmp / "sub" / "*.json"))[0], OK)
        check("patron que no resuelve", revisar(str(tmp / "sub" / "*.md"))[0], FALTA)

        # un patron con un archivo malo entre varios buenos tiene que fallar
        (tmp / "sub" / "c.json").write_text("{}", encoding="utf-8")
        check("patron con un archivo vacio adentro", revisar(str(tmp / "sub" / "*.json"))[0], VACIO)

        check("exit 0 cuando esta todo", main(["--esperado", str(tmp / "bien.json")]), 0)
        check("exit 1 cuando falta algo",
              main(["--esperado", str(tmp / "bien.json"), str(tmp / "no-esta.json")]), 1)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
