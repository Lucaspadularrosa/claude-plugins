---
description: "Cuanto costo y como funciono la suite en este proyecto, cosechado por script sin tokens, y opcionalmente analizado para saber que ajustar de los pipelines."
argument-hint: "[opcional: ruta al proyecto] [solo-datos] [export [ruta.jsonl]]"
---

Metricas de la suite para: `$ARGUMENTS`

Segui la skill `metrics-pipeline` con esos argumentos (`solo-datos` = sin analista;
`export` = ademas apendear al JSONL central). Esta corrida solo lee `.dev/` y
escribe en `.dev/metrics/`.
