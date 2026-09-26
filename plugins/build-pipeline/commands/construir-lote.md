---
description: "Construye en paralelo todas las features que no dependen entre si, un agente por feature en su propio worktree, sin pausas. El control queda en los PRs. Para cuando queres avanzar rapido con varias features a la vez."
argument-hint: "[opcional: BATCH-n; por defecto, el proximo lote desbloqueado]"
---

Construi el lote en paralelo: `$ARGUMENTS`

Segui el modo LOTE de la skill `build-pipeline` (lee
`${CLAUDE_PLUGIN_ROOT}/skills/build-pipeline/modes/lote.md`). Resumen del contrato:
ronda de contratos primero si esta pendiente; un worktree por feature;
implementadores en paralelo por tandas de `max_parallel_degree`; cada feature entra a
su tanda de review (reviewer + gate + docs, en paralelo) apenas termina su
implementador, sin esperar a las demas; correccion por delta con tope de 3 rondas; un
bloqueo no frena al resto; compuerta dura por script antes de cada PR; narracion
dosificada durante el lote y resumen final con `render_batch_summary.py`.
