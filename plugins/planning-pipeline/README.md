# Planning Pipeline — Plugin de Claude Code

Plugin que convierte una linea de base de requisitos en un **plan de ejecucion para
agentes IA**: tareas trazables a los requisitos y dimensionadas para una pasada de
agente, lotes de features que pueden construirse en paralelo (una rama por feature) y un
documento por feature listo para alimentar un pipeline de build.

Es la continuacion del plugin `requirements-pipeline`: arranca donde aquel termina.

A diferencia de un plan clasico, **no hay sprints, fases ni estimaciones en tiempo
humano**. El ejecutor del plan no es un equipo con velocidad fija: es una flota de
agentes. Por eso el orden lo dicta exclusivamente el grafo de dependencias, las tareas
se dimensionan por `complexity` (cuanto contexto y verificacion exige una pasada de
agente) y la metrica central del plan es `max_parallel_degree`: cuantos agentes pueden
trabajar a la vez.

## Que tenes que poner en tu proyecto

Nada. El plugin se instala una vez y queda disponible en todos tus proyectos. En cada
proyecto solo aparecen las salidas, en `.dev/plan/` y `.dev/features/`.

## Estructura del plugin

```
planning-pipeline/
  .claude-plugin/
    plugin.json
  agents/
    task-derivation.md       deriva tareas verticales dimensionadas para agentes
    execution-planning.md    ronda de contratos + lotes paralelos de features
    plan-inspection.md       audita el plan (cobertura, ciclos, granularidad, paralelismo)
    feature-brief.md         emite un documento por feature (con lote y orden de tareas)
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
Genera el plan de ejecucion a partir de los requisitos.
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
| `.dev/plan/tasks.json` / `.md` | Tareas trazables a los requisitos, agrupadas por feature, con `complexity` (low/medium/high) para una pasada de agente. Las dependencias entre tareas se clasifican en `hard` (necesita el codigo mergeado) o `contract` (alcanza con la firma) |
| `.dev/plan/execution-plan.json` / `.md` | Ronda de contratos inicial + lotes paralelos de features, con el orden de tareas de cada feature (`task_order`) y las metricas de paralelismo |
| `.dev/plan/plan-inspection.json` / `.md` | Auditoria del plan |
| `.dev/features/{feature}.md` | Un brief por feature (con su lote, su orden de tareas y sus contratos), para el pipeline de build |

## Como se ejecuta el plan con agentes en paralelo

El pipeline esta pensado para que varias instancias de Claude Code (una por PC,
licencia o agente) trabajen en paralelo, una rama por feature, sin esperarse
mutuamente:

1. **Ronda de contratos** (`contract_round`): primero se ejecutan y mergean las
   tareas-contrato (`type: "contract"`), que definen las firmas publicas (API, tipos,
   schemas, eventos) entre features. Son chicas y baratas.
2. **Lotes** (`BATCH-1`, `BATCH-2`, ...): cada lote agrupa las features que no tienen
   dependencias `hard` entre si. Se lanza un agente por feature del lote, cada uno en
   su rama, todos a la vez. Cuando el lote mergea, arranca el siguiente.
3. Dentro de su rama, cada agente ejecuta las tareas de su feature en el `task_order`
   del plan y verifica cada una contra sus criterios de aceptacion Gherkin.

Las claves del paralelismo:

- `task-derivation` extrae **tareas-contrato** cuando una feature depende de otra: el
  consumidor pasa a depender de la firma (`kind: "contract"`) en vez del codigo completo
  (`kind: "hard"`). Solo las dependencias `hard` bloquean paralelismo.
- `execution-planning` emite `.dev/plan/execution-plan.json` con la ronda de contratos
  y los lotes. `max_parallel_degree` dice cuantos agentes simultaneos aprovecha el
  plan; `critical_path_length` cuantos turnos lleva ejecutarlo.
- Cada `feature-brief` declara en que lote cae, con quien corre en paralelo y que tiene
  que estar mergeado antes de arrancar.

Si el plan termina con paralelismo bajo, `execution-planning` emite warnings
**accionables** (que tarea concreta extraer como contrato para subir una feature de
lote) y `plan-inspection` rebota a `task-derivation` para extraer mas contratos o
partir features densamente acopladas.

## Relacion con `feature-pipeline`

Los briefs de `.dev/features/` estan pensados para un pipeline de build generico que
tome un brief y construya la feature. El plugin `feature-pipeline` de este mismo
marketplace es independiente: lee requerimientos de `/features/` (en la raiz del
proyecto) con su propia estructura y flujo de aprobacion humana. Hoy no enganchan de
forma directa; si queres alimentar `feature-pipeline` con estos briefs, copialos a
`/features/` y revisa que el spec resultante respete el lote de ejecucion del plan.

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.
