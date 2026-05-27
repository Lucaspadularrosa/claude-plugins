---
description: Convierte la linea de base de requisitos en un plan de implementacion auditable (tareas, sprints y briefs de feature).
---

Genera el plan de implementacion a partir de la linea de base de requisitos del proyecto.

Segui la skill `planning-pipeline` de punta a punta:

1. Verifica que existan `.dev/requirements/requirements.json`, `technical-design.json` y
   `data-model.json`. Si falta alguno, deteni y pedime correr antes el pipeline de
   requisitos.
2. Encadena los subagentes: `task-derivation` -> `sprint-planning`.
3. Corre `plan-inspection` y su lazo de correccion hasta que el plan pase.
4. Corre `feature-brief` para emitir un documento por feature en `.dev/features/`.
5. Al final, lista los archivos generados en `.dev/plan/` y `.dev/features/` con un
   resumen de features, tareas, sprints y esfuerzo total.

$ARGUMENTS
