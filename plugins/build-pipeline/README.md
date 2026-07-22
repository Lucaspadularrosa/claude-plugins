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

## Seguridad por construccion (piso OWASP)

En la misma pasada, `stack-profiler` deriva la **base de seguridad** del stack en
`.dev/build/security-baseline.json`: la superficie de ataque del proyecto (web, API,
CLI, libreria, servicio), las categorias de OWASP Top 10 que aplican, el mecanismo
**nativo** del stack para cada una (el ORM que parametriza, el template que escapa, el
middleware de authz, el hasher de passwords, el gestor de secretos) y el comando de
audit de dependencias.

Con eso, el `feature-implementer` codea con un **piso de seguridad desde el primer
commit** — usando lo que el framework ya da, nunca crypto o escaping artesanal — y el
`security-gate` lo verifica antes del PR: revisa el diff contra las categorias
aplicables y corre el audit de dependencias. Es **prevencion**, no auditoria: el piso
que evita los errores tipicos. La auditoria profunda adversarial sigue siendo
`audit-pipeline` (`/auditar`), al que el gate deriva lo que lo excede.

Como todo en el plugin, es por evidencia y agnostico de stack: no hay un checklist de
seguridad hardcodeado. La referencia de categorias y defensas es
`reference/owasp-baseline.md`.

## Documentacion de usuario final

Cada feature que pasa las compuertas (review + gate) sale ademas con su **guia de
usuario**: `.dev/manual/{slug}.md`, un Markdown escrito por el `user-docs-writer`
(sonnet: redactar no necesita el modelo de las etapas de juicio) para una persona
**no tecnica** — que hace la feature, paso a paso (derivado de los escenarios),
roles, casos especiales. Habla el vocabulario del LEL y documenta el comportamiento
**real construido** (desvios incluidos), no la spec. La guia viaja en el mismo PR de
la feature; el indice del manual (`.dev/manual/README.md`) es un archivo derivado
que regenera el orquestador — por eso los PRs paralelos de un lote nunca se pisan.
Es best-effort: nunca bloquea un PR, y las features sin superficie de usuario
(contratos internos, infraestructura) no generan guia.

El Markdown es la **fuente de verdad** del manual y vive en `.dev/` como todo
artefacto de la suite (renderiza en GitHub y se revisa en el PR). Lo unico de cara
al usuario final es la publicacion: el plugin **`manual-usuario`**
(`/publicar-manual`) lo convierte en un sitio HTML navegable en `docs/manual/`,
fuera de `.dev/` — una publicacion derivada y determinista, separada del build.

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
   corridos de verdad) y `security-gate` revisa el piso de seguridad (OWASP + audit de
   dependencias); los hallazgos de ambos rebotan al implementador en modo correccion
   (tope: 3 rondas; lo no corregible se bloquea y se escala).
5. `user-docs-writer` escribe la guia de usuario de la feature (`.dev/manual/{slug}.md`,
   best-effort) y se commitea en la rama.
6. PR contra la rama de integracion, con el resumen, los veredictos (review y seguridad)
   y la guia de usuario.

### `/construir-lote` — el ejecutor del plan

Para correr el plan de corrido: toma el proximo lote desbloqueado, ejecuta y mergea
primero la **ronda de contratos** si esta pendiente, crea un worktree por feature y
lanza todos los implementadores **a la vez**. Sin pausas de aprobacion: el brief ya
fue auditado por `plan-inspection`, y el control humano queda en los PRs (uno por
feature). Un bloqueo en una feature no frena a las demas.

Tambien podes repartir el lote entre **varias instancias de Claude Code** (una por PC
o licencia): cada una corre `/construir <feature>` con una feature distinta del mismo
lote. `progress.json` coordina el estado **solo si viaja por git**: el protocolo
minimo es commitear y pushear el `progress.json` al marcar la feature `in_progress`
(el claim), y pullear antes de la compuerta de lote y antes de marcar `done`. Si dos
instancias reclaman la misma feature, vale el claim pusheado primero; la otra toma
otra feature.

## Estructura del plugin

```
build-pipeline/
  .claude-plugin/
    plugin.json
  agents/
    stack-profiler.md        descubre el stack y la base de seguridad (por evidencia)
    feature-implementer.md   construye una feature (modo plan / modo ejecucion)
    build-reviewer.md        revisa el diff contra el brief antes del PR
    security-gate.md         revisa el piso de seguridad (OWASP) antes del PR
    user-docs-writer.md      escribe la guia de usuario final (Markdown)
  skills/
    build-pipeline/
      SKILL.md               orquestacion de los dos modos
  commands/
    construir.md             /construir <feature>
    construir-lote.md        /construir-lote [BATCH-n]
  reference/
    owasp-baseline.md        base de seguridad canonica (OWASP Top 10 2021)
  PIPELINE.md
  README.md
```

## Garantias

- **Nada sin verificar**: una tarea esta terminada cuando sus criterios Gherkin se
  demostraron con tests verdes. El reviewer corre los tests; no le cree al reporte.
- **Nada fuera del brief**: sin features extra, refactors oportunistas ni dependencias
  que el diseno no pida. Tocar archivos de otra feature del lote es hallazgo `high`
  (rompe el paralelismo).
- **Piso de seguridad OWASP**: cada feature se codea con los mecanismos nativos del
  stack contra las categorias OWASP aplicables, y el `security-gate` lo verifica (mas el
  audit de dependencias) antes del PR. Veredictos en `.dev/build/security/`.
- **Trazabilidad hasta el codigo**: commits `[T-xxx]` → tarea → requisito → escenario
  → LEL → fuente. Reviews archivados en `.dev/build/reviews/`.
- **Manual de usuario que crece con el producto**: cada feature con superficie de
  usuario sale de su PR con su guia (`.dev/manual/`), en el vocabulario del LEL y
  fiel a lo construido. Best-effort: nunca bloquea un PR.
- **`progress.json` siempre al dia**: `done` = mergeado. Es lo que le permite a
  `/replanificar` absorber cambios de requisitos sin pisar lo construido.

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.

Nota historica: el plugin `feature-pipeline` (primera generacion, atado a
Next.js/TypeScript y a `/features/`) fue retirado a `archive/`; `build-pipeline` es
su reemplazo agnostico de stack.
