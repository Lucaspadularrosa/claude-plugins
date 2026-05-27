# Pipeline: Planificacion

Pipeline que convierte una linea de base de requisitos en un plan de implementacion
auditable: tareas trazables a los requisitos, agrupadas en fases y sprints, con un brief
por feature para alimentar un pipeline de build.

Es la continuacion natural del pipeline de requisitos: arranca donde aquel termina.

---

## Flujo

```
.dev/requirements/requirements.json
.dev/requirements/technical-design.json      <- ENTRADA (linea de base de requisitos)
.dev/requirements/data-model.json
        |
        v  [task-derivation]
.dev/plan/tasks.json + tasks.md               (tareas trazables, agrupadas por feature)
        |
        v  [sprint-planning]
.dev/plan/sprints.json + sprints.md           (fases y sprints)
        |
        v  [plan-inspection]
.dev/plan/plan-inspection.json + .md          (auditoria del plan)
        -> Si hay defectos high/medium: corregir (task-derivation / sprint-planning)
           -> plan-inspection
        |
        v  [feature-brief]
.dev/features/{feature}.md                    (un brief por feature)
        <- FIN (plan auditable + briefs para el pipeline de build)
```

---

## Agentes del pipeline

| Agente | Rol | Dispatch | Definicion |
|---|---|---|---|
| `task-derivation` | Deriva tareas verticales desde los requisitos, por feature | Secuencial | `agents/task-derivation.md` |
| `sprint-planning` | Agrupa las tareas en fases y sprints | Secuencial | `agents/sprint-planning.md` |
| `plan-inspection` | Audita el plan: cobertura, huerfanos, ciclos, desactualizacion | Secuencial | `agents/plan-inspection.md` |
| `feature-brief` | Emite un documento por feature en `.dev/features/` | Secuencial (al final) | `agents/feature-brief.md` |

La orquestacion vive en la skill `skills/planning-pipeline/SKILL.md`.

---

## Reglas de orquestacion

### Dispatch secuencial
- Cada etapa consume el archivo que produjo la anterior. No hay paralelismo.
- La precondicion es que exista la linea de base de requisitos en `.dev/requirements/`.

### Lazo de correccion del plan - condicional
- `plan-inspection` audita el plan. Si reporta defectos `high` o `medium`, volver a la
  etapa que corresponda en modo correccion (`task-derivation` para cobertura, huerfanos o
  dependencias; `sprint-planning` para orden o balance de sprints) y re-inspeccionar,
  hasta que el plan pase.

### Trazabilidad y auditoria
- Toda tarea cita `requirement_ids`; ningun requisito queda sin tarea.
- La cadena de auditoria se extiende: tarea -> requisito -> escenario -> episodio ->
  simbolo del LEL -> seccion del documento.
- El plan registra de que version de los requisitos y del diseno se construyo. Si esas
  versiones cambian, el plan quedo desactualizado y hay que re-planificar.

---

## Como iniciar el pipeline

Con el slash command:

```
/planificar
```

O en lenguaje natural (la skill se activa sola):

```
"Genera el plan de implementacion a partir de los requisitos."
```

El agente principal:
1. Verifica que exista la linea de base de requisitos en `.dev/requirements/`.
2. Encadena `task-derivation` -> `sprint-planning`.
3. Corre `plan-inspection` y su lazo de correccion hasta que el plan pase.
4. Corre `feature-brief` para emitir los `.dev/features/{feature}.md`.
5. Lista los archivos generados.

---

## Estructura resultante

```
.dev/plan/
  tasks.json / tasks.md           tareas trazables a los requisitos
  sprints.json / sprints.md       fases y sprints
  plan-inspection.json / .md      auditoria del plan
.dev/features/
  {feature}.md                    un brief por feature para el pipeline de build
```
