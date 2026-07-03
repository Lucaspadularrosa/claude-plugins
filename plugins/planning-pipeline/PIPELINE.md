# Pipeline: Planificacion

Pipeline que convierte una linea de base de requisitos en un plan de ejecucion para una
flota de agentes IA: tareas trazables a los requisitos y dimensionadas para una pasada de
agente, lotes de features que pueden construirse en paralelo (una rama por feature) y un
brief por feature para alimentar un pipeline de build.

Es la continuacion natural del pipeline de requisitos: arranca donde aquel termina.

No hay sprints, fases ni estimaciones en tiempo humano: el orden lo dicta exclusivamente
el grafo de dependencias, y la metrica central es cuantos agentes pueden trabajar en
simultaneo.

---

## Flujo

```
.dev/requirements/requirements.json
.dev/requirements/technical-design.json      <- ENTRADA (linea de base de requisitos)
.dev/requirements/data-model.json
        |
        v  [task-derivation]
.dev/plan/tasks.json + tasks.md               (tareas verticales por feature, con
                                               complexity para agentes, dependency kind
                                               hard/contract y tareas-contrato)
        |
        v  [execution-planning]
.dev/plan/execution-plan.json + .md           (ronda de contratos + lotes paralelos
                                               de features, con orden de tareas por
                                               feature)
        |
        v  [plan-inspection]
.dev/plan/plan-inspection.json + .md          (auditoria del plan + paralelismo)
        -> Si hay defectos high/medium: corregir (task-derivation /
           execution-planning) -> plan-inspection
        |
        v  [feature-brief]
.dev/features/{feature}.md                    (un brief por feature, con su lote,
                                               su orden de tareas y sus contratos)
        <- FIN (plan auditable + briefs para el pipeline de build)
           + .dev/plan/progress.json inicializado por el orquestador (el build lo actualiza)


            /replanificar  (cuando los requisitos cambiaron)

.dev/requirements/changelog.json  vs  tasks.json metadata.applied_changelog_ids
        |
        v  delta = INC/CR/REC aplicados que el plan no absorbio
        v  + .dev/plan/progress.json (estado del build; si falta, se pregunta)
        |
        v  [task-derivation, modo replanificacion]
            solo las features afectadas: tareas nuevas / reescritas (pending) /
            tareas de ajuste (done) / canceladas (deprecado + pending)
        -> PAUSA si hay conflictos (deprecado con tarea construida, etc.)
        |
        v  [execution-planning, modo replanificacion]
            lotes solo del trabajo restante (done fuera del grafo,
            in_progress conserva su lote, lo nuevo entra por niveles)
        |
        v  [plan-inspection] -> lazo de correccion
        v  [feature-brief]   -> solo los briefs de las features afectadas
        <- FIN (plan al dia, sin tocar lo construido)
```

---

## Agentes del pipeline

| Agente | Rol | Dispatch | Definicion |
|---|---|---|---|
| `task-derivation` | Deriva tareas verticales desde los requisitos, dimensionadas para una pasada de agente (`complexity`); clasifica dependencias en `hard` / `contract` y extrae tareas-contrato cross-feature | Secuencial | `agents/task-derivation.md` |
| `execution-planning` | Calcula la ronda de contratos inicial y los lotes de features que pueden construirse en paralelo, directo del grafo de dependencias `hard` | Secuencial | `agents/execution-planning.md` |
| `plan-inspection` | Audita el plan: cobertura, huerfanos, ciclos, granularidad para agentes, coherencia de los lotes y desactualizacion | Secuencial | `agents/plan-inspection.md` |
| `feature-brief` | Emite un documento por feature en `.dev/features/`, con su lote de ejecucion, el orden de sus tareas y sus contratos | Secuencial (al final) | `agents/feature-brief.md` |

La orquestacion vive en la skill `skills/planning-pipeline/SKILL.md`.

---

## Reglas de orquestacion

### Dispatch secuencial
- Cada etapa consume el archivo que produjo la anterior. Las etapas del pipeline son
  secuenciales; el paralelismo es del plan que producen.
- La precondicion es que exista la linea de base de requisitos en `.dev/requirements/`.

### Lazo de correccion del plan - condicional
- `plan-inspection` audita el plan. Si reporta defectos confirmados `high` o `medium`,
  volver a la etapa que corresponda en modo correccion y re-inspeccionar, con tope de
  3 pasadas (los defectos remanentes los decide el usuario):
  - `task-derivation` para cobertura, huerfanos, dependencias, granularidad y
    complejidad, criterios de aceptacion o extraccion de contratos
    (checks 001, 002, 003, 004, 005, 006, 011).
  - `execution-planning` para completitud, orden, metricas o lotes seriales sin
    justificar (checks 008, 009, 010, 012).
  - El check de desactualizacion (007) no se corrige en el lazo: la correccion es
    correr `/replanificar`.

### Replanificacion - quirurgica, nunca destructiva
- El delta se calcula contra `changelog.json` de requisitos: entradas `INC`/`CR`/`REC`
  aplicadas que no estan en `metadata.applied_changelog_ids` del plan (ni postergadas
  a proposito en `metadata.deferred_changelog_ids`).
- Solo se re-derivan las features afectadas; el resto del plan queda intacto.
- `progress.json` protege lo construido: lo `done` no se reescribe (se crean tareas de
  ajuste), lo `in_progress` no se mueve sin decision del usuario, y lo deprecado con
  trabajo hecho es un conflicto que decide el usuario, no un agente.
- Las tareas canceladas quedan con `status: "cancelled"`; nada se borra.

### Trazabilidad y auditoria
- Toda tarea cita `requirement_ids`; ningun requisito queda sin tarea.
- La cadena de auditoria se extiende: tarea -> requisito -> escenario -> episodio ->
  simbolo del LEL -> seccion del documento.
- El plan registra de que version de los requisitos y del diseno se construyo, y que
  entradas del changelog absorbio. Si algo de eso quedo atras, `plan-inspection` lo
  marca y la correccion es `/replanificar`.

---

## Como iniciar el pipeline

Con los slash commands:

```
/planificar          (primera vez)
/replanificar        (cuando los requisitos cambiaron despues de planificar)
```

O en lenguaje natural (la skill se activa sola):

```
"Genera el plan de ejecucion a partir de los requisitos."
```

El agente principal:
1. Verifica que exista la linea de base de requisitos en `.dev/requirements/`.
2. Encadena `task-derivation` -> `execution-planning`.
3. Corre `plan-inspection` y su lazo de correccion (tope: 3 pasadas; los defectos
   remanentes los decide el usuario).
4. Corre `feature-brief` para emitir los `.dev/features/{feature}.md`.
5. Lista los archivos generados, incluyendo el maximo paralelismo (agentes simultaneos)
   y el critical path en turnos.

---

## Estructura resultante

```
.dev/plan/
  tasks.json / tasks.md             tareas trazables a los requisitos
                                    (con applied_changelog_ids)
  execution-plan.json / .md         ronda de contratos + lotes paralelos de features
  plan-inspection.json / .md        auditoria del plan
  progress.json                     estado de ejecucion (lo actualiza el build)
.dev/features/
  {feature}.md                      un brief por feature para el pipeline de build
```
