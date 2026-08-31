# Pipeline: Planificacion

Pipeline que convierte una linea de base de requisitos en un plan de ejecucion para una
flota de agentes IA: tareas trazables a los requisitos y dimensionadas para una pasada de
agente, lotes de features que pueden construirse en paralelo (una rama por feature) y un
brief por feature para alimentar un pipeline de build.

Es la continuacion natural del pipeline de requisitos: arranca donde aquel termina.

No hay sprints, fases ni estimaciones en tiempo humano: el orden lo dicta exclusivamente
el grafo de dependencias, y la metrica central es cuantos agentes pueden trabajar en
simultaneo.

Principio de diseno (desde 2.6): **todo lo determinista es script, cero tokens; el
modelo solo donde hay juicio**, y cada subagente lee una tajada, nunca la linea de base
completa. Python 3.8+ es requisito.

---

## Flujo

```
.dev/requirements/requirements.json
.dev/requirements/technical-design.json      <- ENTRADA (linea de base de requisitos)
.dev/requirements/data-model.json
        |
        v  [script slice_requirements_context.py --mapa]   proyeccion compacta
        v  [task-derivation, modo mapa]  (opus, 1 pasada)   features, aristas
                                                             cross-feature, contratos
        v  [script slice_requirements_context.py]           una tajada por feature
        v  [task-derivation, modo feature x N, EN PARALELO] parciales tasks.FG-xx.json
        v  [script merge_tasks.py]                          ids globales, deps
                                                             cross-feature, summary
.dev/plan/tasks.json
        |
        v  [script compute_execution_plan.py + render_plan_docs.py]   (una tanda)
.dev/plan/execution-plan.json + tasks.md + execution-plan.md
        |
        v  [script validate_plan.py]           (checks mecanicos, hasta verde)
        -> defectos: [task-patch] (sonnet, Edit quirurgico) -> recomputar -> revalidar
        |
        v  [plan-inspection, modo juicio]  ||  [script slice_brief_context.py
                                            ||   + render_brief.py]  (en paralelo)
        v  [script validate_plan.py --inyectar-checks + render_plan_docs.py]
.dev/plan/plan-inspection.json + .md
        |
        v  [feature-brief x N, EN PARALELO]  (haiku: solo resumen + superficie OWASP)
        v  [script validate_plan.py --briefs]  (linter de briefs)
.dev/features/FG-xx-{slug}.md
        <- FIN (plan auditable + briefs para el pipeline de build)
           + .dev/plan/progress.json inicializado por el orquestador (el build lo actualiza)


            /replanificar  (cuando los requisitos cambiaron)

changelog.json vs tasks.json metadata.applied_changelog_ids  -> delta
        + progress.json (estado del build; si falta, se pregunta)
        |
        v  [task-derivation modo feature, solo afectadas, con tajada --replan]
        v  [script merge_tasks.py --replan --features ...]   (conserva ids, continua numeracion)
        -> PAUSA si hay CONFLICTO (deprecado con tarea construida, etc.)
        |
        v  [script compute_execution_plan.py --replan]
            done fuera del grafo, in_progress conserva lote, nuevo por niveles,
            ajustes como entradas adjustment/groupable, contratos nuevos en lote propio
        -> exit 2 con CONFLICTOs: decide el usuario -> [execution-planning] los aplica
        |
        v  inspeccion (con PLAN-CHECK-013) -> briefs solo de las afectadas
        <- FIN (plan al dia, sin tocar lo construido)
```

---

## Agentes y scripts del pipeline

