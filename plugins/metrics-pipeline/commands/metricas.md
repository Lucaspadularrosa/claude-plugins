---
description: "Cosecha las metricas de proceso de la suite sobre este proyecto (script, cero tokens) y opcionalmente las analiza para saber que mejorar de los pipelines."
argument-hint: "[opcional: ruta al proyecto] [solo-datos] [export [ruta.jsonl]]"
---

Metricas de la suite para: `$ARGUMENTS`

Segui la skill `metrics-pipeline` con esos argumentos (`solo-datos` = sin analista;
`export` = ademas apendear al JSONL central). Esta corrida solo lee `.dev/` y
escribe en `.dev/metrics/`.
