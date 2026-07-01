---
name: build-pipeline
description: Ejecuta el plan de construccion generado por planning-pipeline, en cualquier lenguaje o framework. Construye una feature en su rama (con aprobacion del plan de implementacion) o un lote completo en paralelo con un subagente por feature en worktrees (autonomo). Verifica cada tarea contra sus criterios de aceptacion y mantiene progress.json al dia. Usar cuando el usuario quiere construir, implementar o desarrollar features planificadas en .dev/features/.
---

# Pipeline de Build (ejecucion del plan, agnostico de stack)

Esta skill ejecuta el plan que produjo `planning-pipeline`: toma los briefs de
`.dev/features/`, implementa cada feature en su propia rama verificando los criterios
de aceptacion, y construye lotes completos en paralelo. No tiene conocimiento
hardcodeado de ningun lenguaje o framework: todo lo especifico del proyecto sale del
**perfil de stack** que se descubre por evidencia del propio repo.

Vos, el agente principal, sos el orquestador: delegas en los subagentes con la
herramienta Task, manejas git (ramas, worktrees, PRs) y mantenes `progress.json`.

## Precondicion

Antes de empezar, verifica que existan:
- `.dev/features/*.md` (los briefs) y `.dev/plan/execution-plan.json` (los lotes).
- `.dev/plan/progress.json` (estado del build; si falta, inicializalo con todo
  `pending` a partir del plan).

Si falta el plan, indicale al usuario que primero corra `/planificar`
(`planning-pipeline`).

## Subagentes (en `agents/` del plugin)

| Subagente | Rol | Cuando |
|---|---|---|
| `stack-profiler` | Descubre el stack y la base de seguridad del proyecto; emite `.dev/build/stack-profile.json` y `.dev/build/security-baseline.json` | Primera vez, o si el perfil quedo stale |
| `feature-implementer` | Construye UNA feature: modo plan (propone) y modo ejecucion (implementa y verifica, con el piso de seguridad OWASP por construccion) | Por cada feature |
| `build-reviewer` | Revisa el diff contra el brief (cobertura, scope, correctitud, convenciones) y emite veredicto en `.dev/build/reviews/{slug}.json` | Antes de cada PR |
| `security-gate` | Revisa el diff contra la base de seguridad (piso OWASP) y corre el audit de dependencias; emite veredicto en `.dev/build/security/{slug}.json` | Antes de cada PR, junto con el review |

## Convenciones compartidas

- **Perfil de stack y base de seguridad**: si `.dev/build/stack-profile.json` o
  `.dev/build/security-baseline.json` no existen, o el `technical_design_version_ref`
  del perfil no coincide con la version actual del diseno, invoca `stack-profiler` antes
  que nada (emite ambos en una pasada). Si el perfil tiene `open_questions` (no hay
  comando de test, no se sabe la rama de integracion), resolvelas con el usuario antes
  de construir: sin verificacion no hay build. Si la base de seguridad quedo con huecos
  (ej.: sin comando de audit de dependencias), no bloquea el build, pero avisale al
  usuario: el `security-gate` lo va a reportar.
- **Compuerta de lote**: una feature solo puede construirse si su lote esta
  desbloqueado: todos los lotes de su `unlocks_after` tienen sus features `done` en
  `progress.json`, y la ronda de contratos esta mergeada. Si no, explicale al usuario
  que falta y no arranques.
- **Semantica de `progress.json`**: `in_progress` desde que la feature arranca (anota
  la rama); `done` significa **mergeado a la rama de integracion**, no "PR abierto".
  Las tareas se marcan `done` a medida que el implementador las termina. Si el PR no
  se mergea en la sesion, la feature queda `in_progress` con el PR anotado en
  `notes`; al verificar lotes, ofrece chequear si los PRs pendientes ya se mergearon
  (`gh pr view`) y actualizar.
- **Ramas**: `feature/{slug}`, desde la rama de integracion del perfil. Un PR por
  feature, con `gh` si esta disponible (si no, deja la rama lista y las instrucciones).
  El cuerpo del PR cita la feature (`FG-xx`), las tareas (`T-xxx`) y el resultado del
  review.
- Si un subagente falla o reporta bloqueo, no improvises: mostra el bloqueo al usuario
  con el contexto del brief.

---

## Modo FEATURE (`/construir <feature>`)

Construye una feature, con aprobacion del plan de implementacion antes de codear.

1. Resolve la feature contra `.dev/features/` (acepta slug o nombre; si hay
   ambiguedad, lista y pregunta). Verifica la compuerta de lote y que la feature no
   este ya `done` o `in_progress` (si esta `in_progress`, pregunta si retomar).
2. Asegura el perfil de stack (ver convenciones).
3. Invoca `feature-implementer` en **modo plan**. Mostrale al usuario el plan de
   implementacion (enfoque por tarea, archivos, verificacion) y **espera su
   aprobacion**. Si pide cambios, ajusta el plan y volve a mostrarlo. No toques codigo
   sin el OK.
