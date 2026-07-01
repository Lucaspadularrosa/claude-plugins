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

**Seguridad por construccion**: junto al perfil de stack se deriva la base de seguridad
(`security-baseline.json`): la superficie de ataque del proyecto, las categorias OWASP
Top 10 aplicables y el mecanismo **nativo** del stack para cada una, mas el comando de
audit de dependencias. Con eso, el `feature-implementer` codea con un piso de seguridad
y el `security-gate` lo verifica antes del PR, sin conocimiento de seguridad hardcodeado.
Es prevencion (el piso); la auditoria profunda adversarial sigue siendo `audit-pipeline`
(`/auditar`), al que el gate deriva lo que excede el piso. La referencia canonica de
categorias y defensas es `reference/owasp-baseline.md`.

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
.dev/build/security-baseline.json   (superficie, categorias OWASP, mecanismo nativo por
                                     control, comando de audit de dependencias)
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
     implementar con piso OWASP ->                       EN PARALELO, modo ejecucion
     verificar Gherkin + dep-audit ->                    (sin pausas)
     lint -> commit [T-xxx]                                     |
        |                                                        |
   [build-reviewer] + [security-gate]                    [build-reviewer + security-gate
        -> lazo de correccion                             x N] -> lazos
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
| `stack-profiler` | Descubre stack, comandos, layout, convenciones y la base de seguridad del proyecto, por evidencia; valida comandos cuando puede | `agents/stack-profiler.md` |
| `feature-implementer` | Construye una feature: modo plan (propone sin tocar codigo) y modo ejecucion (implementa con el piso de seguridad OWASP, verifica criterios, commit por tarea) | `agents/feature-implementer.md` |
| `build-reviewer` | Revisa el diff contra el brief: cobertura, scope, correctitud, verificacion real (corre los tests) y convenciones | `agents/build-reviewer.md` |
| `security-gate` | Revisa el diff contra la base de seguridad (piso OWASP), corre el audit de dependencias y delega lo profundo a `/auditar` | `agents/security-gate.md` |

La orquestacion vive en la skill `skills/build-pipeline/SKILL.md`. La referencia
canonica de seguridad es `reference/owasp-baseline.md`.

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
- `security-gate` es la otra compuerta del PR: revisa el diff contra la base de
  seguridad (piso OWASP) y corre el audit de dependencias. Sus `high`/`medium` tambien
  rebotan al implementador hasta pasar; lo que excede el piso lo deriva a `/auditar`.

### progress.json
- `in_progress` al arrancar (con la rama); tareas `done` a medida que se verifican;
  feature `done` = **mergeada** a la rama de integracion (PR abierto no es done).
- Es el insumo de `/replanificar`: por eso se actualiza en cada transicion.

### Trazabilidad
- La cadena llega hasta el codigo: commit `[T-xxx]` -> tarea -> requisito ->
  escenario -> simbolo del LEL -> fuente. Los PRs citan `FG-xx` y sus tareas; los
  reviews quedan en `.dev/build/reviews/` y los veredictos de seguridad en
  `.dev/build/security/`. Los hallazgos de seguridad citan su categoria OWASP (`owasp_id`).

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
  security-baseline.json      base de seguridad del stack (superficie, OWASP, tooling)
  reviews/{slug}.json         veredicto de review por feature
  security/{slug}.json        veredicto de seguridad (piso OWASP) por feature
.dev/plan/progress.json       estado del build, al dia
ramas feature/{slug}          una por feature -> PR a la rama de integracion
```
