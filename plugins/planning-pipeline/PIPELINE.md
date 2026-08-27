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
        v  [script compute_execution_plan.py]  (determinista: cero tokens)
.dev/plan/execution-plan.json + .md           (ronda de contratos + lotes paralelos
                                               de features, con orden de tareas por
                                               feature, metricas y warnings accionables)
        |
        v  [script validate_plan.py]           (checks mecanicos: cero tokens)
        -> Si hay defectos: corregir (task-derivation con Edit quirurgico)
           -> recomputar el plan por script -> revalidar
        |
        v  [plan-inspection, modo juicio]
.dev/plan/plan-inspection.json + .md          (solo lo que requiere juicio:
                                               granularidad real, coherencia semantica
                                               de criterios, sanidad de lotes)
        |
        v  [script slice_brief_context.py]     (una tajada de contexto por feature)
        v  [feature-brief x N, EN PARALELO]    (un subagente por feature, cada uno
                                               lee solo su tajada)
        v  [script validate_plan.py --briefs]  (linter de briefs: cero tokens)
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

## Agentes y scripts del pipeline

| Etapa | Rol | Dispatch | Definicion |
|---|---|---|---|
| `task-derivation` (agente) | Deriva tareas verticales desde los requisitos, dimensionadas para una pasada de agente (`complexity`); clasifica dependencias en `hard` / `contract` y extrae tareas-contrato cross-feature. En correccion edita quirurgicamente con Edit | Secuencial | `agents/task-derivation.md` |
| `compute_execution_plan.py` (script) | Calcula la ronda de contratos y los lotes paralelos directo del grafo `hard` (niveles topologicos, metricas, warnings de extraccion de contratos). Determinista, cero tokens | Secuencial | `skills/planning-pipeline/scripts/` |
| `validate_plan.py` (script) | Corre los PLAN-CHECK mecanicos (cobertura, huerfanos, ciclos, staleness, lotes, metricas, summary) y el linter de briefs (`--briefs`). Cero tokens; los defectos rebotan con su etapa | Tras cada etapa | `skills/planning-pipeline/scripts/` |
| `plan-inspection` (agente) | Modo juicio: granularidad real de las tareas, coherencia semantica de los criterios y sanidad de los lotes (lo mecanico llega pre-verificado por script) | Secuencial | `agents/plan-inspection.md` |
| `slice_brief_context.py` (script) | Pre-corta una tajada de contexto por feature (`.dev/plan/.brief-context/`) para que los briefs paralelos no multipliquen el input | Antes de los briefs | `skills/planning-pipeline/scripts/` |
| `feature-brief` (agente) | Emite el brief de UNA feature desde su tajada; N subagentes corren en paralelo, uno por feature | **Paralelo** (al final) | `agents/feature-brief.md` |
| `execution-planning` (agente) | Solo en replanificacion (conservar lotes en curso y resolver conflictos requiere juicio) o como fallback sin Python | Solo replanificacion | `agents/execution-planning.md` |

La orquestacion vive en la skill `skills/planning-pipeline/SKILL.md`.

---

## Reglas de orquestacion

### Dispatch secuencial
- Cada etapa consume el archivo que produjo la anterior. Las etapas del pipeline son
  secuenciales; el paralelismo es del plan que producen.
- La precondicion es que exista la linea de base de requisitos en `.dev/requirements/`.

### Lazo de correccion del plan - script primero, juicio despues
- `validate_plan.py` corre los checks mecanicos en milisegundos y con cero tokens:
  sus defectos rebotan a `task-derivation` (que corrige con Edit quirurgico, no
  reescribiendo el archivo) y el execution-plan se recomputa gratis por script.
  Este lazo itera hasta verde sin consumir pasadas de inspeccion.
- `plan-inspection` corre en modo juicio cuando lo mecanico ya paso: granularidad
  real (004), coherencia semantica de criterios (006) y sanidad de lotes. Si reporta
  defectos confirmados `high` o `medium`, se corrige y re-inspecciona con tope de
  3 pasadas (los defectos remanentes los decide el usuario).
- El check de desactualizacion (007) no se corrige en ningun lazo: la correccion es
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
2. Corre `task-derivation` y despues el script `compute_execution_plan.py`.
3. Corre `validate_plan.py` (mecanico, hasta verde) y despues `plan-inspection` en
   modo juicio (tope: 3 pasadas; los defectos remanentes los decide el usuario).
4. Pre-corta el contexto por feature (`slice_brief_context.py`) y lanza los
   `feature-brief` en paralelo, uno por feature; cierra con el linter de briefs.
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
