---
description: Actualiza el plan de ejecucion cuando los requisitos cambiaron (incrementos o CRs nuevos en el changelog), re-derivando solo las features afectadas y sin tocar lo ya construido.
argument-hint: "[opcional: ids de changelog a aplicar, ej. INC-002 CR-001]"
---

Replanifica el plan de ejecucion segun los cambios de requisitos: `$ARGUMENTS`

Segui el modo REPLANIFICACION de la skill `planning-pipeline`: delta contra
`applied_changelog_ids`/`deferred_changelog_ids` (si pase ids, limita el delta a esos
y posterga el resto avisandome), estado del build desde `progress.json` (si no existe,
preguntame; no asumas), resumen previo, derivacion acotada a las features afectadas
(un subagente por feature, merge por script), PAUSA por cada conflicto, lotes por
script (`--replan`; solo con CONFLICTOs interviene `execution-planning` con mis
decisiones), inspeccion con el invariante PLAN-CHECK-013, briefs solo de las
afectadas y cierre con `progress.json` sincronizado y sin archivos temporales.

Si no hay plan, esto es un `/planificar` normal. Al final: que se agrego/modifico/
cancelo, los lotes del trabajo restante, el paralelismo y los `applied_changelog_ids`.
