# Pipeline: Build (ejecucion del plan)

Pipeline que ejecuta el plan generado por `planning-pipeline`: toma los briefs de
`.dev/features/`, implementa cada feature en su propia rama verificando los criterios
de aceptacion, y construye lotes completos en paralelo (un agente por feature, un
worktree por agente).

**Agnostico de stack por diseno**: el pipeline no sabe de ningun lenguaje o framework.
Todo lo especifico del proyecto sale del perfil de stack (`stack-profile.json`), que
se descubre por evidencia del propio repo: manifiestos, configs, CI, CLAUDE.md y el
`stack[]` del diseno tecnico. Para soportar un stack nuevo no se toca el plugin: se
corre en el proyecto.

---

## Flujo

```
.dev/features/{slug}.md          <- ENTRADA (briefs del planning-pipeline)
.dev/plan/execution-plan.json       (lotes y ronda de contratos)
.dev/plan/progress.json             (estado del build)
        |
        v  [stack-profiler]  (primera vez, o si el diseno cambio)
.dev/build/stack-profile.json       (stack, comandos test/lint/build, layout,
                                     convenciones, rama de integracion - por evidencia)
        |
        +---------------------------+----------------------------+
        |                                                        |
   /construir <feature>                                  /construir-lote [BATCH-n]
        |                                                        |
   [feature-implementer, modo plan]                      ronda de contratos (si esta
        -> PAUSA: aprobar el plan                        pendiente): implementar,
        |                                                review y merge primero
   rama feature/{slug}                                          |
   [feature-implementer, modo ejecucion]                 un worktree por feature
     tarea por tarea, en task_order:                     [feature-implementer x N]
     implementar -> verificar criterios                  EN PARALELO, modo ejecucion
     Gherkin -> lint -> commit [T-xxx]                   (sin pausas)
        |                                                        |
   [build-reviewer] -> lazo de correccion                [build-reviewer x N] -> lazos
        |                                                        |
   PR contra la rama de integracion                      push + PR por feature
        |                                                        |
        +---------------------------+----------------------------+
                                    |
                                    v
                    progress.json actualizado en cada transicion
                    (done = mergeado; los PRs abiertos quedan anotados)
```

---

## Agentes del pipeline

| Agente | Rol | Definicion |
|---|---|---|
| `stack-profiler` | Descubre stack, comandos, layout y convenciones del proyecto, por evidencia; valida comandos cuando puede | `agents/stack-profiler.md` |
| `feature-implementer` | Construye una feature: modo plan (propone sin tocar codigo) y modo ejecucion (implementa, verifica criterios, commit por tarea) | `agents/feature-implementer.md` |
| `build-reviewer` | Revisa el diff contra el brief: cobertura, scope, correctitud, verificacion real (corre los tests) y convenciones | `agents/build-reviewer.md` |

La orquestacion vive en la skill `skills/build-pipeline/SKILL.md`.

---

## Reglas de orquestacion

### Compuerta de lote
- Una feature solo se construye si su lote esta desbloqueado: los lotes de su
  `unlocks_after` con todas sus features `done` (mergeadas) y la ronda de contratos
  mergeada. El paralelismo del plan se respeta, no se inventa.

### Control asimetrico
- `/construir <feature>`: pausa unica de aprobacion del **plan de implementacion**
  antes de tocar codigo. Despues, implementacion y review corren solos hasta el PR.
- `/construir-lote`: sin pausas (el brief auditado por `plan-inspection` es el
  contrato); el control humano queda en los PRs.

### Verificacion obligatoria
- Cada tarea se verifica contra sus criterios Gherkin con los comandos del perfil
  antes de pasar a la siguiente. Commit por tarea con `[T-xxx]`.
- `build-reviewer` comprueba (no cree): corre tests y lint sobre el diff. Hallazgos
  `high`/`medium` rebotan al implementador hasta pasar.

### progress.json
- `in_progress` al arrancar (con la rama); tareas `done` a medida que se verifican;
  feature `done` = **mergeada** a la rama de integracion (PR abierto no es done).
- Es el insumo de `/replanificar`: por eso se actualiza en cada transicion.

### Trazabilidad
- La cadena llega hasta el codigo: commit `[T-xxx]` -> tarea -> requisito ->
  escenario -> simbolo del LEL -> fuente. Los PRs citan `FG-xx` y sus tareas; los
  reviews quedan en `.dev/build/reviews/`.

---

## Como iniciar

```
/construir importacion-padron        (una feature, con aprobacion del plan)
/construir-lote                      (el proximo lote desbloqueado, en paralelo)
/construir-lote BATCH-2              (un lote especifico)
```

O en lenguaje natural ("construi la feature de facturacion", "ejecuta el proximo
lote del plan").

---

## Estructura resultante

```
.dev/build/
  stack-profile.json          perfil de stack (por evidencia, versionado)
  reviews/{slug}.json         veredicto de review por feature
.dev/plan/progress.json       estado del build, al dia
ramas feature/{slug}          una por feature -> PR a la rama de integracion
```
