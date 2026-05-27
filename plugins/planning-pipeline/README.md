# Planning Pipeline — Plugin de Claude Code

Plugin que convierte una linea de base de requisitos en un **plan de implementacion
auditable**: tareas trazables a los requisitos, agrupadas en fases y sprints, con un
documento por feature listo para alimentar un pipeline de build.

Es la continuacion del plugin `requirements-pipeline`: arranca donde aquel termina.

## Que tenes que poner en tu proyecto

Nada. El plugin se instala una vez y queda disponible en todos tus proyectos. En cada
proyecto solo aparecen las salidas, en `.dev/plan/` y `.dev/features/`.

## Estructura del plugin

```
planning-pipeline/
  .claude-plugin/
    plugin.json
  agents/
    task-derivation.md       deriva tareas verticales desde los requisitos
    sprint-planning.md       agrupa las tareas en fases y sprints
    parallel-planning.md     agrupa las features de cada sprint en lotes paralelos
    plan-inspection.md       audita el plan (cobertura, huerfanos, ciclos, staleness, paralelismo)
    feature-brief.md         emite un documento por feature (con lote paralelo)
  skills/
    planning-pipeline/
      SKILL.md               orquestacion del pipeline
  commands/
    planificar.md            slash command de entrada
  PIPELINE.md
  README.md
```

## Instalacion

Este plugin se distribuye en el mismo marketplace que `requirements-pipeline`. Con el
marketplace agregado:

```bash
claude plugin install planning-pipeline@plugins-claude
```

Los comandos exactos del CLI pueden variar segun la version de Claude Code: verificalos
con `/plugin` o `claude plugin --help`.

## Precondicion

El planning consume la salida del pipeline de requisitos. Antes de usarlo, el proyecto
debe tener generados:
- `.dev/requirements/requirements.json`
- `.dev/requirements/technical-design.json`
- `.dev/requirements/data-model.json`

Esos los produce el plugin `requirements-pipeline`. Si faltan, corre primero ese pipeline.

## Uso

```
/planificar
```

O en lenguaje natural:

```
Genera el plan de implementacion a partir de los requisitos.
```

## Como integra con los requisitos

El plan extiende la cadena de trazabilidad, no la rompe. Cada tarea cita los requisitos
que cubre, asi que la cadena de auditoria queda completa:

```
tarea -> requisito -> escenario -> episodio -> simbolo del LEL -> seccion del documento
```

Lo que hace al plan auditable: toda tarea traza a un requisito (sin huerfanos), todo
requisito esta cubierto por una tarea, y el plan registra de que version de los requisitos
se construyo, para detectar cuando quedo desactualizado. La etapa `plan-inspection`
verifica todo eso.

## Salidas

| Archivo | Contenido |
|---|---|
| `.dev/plan/tasks.json` / `.md` | Tareas trazables a los requisitos, agrupadas por feature. Las dependencias entre tareas se clasifican en `hard` (necesita el codigo mergeado) o `contract` (alcanza con la firma) |
| `.dev/plan/sprints.json` / `.md` | Fases y sprints |
| `.dev/plan/parallel-plan.json` / `.md` | Lotes paralelos por sprint: que features pueden desarrollarse simultaneamente sin esperarse |
| `.dev/plan/plan-inspection.json` / `.md` | Auditoria del plan |
| `.dev/features/{feature}.md` | Un brief por feature (incluye el lote paralelo asignado), para el pipeline de build |

## Paralelismo entre features

El pipeline esta pensado para que varias instancias de Claude Code (una por PC,
licencia o desarrollador) puedan trabajar en paralelo, una rama por feature, sin
esperarse mutuamente. Para lograrlo:

- `task-derivation` extrae **tareas-contrato** (`type: "contract"`) cuando una feature
  depende de otra: definen la firma publica (API, tipos, schema) que ambas necesitan.
  Despues de que el contrato se mergea, productor y consumidor desarrollan en paralelo.
- Las dependencias entre tareas se etiquetan con `kind`: `hard` (necesita el codigo
  ejecutable) o `contract` (alcanza con la firma). Solo las `hard` bloquean paralelismo.
- `parallel-planning` emite `.dev/plan/parallel-plan.json` con, por sprint, los **lotes
  paralelos** de features que pueden arrancar simultaneamente, y cuales esperan al
  siguiente lote. La metrica `max_parallel_degree` indica cuantas licencias en
  paralelo saca provecho del plan.
- Cada `feature-brief` declara en que lote cae y con quien puede correr en paralelo.

Si el plan termina con paralelismo bajo (sprints con un solo lote y varias features),
`plan-inspection` lo marca y rebota a `task-derivation` para extraer mas contratos o
partir features densamente acopladas.

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.
