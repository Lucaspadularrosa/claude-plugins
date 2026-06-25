---
description: Audita el codebase en tres dimensiones, bugs, seguridad (defensiva) y mejoras, con verificacion adversarial de cada hallazgo antes de reportarlo.
argument-hint: "[opcional: bugs | seguridad | mejoras | una ruta; por defecto, todo]"
---

Audita esta aplicacion: `$ARGUMENTS`

Segui la skill `audit-pipeline`:

1. Determina el alcance (dimensiones y/o rutas) desde mis argumentos; sin argumentos,
   las tres dimensiones sobre todo el repo. Usa como contexto la linea de base
   (`.dev/requirements/`), el stack-profile y las señales del recovery si existen.
2. Lanza los auditores de las dimensiones elegidas EN PARALELO: `bug-hunter`,
   `security-auditor`, `improvement-scout`. Solo lectura: nada se modifica.
3. Verificacion adversarial: por cada hallazgo high/medium, lanza un
   `finding-verifier` que intente refutarlo leyendo el codigo real. En la duda, se
   descarta. Los low quedan como no verificados.
4. Consolida `.dev/audit/audit-report.{json,md}`: confirmados (con severidad ajustada
   y evidencia), los que necesitan mi respuesta, y los descartados con su razon.
5. Mostrame el resumen ejecutivo (lo mas grave primero) y ofreceme convertir los
   confirmados que elija en trabajo trazable via `/requerimientos:cambio` (y de ahi
   /replanificar + /construir), o encararlos directo.
