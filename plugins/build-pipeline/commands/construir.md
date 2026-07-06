---
description: Construye una feature planificada (.dev/features/) en su propia rama, con aprobacion del plan de implementacion antes de codear. Agnostico de stack.
argument-hint: <slug o nombre de la feature>
---

Construi la feature: `$ARGUMENTS`

Segui el modo FEATURE de la skill `build-pipeline`:

1. Resolve la feature contra `.dev/features/` y verifica que su lote este
   desbloqueado (lotes anteriores `done`, contratos mergeados). Si no, decime que
   falta.
2. Asegura el perfil de stack y la base de seguridad (`.dev/build/stack-profile.json` y
   `.dev/build/security-baseline.json`); si es la primera vez o quedaron stale, corre
   `stack-profiler` (emite ambos). Si el perfil tiene preguntas abiertas (comando de
   test, rama de integracion), resolvelas conmigo antes de seguir. Si el proyecto no
   tiene CI que corra test y lint, bootstrapealo en la primera rama que construyas:
   los checks del PR verifican independiente del reporte del agente.
3. Corre `feature-implementer` en modo plan y mostrame el plan de implementacion
   (enfoque por tarea, archivos, como se verifica cada criterio). **Espera mi
   aprobacion**; si pido cambios, ajustalo.
4. Aprobado: crea la rama `feature/{slug}`, marca `in_progress` en `progress.json` y
   corre `feature-implementer` en modo ejecucion. Tarea terminada y verificada =
   tarea `done` en progress. Al final del implementador viene el cierre de feature:
   cada criterio de los REQUISITOS del brief demostrado (no solo los de las tareas).
5. Corre `build-reviewer` y `security-gate` (piso OWASP + audit de dependencias);
   hallazgos high/medium de cualquiera rebotan al implementador en modo correccion,
   con tope de 3 rondas: si no pasa, o algo es no corregible (p. ej. vulnerabilidad
   de dependencia sin fix), bloquea y mostrame el caso.
6. Crea el PR contra la rama de integracion y mostrame el resumen (tareas, criterios
   verificados, cierre por requisito, veredicto del review, veredicto de seguridad,
   PR). La feature queda `done` recien cuando el PR mergea.
