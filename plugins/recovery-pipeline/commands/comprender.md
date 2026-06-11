---
description: Comprende una aplicacion existente (aunque no tenga documentacion): que hace, en que estado esta, que falta y que hay que decidir. Reconstruye la linea de base de requisitos para engancharla con la suite.
argument-hint: "[opcional: ruta al repo; por defecto, el proyecto actual]"
---

Comprende esta aplicacion: `$ARGUMENTS`

Segui la skill `recovery-pipeline` de punta a punta:

1. Corre `code-inventory` (stack, layout, modulos, entry points, señales de salud) y
   despues `behavior-extraction` (que hace la app, con evidencia archivo:linea).
2. Registra la corrida (`REC-xxx`) en el changelog y corre `baseline-reconstruction`:
   la linea de base en `.dev/requirements/` (mapa del producto, LEL, escenarios,
   requisitos, modelo de datos, diseno), todo con evidencia al codigo. Lo que el
   codigo demuestra completo queda baselineado; lo incompleto queda en stub.
3. Corre `gap-analysis` y mostrame el reporte de estado: features completas, a medias
   y muertas, huecos e incoherencias.
4. Hace la PAUSA: mostrame el cuestionario del dueño (`owner-questions.md`) y espera
   mis respuestas. Aplicalas a la reconstruccion. No inventes respuestas.
5. Cierra con el resumen: estado general, que quedo baselineado y en stub, y los
   proximos pasos (completar con /requerimientos:incremento, auditar con /auditar,
   planificar y construir).

No modifiques ningun archivo del codigo: este pipeline solo lee y escribe en .dev/.
