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
    plan-inspection.md       audita el plan (cobertura, huerfanos, ciclos, staleness)
    feature-brief.md         emite un documento por feature
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
| `.dev/plan/tasks.json` / `.md` | Tareas trazables a los requisitos, agrupadas por feature |
| `.dev/plan/sprints.json` / `.md` | Fases y sprints |
| `.dev/plan/plan-inspection.json` / `.md` | Auditoria del plan |
| `.dev/features/{feature}.md` | Un brief por feature, para el pipeline de build |

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.