| Etapa | Rol | Modelo / dispatch | Definicion |
|---|---|---|---|
| `slice_requirements_context.py` | Proyeccion compacta (`--mapa`) y una tajada por feature para la derivacion; en `--replan` suma tareas previas, progress y delta | script | `skills/planning-pipeline/scripts/` |
| `task-derivation` | Modo mapa: features, aristas cross-feature y tareas-contrato. Modo feature: tareas verticales de UNA feature desde su tajada, dimensionadas para una pasada de agente | opus; mapa secuencial, feature **paralelo** | `agents/task-derivation.md` |
| `merge_tasks.py` | Consolida esqueleto + parciales en `tasks.json`: ids globales, dependencias cross-feature a nivel requisito, summary | script | `skills/planning-pipeline/scripts/` |
| `compute_execution_plan.py` | Ronda de contratos y lotes por niveles topologicos, metricas y warnings accionables; `--replan` para el trabajo restante | script | `skills/planning-pipeline/scripts/` |
| `render_plan_docs.py` | `tasks.md`, `execution-plan.md`, `plan-inspection.md` derivados de sus JSON | script | `skills/planning-pipeline/scripts/` |
| `validate_plan.py` | PLAN-CHECK mecanicos, linter de briefs (`--briefs`), inyeccion de checks en la inspeccion (`--inyectar-checks`) | script | `skills/planning-pipeline/scripts/` |
| `task-patch` | Aplica defectos ya diagnosticados sobre `tasks.json` con Edit quirurgico, sin releer la linea de base | sonnet | `agents/task-patch.md` |
| `plan-inspection` | Solo juicio: granularidad real (004), coherencia semantica de criterios (006), sanidad de lotes (012); en pasada 2+ acotado a los ids corregidos | sonnet | `agents/plan-inspection.md` |
| `slice_brief_context.py` + `render_brief.py` | Tajada por feature y brief completo renderizado con dos marcadores `<!-- LLM: -->` | script | `skills/planning-pipeline/scripts/` |
| `feature-brief` | Completa el resumen en prosa y la superficie OWASP del brief renderizado | haiku, **paralelo** | `agents/feature-brief.md` |
| `execution-planning` | Solo con CONFLICTOs de `--replan`: aplica las decisiones del usuario sobre el plan calculado | sonnet, excepcional | `agents/execution-planning.md` |

La orquestacion vive en la skill `skills/planning-pipeline/SKILL.md`.

---

## Reglas de orquestacion

### Script primero, juicio despues
- Lo determinista nunca pasa por un modelo: lotes, vistas, validacion, merge, render
  de briefs, inyeccion de checks. Los scripts tienen `--self-test` y corren en el CI.
- Los subagentes leen tajadas (`.dev/plan/.derivation-context/`,
  `.dev/plan/.brief-context/`), no la linea de base: el paralelismo no multiplica el
  input. Las carpetas de tajadas son temporales y se borran en el cierre.
- El orquestador lee solo `summary`/`passed`/`metadata` y la salida de los scripts.

### Lazo de correccion
- `validate_plan.py` itera hasta verde sin consumir pasadas; sus defectos los aplica
  `task-patch` (sonnet). Solo si `task-patch` necesita la linea de base se re-deriva
  esa feature con `task-derivation`.
- `plan-inspection` corre cuando lo mecanico paso; sus checks mecanicos los inyecta el
  script. Tope: 3 pasadas; en la 2+ recibe los `task_ids` corregidos y no relee todo.
- PLAN-CHECK-007 (desactualizacion) no se corrige en el lazo: es `/replanificar`.
- Las vistas `.md` se renderizan antes de validar (PLAN-CHECK-014 nunca sale en rojo
  por orden de pasos).

### Replanificacion - quirurgica, nunca destructiva
- Delta contra `changelog.json`; solo se re-derivan las features afectadas (merge con
  `--replan` conserva las demas byte a byte y falla si un parcial omite una tarea previa).
- `progress.json` protege lo construido: lo `done` no se reescribe (tareas de ajuste),
  lo `in_progress` conserva su lote, lo deprecado con trabajo hecho es un conflicto
  que decide el usuario.
- Nada se borra: las tareas canceladas quedan `status: "cancelled"`.

### Trazabilidad
- Toda tarea cita `requirement_ids`; ningun requisito `active` sin tarea. Cadena:
  tarea -> requisito -> escenario -> episodio -> simbolo del LEL -> seccion del documento.
- El plan registra versiones de requisitos y diseno y el changelog absorbido.

---

## Como iniciar el pipeline

```
/planificar          (primera vez)
/replanificar        (cuando los requisitos cambiaron despues de planificar)
```

O en lenguaje natural: "Genera el plan de ejecucion a partir de los requisitos."

---

## Estructura resultante

```
.dev/plan/
  tasks.json / tasks.md             tareas trazables a los requisitos (con applied_changelog_ids)
  execution-plan.json / .md         ronda de contratos + lotes paralelos de features
  plan-inspection.json / .md        auditoria del plan (juicio + checks mecanicos inyectados)
  progress.json                     estado de ejecucion (lo actualiza el build)
.dev/features/
  FG-xx-{slug}.md                   un brief por feature para el pipeline de build
```
