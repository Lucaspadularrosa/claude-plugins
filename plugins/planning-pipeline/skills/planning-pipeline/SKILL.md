---
name: planning-pipeline
description: Convierte una linea de base de requisitos en un plan de implementacion auditable. Deriva tareas trazables a los requisitos, las agrupa en fases y sprints, inspecciona el plan y emite un documento por feature. Usar cuando el usuario quiere planificar la construccion de un sistema a partir de requisitos ya generados.
---

# Pipeline de Planificacion (tareas, sprints y briefs de feature)

Esta skill convierte una linea de base de requisitos en un plan de implementacion
auditable: tareas trazables a los requisitos, agrupadas en sprints, con un documento por
feature listo para un pipeline de build.

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
| 2 | `sprint-planning` | `tasks.json` | `.dev/plan/sprints.json` (+ `.md`) |
| 3 | `parallel-planning` | `tasks.json`, `sprints.json` | `.dev/plan/parallel-plan.json` (+ `.md`) |
| 4 | `plan-inspection` | `tasks.json`, `sprints.json`, `parallel-plan.json`, requisitos | `.dev/plan/plan-inspection.json` (+ `.md`) |
| 5 | `feature-brief` | plan + parallel-plan + requisitos + diseno | `.dev/features/{feature}.md` |

## Procedimiento

### Paso 1 - Derivar tareas y planificar sprints

Invoca `task-derivation` y luego `sprint-planning`, en orden y de a una con la herramienta
Task. Espera a que cada subagente termine antes de lanzar el siguiente.

### Paso 2 - Planificar lotes paralelos

Invoca `parallel-planning`. Lee `tasks.json` y `sprints.json` y emite
`.dev/plan/parallel-plan.json` (+ `.md`) con, por sprint, los lotes de features que se
pueden desarrollar en paralelo respetando las dependencias `hard`. Las dependencias
`contract` no bloquean paralelismo (la tarea-contrato se mergea en sprint anterior).

### Paso 3 - Inspeccionar el plan (con lazo de correccion)

Invoca `plan-inspection`. Es la compuerta de auditoria del plan.

- Si devuelve `passed: true`, el plan cierra.
- Si reporta defectos `high` o `medium`, volve a invocar la etapa que corresponda en modo
  correccion, indicandole que lea `.dev/plan/plan-inspection.json` y aplique las
  correcciones propuestas:
  - `task-derivation` para defectos de cobertura, tareas huerfanas, dependencias o
    paralelismo bajo (extraer mas tareas-contrato, partir features acopladas):
    checks 001, 002, 003, 010, 011, 014.
  - `sprint-planning` para defectos de orden o balance de sprints, o posicion de
    tareas-contrato: checks 005, 008, 009, 012.
  - `parallel-planning` para defectos de coherencia o batching: check 013.
  Despues volve a invocar `plan-inspection`. Repeti hasta que el plan pase.

### Paso 4 - Emitir los briefs de feature

Cuando el plan paso la inspeccion, invoca `feature-brief`. Escribe un documento por
feature en `.dev/features/`, listo para alimentar un pipeline de desarrollo de features.

### Paso 5 - Cierre

Informa al usuario los archivos generados en `.dev/plan/` y `.dev/features/`, y resalta el
conteo de features, tareas y sprints, el esfuerzo total, el grado de paralelismo maximo
(de `parallel-plan.json`) y las preguntas abiertas.

## Reglas de orquestacion

- El pipeline es secuencial: no lances una etapa sin el archivo de entrada de la anterior.
- El lazo de correccion del Paso 2 se repite hasta que el plan pase.
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
  tasks.json / tasks.md           tareas trazables a los requisitos
  sprints.json / sprints.md       fases y sprints
  parallel-plan.json / .md        lotes paralelos por sprint
  plan-inspection.json / .md      inspeccion del plan (auditoria)
.dev/features/
  {feature}.md                    un brief por feature para el pipeline de build
```
