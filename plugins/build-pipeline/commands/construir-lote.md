---
description: Construye un lote completo del plan en paralelo, un subagente por feature en su propio git worktree, sin pausas de aprobacion. El control queda en los PRs.
argument-hint: "[opcional: BATCH-n; por defecto, el proximo lote desbloqueado]"
---

Construi el lote en paralelo: `$ARGUMENTS`

Segui el modo LOTE de la skill `build-pipeline`:

1. Determina el lote (el indicado, o el primero con features pendientes o retomables
   — `in_progress` sin PR, de una corrida cortada — y `unlocks_after` completo). Si
   la ronda de contratos esta pendiente, ejecutala y mergeala primero, con review y
   security-gate: bloquea todo lo demas.
2. Asegura el perfil de stack y la base de seguridad (los emite `stack-profiler`);
   resolve conmigo sus preguntas abiertas si las hay. En greenfield sin esqueleto,
   construi una primera feature en secuencia antes de paralelizar.
3. Prepara un git worktree por feature (limpiando restos de corridas anteriores y
   corriendo el install del perfil en cada uno) y lanza los `feature-implementer`
   **en paralelo**, cada uno en su worktree, en modo ejecucion (sin aprobacion de
   plan: el brief auditado es el contrato).
4. A medida que cada una termina, corre su `build-reviewer` y su `security-gate`;
   hallazgos high/medium de cualquiera rebotan al implementador de esa feature en
   modo correccion (tope: 3 rondas; si no pasa, queda bloqueada con su motivo en
   `progress.json`). Un bloqueo en una feature no frena a las demas.
5. Por cada feature que paso (review y gate en verde): push, PR contra la rama de
   integracion, limpieza del worktree y actualizacion de `progress.json`.
6. Al final, resumen por feature (tareas, veredicto del review, veredicto de seguridad,
   PR), bloqueos y lo que el gate haya derivado a `/auditar`, y el proximo paso (mergear
   PRs; cuando esten `done`, el siguiente lote).