4. Aprobado: crea la rama `feature/{slug}`, marca la feature `in_progress` en
   `progress.json` (con la rama), e invoca `feature-implementer` en **modo ejecucion**
   con el plan aprobado. A medida que reporta tareas terminadas, marcalas `done` en
   `progress.json`.
5. Invoca `build-reviewer` y `security-gate` (podes lanzarlos en paralelo: ambos son de
   solo lectura y emiten veredictos separados). Si cualquiera reporta hallazgos `high` o
   `medium`, re-invoca `feature-implementer` con los hallazgos de ambos para corregir y
   volve a revisar con los dos, hasta que los dos pasen. Los `deferred_to_audit` del
   gate no bloquean el PR: se anotan para sugerir `/auditar` despues.
6. Crea el PR contra la rama de integracion y mostrale al usuario el resumen: tareas
   construidas, criterios verificados, veredicto del review, **veredicto de seguridad**
   (piso OWASP: passed, hallazgos, resultado del audit de dependencias) y link del PR. La
   feature queda `in_progress` hasta que el PR mergee (anota el PR en `notes`); si el
   usuario lo mergea en la sesion, marcala `done`.

## Modo LOTE (`/construir-lote [BATCH-n]`)

Construye un lote completo en paralelo, **sin pausas de aprobacion** (el control queda
en los PRs). Pensado para una sesion que ejecuta el plan de corrido.

1. Determina el lote: el indicado, o el primer lote con features `pending` cuyo
   `unlocks_after` este completo. Si la **ronda de contratos** (`contract_round`) esta
   pendiente, ejecutala primero: un solo `feature-implementer` con esas tareas en una
   rama `contracts/{ronda}`, review, y merge a la rama de integracion (los contratos
   ya fueron auditados por plan-inspection y bloquean todo lo demas). Si el repo exige
   PR para mergear, abri el PR, avisale al usuario que es bloqueante y espera el merge
   antes de seguir.
2. Asegura el perfil de stack. Marca las features del lote `in_progress`.
3. Prepara un **worktree por feature**:
   `git worktree add ../{repo}-wt-{slug} -b feature/{slug} {rama_integracion}`.
4. Lanza los `feature-implementer` en **modo ejecucion** (sin modo plan) de TODAS las
   features del lote **en paralelo** (una sola tanda de llamadas Task), cada uno con
   su worktree como ruta de trabajo. Cada agente trabaja solo dentro de su feature:
   los briefs garantizan que no se pisan.
5. A medida que cada implementador termina, lanza su `build-reviewer` y su
   `security-gate` (tambien en paralelo entre features). Hallazgos `high`/`medium` de
   cualquiera de los dos: re-invoca al implementador de esa feature para corregir y
   re-revisa con ambos, hasta que pasen. Un bloqueo en una feature no frena a las demas:
   registralo y segui.
6. Por cada feature que paso (review y gate en verde): push de la rama, PR contra la
   rama de integracion, y limpieza del worktree (`git worktree remove`). Actualiza
   `progress.json` (tareas `done`; features `in_progress` con su PR en `notes`).
7. Resumen final: por feature, tareas construidas, veredicto del review, veredicto de
   seguridad (piso OWASP + audit de dependencias) y PR; bloqueos y `deferred_to_audit`
   si los hubo; y el proximo paso (mergear los PRs y, cuando esten `done`, el siguiente
   lote — o `/replanificar` si llegaron cambios de requisitos, o `/auditar` si el gate
   dejo cosas para auditoria profunda).

---

## Reglas de orquestacion

- Una feature por agente, un agente por feature: el paralelismo del plan se respeta,
  no se inventa (no lances features de lotes bloqueados).
- Nada se construye sin verificacion: criterios Gherkin demostrados con los comandos
  del perfil. Si el perfil no tiene comando de test, eso se resuelve con el usuario
  antes, no se saltea.
- Nada se mergea sin el piso de seguridad: el `security-gate` es compuerta del PR igual
  que el `build-reviewer`. Ambos deben pasar (sin `high`/`medium`) antes de abrir/mergear.
  El piso es prevencion; la auditoria profunda sigue siendo `/auditar` (audit-pipeline),
  al que el gate deriva lo que lo excede.
- `progress.json` es sagrado: es lo que `/replanificar` usa para no pisar trabajo.
  Actualizalo en cada transicion, no al final.
- Trazabilidad: commits con `[T-xxx]`, PRs citando `FG-xx` y tareas; el review queda
  en `.dev/build/reviews/` y el veredicto de seguridad en `.dev/build/security/`.
- Si durante el build llegan cambios de requisitos (el usuario lo menciona o
  `plan-inspection` marco staleness), no improvises sobre el plan viejo: sugerile
  correr `/replanificar` y retoma despues.

## Estructura resultante

```
.dev/build/
  stack-profile.json          perfil de stack del proyecto (por evidencia)
  security-baseline.json      base de seguridad del stack (superficie, OWASP, tooling)
  reviews/{slug}.json         veredicto de review por feature
  security/{slug}.json        veredicto de seguridad (piso OWASP) por feature
.dev/plan/progress.json       actualizado en cada transicion
ramas feature/{slug}          una por feature, PR contra la rama de integracion
```
