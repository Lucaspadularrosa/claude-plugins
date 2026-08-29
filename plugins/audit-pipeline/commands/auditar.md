---
description: Audita el codebase en tres dimensiones, bugs, seguridad (defensiva) y mejoras, con verificacion adversarial de cada hallazgo antes de reportarlo.
argument-hint: "[opcional: bugs | seguridad | mejoras | una ruta; por defecto, todo]"
---

Audita esta aplicacion: `$ARGUMENTS`

Segui la skill `audit-pipeline`:

1. Determina el alcance (dimensiones y/o rutas) desde mis argumentos; sin argumentos,
   las tres dimensiones sobre todo el repo. Usa el contexto que enumera la skill
   (linea de base, stack-profile, base de seguridad, `deferred_to_audit` del gate,
   señales del recovery), si existe.
2. Lanza los auditores de las dimensiones elegidas EN PARALELO: `bug-hunter`,
   `security-auditor`, `improvement-scout`. Solo lectura: nada se modifica.
3. Consolida con `dedupe_findings.py` (duplicados entre dimensiones, grupos por
   archivo) y verifica: lo mecanico con `verify_mechanical.py`, lo demas con un
   `finding-verifier` por grupo (opus si tiene algun high, sonnet si no). En la duda,
   se descarta. Los low quedan sin verificar. Si hay mas de ~10 grupos, mostrame el
   conteo y confirmo el alcance antes de gastar.
4. Genera `.dev/audit/audit-report.{json,md}` con `render_audit_report.py` (no lo
   redactes vos): confirmados con severidad ajustada, los que necesitan mi respuesta
   y los descartados con su razon.
5. Mostrame el resumen ejecutivo (lo mas grave primero) y ofreceme convertir los
   confirmados que elija en trabajo trazable: genera `.dev/audit/cr-input-{run}.md`
   con esos hallazgos completos y sugerime `/requerimientos:cambio` con esa ruta (y
   de ahi /replanificar + /construir), o encararlos directo.
