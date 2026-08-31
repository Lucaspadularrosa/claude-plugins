---
description: Construye una feature planificada (.dev/features/) en su propia rama, con aprobacion del plan de implementacion antes de codear. Agnostico de stack.
argument-hint: <slug o nombre de la feature>
---

Construi la feature: `$ARGUMENTS`

Segui el modo FEATURE de la skill `build-pipeline` (lee
`${CLAUDE_PLUGIN_ROOT}/skills/build-pipeline/modes/feature.md`). Resumen del
contrato: plan de implementacion con mi aprobacion antes de tocar codigo; ejecucion
tarea por tarea con commits `[T-xxx]`; verificacion por script (`verify.py`);
`build-reviewer`, `security-gate` y `user-docs-writer` **siempre en una sola tanda
paralela**; lazo de correccion con tope de 3 rondas por delta del fix; compuerta dura
por script antes del PR; resumen final con `render_batch_summary.py`. `progress.json`
solo via `progress_update.py`.
