---
description: Construye una feature planificada (.dev/features/) en su propia rama, con aprobacion del plan de implementacion antes de codear. Agnostico de stack.
argument-hint: <slug o nombre de la feature>
---

Construi la feature: `$ARGUMENTS`

Segui el modo FEATURE de la skill `build-pipeline`:

1. Resolve la feature contra `.dev/features/` y verifica que su lote este
   desbloqueado (lotes anteriores `done`, contratos mergeados). Si no, decime que
   falta.
2. Asegura el perfil de stack (`.dev/build/stack-profile.json`); si es la primera vez
   o quedo stale, corre `stack-profiler`. Si el perfil tiene preguntas abiertas
   (comando de test, rama de integracion), resolvelas conmigo antes de seguir.
3. Corre `feature-implementer` en modo plan y mostrame el plan de implementacion
   (enfoque por tarea, archivos, como se verifica cada criterio). **Espera mi
   aprobacion**; si pido cambios, ajustalo.
4. Aprobado: crea la rama `feature/{slug}`, marca `in_progress` en `progress.json` y
   corre `feature-implementer` en modo ejecucion. Tarea terminada y verificada =
   tarea `done` en progress.
5. Corre `build-reviewer`; hallazgos high/medium rebotan al implementador hasta que
   pase.
6. Crea el PR contra la rama de integracion y mostrame el resumen (tareas, criterios
   verificados, veredicto, PR). La feature queda `done` recien cuando el PR mergea.
