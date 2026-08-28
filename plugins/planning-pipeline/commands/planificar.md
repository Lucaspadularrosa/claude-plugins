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
2. Corre `task-derivation` y despues el script `compute_execution_plan.py` (el
   armado de lotes es determinista: no gasta subagente).
3. Corre la validacion mecanica por script (`validate_plan.py`) hasta verde (los
   rebotes van a `task-derivation` en modo correccion con Edit) y despues
   `plan-inspection` en modo juicio (tope: 3 pasadas; si no pasa, mostrame los
   defectos remanentes y decido yo). El de desactualizacion (PLAN-CHECK-007) no se
   corrige en el lazo: me indicas correr `/replanificar`.
4. Pre-corta el contexto (`slice_brief_context.py`) y lanza los `feature-brief` en
   paralelo, uno por feature, para emitir los documentos en `.dev/features/`; cierra
   la etapa con el linter (`validate_plan.py --briefs`).
5. Al final, lista los archivos generados en `.dev/plan/` (incluyendo
   `execution-plan.{json,md}`) y `.dev/features/` con un resumen de features, tareas,
   contratos, maximo paralelismo (agentes simultaneos) y critical path en turnos.

$ARGUMENTS
