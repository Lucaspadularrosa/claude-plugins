---
description: "Cosecha las metricas de proceso de la suite sobre este proyecto (script determinista, cero tokens) y opcionalmente las analiza con un agente dedicado para saber que mejorar de los pipelines."
argument-hint: "[opcional: ruta al proyecto] [solo-datos] [export [ruta.jsonl]]"
---

Metricas de la suite para: `$ARGUMENTS`

Segui la skill `metrics-pipeline`:

1. Corre el cosechador (`metrics_harvest.py`) sobre el proyecto: genera
   `.dev/metrics/metrics.json` y `.html` desde los artefactos que los pipelines ya
   dejaron. Cero tokens de modelo en este paso.
2. Si pedi `solo-datos`: mostrame las rutas y los numeros clave, y termina ahi.
3. Si no: invoca `metrics-analyst` (lee solo el metrics.json) y mostrame el
   diagnostico de `analysis.md` — que esta funcionando, que no, y que tocar en la
   suite, priorizado y con honestidad sobre el tamaño de la muestra.
4. Si pedi `export`: apendea el registro compacto al JSONL central para comparar
   versiones del plugin entre proyectos.

No toques los otros pipelines ni sus artefactos: esta corrida solo lee `.dev/` y
escribe en `.dev/metrics/`.
