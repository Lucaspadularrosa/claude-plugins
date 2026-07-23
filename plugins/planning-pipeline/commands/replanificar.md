---
description: Actualiza el plan de ejecucion cuando los requisitos cambiaron (incrementos o CRs nuevos en el changelog), re-derivando solo las features afectadas y sin tocar lo ya construido.
argument-hint: "[opcional: ids de changelog a aplicar, ej. INC-002 CR-001]"
---

Replanifica el plan de ejecucion segun los cambios de requisitos: `$ARGUMENTS`

Segui el modo REPLANIFICACION de la skill `planning-pipeline`:

1. Verifica que exista el plan (`.dev/plan/tasks.json`, `execution-plan.json`) y la
   linea de base de requisitos. Si no hay plan, esto es un `/planificar` normal.
2. Calcula el delta: entradas `INC-xxx` / `CR-xxx` / `REC-xxx` con `status: applied`
   en `.dev/requirements/changelog.json` que NO esten en
   `metadata.applied_changelog_ids` ni en `metadata.deferred_changelog_ids` de
   `tasks.json`. Si pase ids como argumento, limita el delta a esos y registra el
   resto como postergado (`deferred_changelog_ids`), avisandome que quedo pendiente.
   Si no hay delta y las versiones coinciden, informa que el plan esta al dia y
   termina.
3. Lee `.dev/plan/progress.json` (estado del build). Si no existe, preguntame que
   features/tareas estan hechas o en curso antes de seguir; no asumas que nada se
   construyo sin confirmarmelo.
4. Mostrame el resumen del delta (features afectadas, veredictos) y corre
   `task-derivation` en modo replanificacion: re-deriva solo las features afectadas.
5. Si reporta conflictos (requisito deprecado con tarea ya construida, requisito
   modificado con tarea en curso), hace la PAUSA: mostramelos y espera mi decision
   uno por uno. Aplicalas re-invocando al agente.
6. Corre `execution-planning` en modo replanificacion: recalcula los lotes solo del
   trabajo restante (lo `done` queda fuera del grafo, lo `in_progress` conserva su
   lote).
7. Corre `plan-inspection` y su lazo de correccion (tope: 3 pasadas; si no pasa,
   mostrame los defectos remanentes y decido yo). Indicale que es replanificacion y
   pasale la version previa de `tasks.json` (referencia git o ruta) para el
   invariante de replanificacion (PLAN-CHECK-013).
8. Corre `feature-brief` solo para las features afectadas, marcando que cambio.
9. Al final: si algun agente reporto un delta (`*.delta.json`), mergealo al canonico,
   verifica el resultado y borralo antes de cerrar — no pueden quedar archivos
   `*delta*`, `*patch*` ni `_*` en `.dev/plan/` ni `.dev/requirements/`; el layout es
   cerrado. Sincroniza `progress.json.plan_ref` (tasks_version y
   applied_changelog_ids) con el `tasks.json` recien emitido. Despues el resumen de
   que se agrego/modifico/cancelo, los nuevos lotes
   del trabajo restante, el paralelismo resultante y los `applied_changelog_ids`
   actualizados.
