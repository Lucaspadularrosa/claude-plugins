#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook SubagentStop: verifica que un subagente de la suite devolvio su sobre.

Los 31 agentes prometen cerrar con el mismo puntero — `status`, `artifact_paths`,
`summary` y `blocking_items` si los hay — pero eso era convencion de prompt: ningun
script lo miraba. Un subagente que termina sin reporte (429, corte, o un Task cuyo
ultimo mensaje es el resultado de una herramienta en vez de texto) se ve igual que
uno que cerro bien, y el orquestador sigue con las manos vacias.

`SubagentStop` no puede bloquear (el subagente ya termino) pero si escribir un
`systemMessage` que el orquestador ve en el transcript. Eso alcanza: convierte un
silencio en un aviso.

Actua **solo** sobre los agentes de esta suite, por prefijo de plugin: este hook
viaja instalado a nivel usuario y no tiene por que opinar sobre los subagentes de
ningun otro trabajo.

Solo stdlib, Python 3.8+. No modifica nada. Siempre exit 0: un hook que rompe la
sesion por un aviso es peor que el problema que reporta.
"""

import json
import sys

# Plugins de la suite. `validate.py` verifica que esta lista coincida con los
# nombres del marketplace: si se agrega un plugin y no entra aca, sus agentes
# dejan de verificarse en silencio.
PLUGINS = (
    "audit-pipeline",
    "build-pipeline",
    "manual-usuario",
    "metrics-pipeline",
    "planning-pipeline",
    "recovery-pipeline",
    "requerimientos",
)

# `blocking_items` es opcional por contrato ("si los hay"): no se exige.
CLAVES = ("status", "artifact_paths", "summary")


def revisar(payload):
    """`systemMessage` si el sobre falta o esta incompleto; None si esta bien."""
    agente = str(payload.get("agent_type") or "")
    if not any(agente.startswith(p + ":") for p in PLUGINS):
        return None  # no es de la suite: no opinamos

    mensaje = payload.get("last_assistant_message")
    if not isinstance(mensaje, str) or not mensaje.strip():
        return ("El subagente `%s` termino sin devolver texto. Su ultimo mensaje fue una "
                "llamada a herramienta o no hubo mensaje: el sobre de retorno se perdio. "
                "Verifica en disco si dejo su artefacto (`suite-stage-check --esperado ...`) "
                "antes de seguir; si no lo dejo, relanzalo." % agente)

    faltan = [c for c in CLAVES if c not in mensaje]
    if faltan:
        return ("El subagente `%s` cerro sin el sobre completo: falta %s. El contrato es "
                "`status`, `artifact_paths`, `summary` (y `blocking_items` si los hay). "
                "Confirma en disco que el artefacto existe antes de darlo por bueno."
                % (agente, ", ".join("`%s`" % c for c in faltan)))
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # sin payload utilizable no hay nada que decir
    if not isinstance(payload, dict):
        return 0

    aviso = revisar(payload)
    if aviso:
        json.dump({"systemMessage": aviso}, sys.stdout, ensure_ascii=False)
    return 0


def self_test():
    casos = [
        ("agente ajeno se ignora",
         {"agent_type": "Explore", "last_assistant_message": "nada"}, False),
        ("agente de la suite con sobre completo",
         {"agent_type": "audit-pipeline:bug-hunter",
          "last_assistant_message": "status: ok\nartifact_paths: a.json\nsummary: 3 bugs"}, False),
        ("agente de la suite sin texto",
         {"agent_type": "planning-pipeline:task-patch", "last_assistant_message": ""}, True),
        ("agente de la suite sin last_assistant_message",
         {"agent_type": "recovery-pipeline:gap-analysis"}, True),
        ("agente de la suite con sobre incompleto",
         {"agent_type": "requerimientos:lel-authoring",
          "last_assistant_message": "status: ok, ya esta"}, True),
        ("payload sin agent_type", {"last_assistant_message": "hola"}, False),
    ]
    fallos = 0
    for nombre, payload, espera_aviso in casos:
        got = revisar(payload) is not None
        if got != espera_aviso:
            print("SELF-TEST FALLO (%s): aviso=%s, esperaba %s" % (nombre, got, espera_aviso))
            fallos += 1
        else:
            print("self-test ok (%s)" % nombre)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv[1:] else main())
