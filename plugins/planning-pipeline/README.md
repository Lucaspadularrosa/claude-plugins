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
    replanificar.md          actualiza el plan cuando los requisitos cambian
  PIPELINE.md
  README.md
```

## Instalacion

Este plugin se distribuye en el mismo marketplace que `requirements-pipeline`
(`lpadularrosa-dev-plugins`). Con el marketplace agregado:

```bash
claude plugin install planning-pipeline@lpadularrosa-dev-plugins
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
/planificar          (primera vez)
/replanificar        (cuando los requisitos cambiaron despues de planificar)
```

O en lenguaje natural:

```
Genera el plan de ejecucion a partir de los requisitos.
Los requisitos cambiaron: actualiza el plan sin tocar lo construido.
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
| `.dev/plan/progress.json` | Estado de ejecucion del plan (features: pending / in_progress / done; tareas suman blocked y cancelled); lo actualiza el pipeline de build o el usuario |
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

## Replanificacion: cuando los requisitos cambian a mitad del build

El pipeline de requisitos (`requirements-pipeline`) es iterativo: llegan incrementos y
change requests despues de planificar. `/replanificar` los absorbe sin regenerar el
plan ni tocar lo construido:

1. El delta se calcula contra `.dev/requirements/changelog.json`: las entradas
   `INC-xxx`/`CR-xxx` aplicadas que no figuran en `metadata.applied_changelog_ids` del
   plan.
2. `progress.json` dice que esta hecho. Con eso: requisito nuevo -> tareas nuevas;
   requisito modificado -> se reescriben solo las tareas `pending` (lo `done` recibe
   una **tarea de ajuste**, nunca se reescribe la historia); requisito deprecado ->
   tareas `pending` canceladas, y si habia trabajo construido encima queda como
   conflicto que decide el usuario.
3. Los lotes se recalculan **solo para el trabajo restante**: las features terminadas
   salen del grafo (sus dependencias cuentan como satisfechas), las que estan en curso
   conservan su lote, y lo nuevo se inserta por niveles — incluso en paralelo con lo
   que ya corre, si el grafo lo permite.
4. Se regeneran solo los briefs de las features afectadas, citando que entrada del
   changelog las cambio.

Nada se borra: las tareas canceladas quedan con `status: "cancelled"` y todo el delta
queda auditado en el changelog y en `applied_changelog_ids`.

## Quien ejecuta el plan

El ejecutor nativo de los briefs es el plugin `build-pipeline` (este mismo
marketplace): `/construir <feature>` toma un brief y construye la feature en su rama
(en cualquier stack), y `/construir-lote` ejecuta un lote completo en paralelo con un
subagente por feature, actualizando `progress.json` — el insumo de `/replanificar`.

El plugin `feature-pipeline` es independiente: lee requerimientos de `/features/` (en
la raiz del proyecto) con su propia estructura y flujo de aprobacion humana. No
engancha de forma directa con estos briefs.

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.
