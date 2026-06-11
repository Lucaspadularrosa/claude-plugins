# Build Pipeline — Plugin de Claude Code

Plugin que **ejecuta el plan**: toma los briefs que genera `planning-pipeline` en
`.dev/features/`, implementa cada feature en su propia rama verificando los criterios
de aceptacion, y construye lotes completos **en paralelo** (un subagente por feature,
cada uno en su git worktree). Cierra el ciclo: requisitos → plan → **build** →
progreso que retroalimenta la replanificacion.

## Agnostico de stack, en serio

El plugin no tiene una linea de Next.js, Laravel, Django ni de ningun framework. Lo
que un build necesita saber del proyecto se **descubre por evidencia** la primera vez
(`stack-profiler`): manifiestos (`package.json`, `composer.json`, `pyproject.toml`,
`go.mod`...), configs de test y lint, pipelines de CI, `CLAUDE.md` y el `stack[]` del
diseno tecnico. El resultado es `.dev/build/stack-profile.json`: comandos exactos de
test/lint/build, layout, convenciones y rama de integracion — validados cuando se
puede, marcados como deducidos cuando no.

Para soportar un stack nuevo no se modifica el plugin: se corre en el proyecto. En
proyectos greenfield (sin codigo todavia), el perfil se deriva del diseno tecnico y la
primera feature crea el esqueleto.

## Que necesitas antes

La salida de `planning-pipeline` en el proyecto:
- `.dev/features/*.md` (briefs) y `.dev/plan/execution-plan.json` (lotes).
- `.dev/plan/progress.json` (si falta, se inicializa solo).

`CLAUDE.md` con convenciones del equipo ayuda (el perfil lo respeta como fuente mas
autoritativa), pero no es obligatorio.

## Uso

```
/construir <feature>          una feature, con tu aprobacion del plan de implementacion
/construir-lote [BATCH-n]     un lote completo en paralelo, sin pausas
```

### `/construir <feature>` — control fino

1. Verifica que el lote de la feature este desbloqueado y que el perfil de stack
   exista (lo genera si no).
2. Te muestra el **plan de implementacion** (enfoque por tarea, archivos, como se
   verifica cada criterio) y **espera tu aprobacion**.
3. Implementa tarea por tarea en `feature/{slug}`: cada tarea se verifica contra sus
   criterios Gherkin (tests con el framework del perfil) y se commitea con su
   `[T-xxx]`.
4. `build-reviewer` revisa el diff (cobertura del brief, scope, correctitud, tests
   corridos de verdad); los hallazgos rebotan al implementador hasta pasar.
5. PR contra la rama de integracion, con el resumen y el veredicto.

### `/construir-lote` — el ejecutor del plan

Para correr el plan de corrido: toma el proximo lote desbloqueado, ejecuta y mergea
primero la **ronda de contratos** si esta pendiente, crea un worktree por feature y
lanza todos los implementadores **a la vez**. Sin pausas de aprobacion: el brief ya
fue auditado por `plan-inspection`, y el control humano queda en los PRs (uno por
feature). Un bloqueo en una feature no frena a las demas.

Tambien podes repartir el lote entre **varias instancias de Claude Code** (una por PC
o licencia): cada una corre `/construir <feature>` con una feature distinta del mismo
lote — `progress.json` coordina el estado.

## Estructura del plugin

```
build-pipeline/
  .claude-plugin/
    plugin.json
  agents/
    stack-profiler.md        descubre el stack del proyecto (por evidencia)
    feature-implementer.md   construye una feature (modo plan / modo ejecucion)
    build-reviewer.md        revisa el diff contra el brief antes del PR
  skills/
    build-pipeline/
      SKILL.md               orquestacion de los dos modos
  commands/
    construir.md             /construir <feature>
    construir-lote.md        /construir-lote [BATCH-n]
  PIPELINE.md
  README.md
```

## Garantias

- **Nada sin verificar**: una tarea esta terminada cuando sus criterios Gherkin se
  demostraron con tests verdes. El reviewer corre los tests; no le cree al reporte.
- **Nada fuera del brief**: sin features extra, refactors oportunistas ni dependencias
  que el diseno no pida. Tocar archivos de otra feature del lote es hallazgo `high`
  (rompe el paralelismo).
- **Trazabilidad hasta el codigo**: commits `[T-xxx]` → tarea → requisito → escenario
  → LEL → fuente. Reviews archivados en `.dev/build/reviews/`.
- **`progress.json` siempre al dia**: `done` = mergeado. Es lo que le permite a
  `/replanificar` absorber cambios de requisitos sin pisar lo construido.

## Relacion con `feature-pipeline`

`feature-pipeline` (este mismo marketplace) es un pipeline de build independiente que
lee requerimientos de `/features/` con su propio formato y flujo de aprobacion, pensado
originalmente para Next.js/TypeScript. `build-pipeline` no lo reemplaza: es el ejecutor
nativo del sistema `.dev/` (requirements-pipeline + planning-pipeline), agnostico de
stack. Si tu proyecto no usa esos pipelines, `feature-pipeline` sigue siendo una opcion
valida.

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.
