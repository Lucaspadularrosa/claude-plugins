---
name: planning-pipeline
description: Convierte una linea de base de requisitos en un plan de ejecucion para agentes IA. Deriva tareas trazables a los requisitos dimensionadas para una pasada de agente, calcula los lotes de features que pueden construirse en paralelo, inspecciona el plan y emite un brief por feature. Usar cuando el usuario quiere planificar la construccion de un sistema a partir de requisitos ya generados.
---

# Pipeline de Planificacion (tareas, lotes paralelos y briefs de feature)

Esta skill convierte una linea de base de requisitos en un plan de ejecucion para una
flota de **agentes IA**: tareas trazables a los requisitos y dimensionadas para una
pasada de agente, lotes de features que pueden construirse en paralelo (una rama por
feature), y un documento por feature listo para un pipeline de build.

No hay sprints, fases ni estimaciones en tiempo humano: el orden lo dicta el grafo de
dependencias, y la metrica del plan es cuantos agentes pueden trabajar a la vez.

Vos, el agente principal, sos el orquestador: delegas cada etapa al subagente
correspondiente con la herramienta Task y encadenas las etapas.

## Precondicion

Esta etapa consume la salida del pipeline de requisitos. Antes de empezar, verifica que
existan en el proyecto:
- `.dev/requirements/requirements.json`
- `.dev/requirements/technical-design.json`
- `.dev/requirements/data-model.json`

Si falta alguno, detente e indicale al usuario que primero corra el pipeline de
requisitos (`requirements-pipeline`).

## Subagentes (en `agents/` del plugin)

| Orden | Subagente | Lee | Escribe |
|---|---|---|---|
| 1 | `task-derivation` | requisitos + diseno | `.dev/plan/tasks.json` (+ `.md`) |
| 2 | `execution-planning` | `tasks.json` | `.dev/plan/execution-plan.json` (+ `.md`) |
| 3 | `plan-inspection` | `tasks.json`, `execution-plan.json`, requisitos | `.dev/plan/plan-inspection.json` (+ `.md`) |
| 4 | `feature-brief` | plan + execution-plan + requisitos + diseno | `.dev/features/{feature}.md` |

## Procedimiento

### Paso 1 - Derivar tareas

Invoca `task-derivation` con la herramienta Task y espera a que termine. Deriva tareas
verticales dimensionadas para agentes (cada una cabe en una pasada), clasifica las
dependencias en `hard` / `contract` y extrae tareas-contrato cross-feature.

### Paso 2 - Planificar la ejecucion

Invoca `execution-planning`. Lee `tasks.json` y emite
`.dev/plan/execution-plan.json` (+ `.md`) con la ronda de contratos inicial y los lotes
ordenados de features que se pueden construir en paralelo respetando las dependencias
`hard`. Las dependencias `contract` no bloquean paralelismo (la tarea-contrato se mergea
en la ronda inicial).

### Paso 3 - Inspeccionar el plan (con lazo de correccion)

Invoca `plan-inspection`. Es la compuerta de auditoria del plan.

- Si devuelve `passed: true`, el plan cierra.
- Si reporta defectos `high` o `medium`, volve a invocar la etapa que corresponda en modo
  correccion, indicandole que lea `.dev/plan/plan-inspection.json` y aplique las
  correcciones propuestas:
  - `task-derivation` para defectos de cobertura, tareas huerfanas, dependencias,
    granularidad/complejidad, criterios de aceptacion, staleness o extraccion de
    contratos: checks 001, 002, 003, 004, 005, 006, 007, 011.
  - `execution-planning` para defectos de completitud, orden, metricas o lotes
    seriales sin justificar: checks 008, 009, 010, 012.
  Despues volve a invocar `plan-inspection`. Repeti hasta que el plan pase.

### Paso 4 - Emitir los briefs de feature

Cuando el plan paso la inspeccion, invoca `feature-brief`. Escribe un documento por
feature en `.dev/features/`, con su lote, su orden de tareas y sus contratos, listo para
alimentar un pipeline de desarrollo de features.

### Paso 5 - Cierre

Informa al usuario los archivos generados en `.dev/plan/` y `.dev/features/`, y resalta:
el conteo de features y tareas, el maximo paralelismo (`max_parallel_degree`: cuantos
agentes a la vez aprovecha el plan), el critical path en turnos
(`critical_path_length`), la cantidad de contratos en la ronda inicial y las preguntas
abiertas.

## Reglas de orquestacion

- El pipeline es secuencial: no lances una etapa sin el archivo de entrada de la anterior.
- El lazo de correccion del Paso 3 se repite hasta que el plan pase.
- Trazabilidad: ninguna tarea sin requisito; ningun requisito sin tarea. El plan registra
  de que version de los requisitos y del diseno se construyo, para detectar cuando quedo
  desactualizado.
- Si un subagente falla o produce un archivo vacio, detene el pipeline e informa al
  usuario en vez de continuar con datos incompletos.
- Despues de cada etapa, valida que el archivo de salida sea JSON valido y que los ids que
  referencia existan.

## Estructura resultante

```
.dev/plan/
  tasks.json / tasks.md             tareas trazables a los requisitos
  execution-plan.json / .md         ronda de contratos + lotes paralelos de features
  plan-inspection.json / .md        inspeccion del plan (auditoria)
.dev/features/
  {feature}.md                      un brief por feature para el pipeline de build
```
