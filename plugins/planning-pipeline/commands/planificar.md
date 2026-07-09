---
description: Convierte la linea de base de requisitos en un plan de ejecucion para agentes IA (tareas, lotes paralelos y briefs de feature).
---

Genera el plan de ejecucion a partir de la linea de base de requisitos del proyecto.

Segui la skill `planning-pipeline` de punta a punta:

1. Verifica que existan `.dev/requirements/requirements.json`, `technical-design.json` y
   `data-model.json`. Si falta alguno, deteni y pedime correr antes el pipeline de
   requisitos. Si ya existe un plan en `.dev/plan/`, frena: con build arrancado (algo
   fuera de `pending` en `progress.json`) lo correcto es `/replanificar`; regenera
   todo solo si te lo confirmo explicitamente (y ahi re-inicializa `progress.json`).
2. Encadena los subagentes: `task-derivation` -> `execution-planning`.
3. Corre `plan-inspection` y su lazo de correccion (tope: 3 pasadas; si no pasa,
   mostrame los defectos remanentes y decido yo). Los rebotes van a `task-derivation`
   o `execution-planning` segun el defecto; el de desactualizacion (PLAN-CHECK-007)
   no se corrige en el lazo: me indicas correr `/replanificar`.
4. Corre `feature-brief` para emitir un documento por feature en `.dev/features/`.
5. Al final, lista los archivos generados en `.dev/plan/` (incluyendo
   `execution-plan.{json,md}`) y `.dev/features/` con un resumen de features, tareas,
   contratos, maximo paralelismo (agentes simultaneos) y critical path en turnos.

$ARGUMENTS
