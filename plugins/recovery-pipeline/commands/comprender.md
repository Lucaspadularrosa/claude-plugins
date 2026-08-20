---
description: "Comprende una aplicacion existente (aunque no tenga documentacion): que hace, en que estado esta, que falta y que hay que decidir. Entrega el diagnostico con un reporte compartible y, si queres, reconstruye la linea de base de requisitos para engancharla con la suite."
argument-hint: "[opcional: ruta al repo; por defecto, el proyecto actual]"
---

Comprende esta aplicacion: `$ARGUMENTS`

Segui la skill `recovery-pipeline` de punta a punta:

1. Corre `code-inventory` (stack, layout, modulos, entry points, señales de salud) y
   despues extrae el comportamiento con `behavior-extraction` (que hace la app, con
   evidencia archivo:linea). Si la app es grande, particiona en tandas paralelas y
   consolida con `behavior-merge`.
2. Corre `evidence-spot-check`: verifica por muestreo que la evidencia citada
   sostiene lo afirmado; lo refutado se corrige antes de seguir.
3. Corre `gap-analysis` y mostrame el diagnostico: features completas, a medias y
   muertas, huecos e incoherencias, con el reporte compartible
   (`state-report.md` + `.html`).
4. Hace la PAUSA: mostrame el cuestionario del dueño (`owner-questions.md`). Puedo
   responderlo en el momento, o llevarselo a los stakeholders y traer las respuestas
   despues. No inventes respuestas.
5. Ofreceme reconstruir la linea de base en `.dev/requirements/` (mapa del producto,
   LEL, escenarios, requisitos, modelo de datos, diseno), registrada como `REC-xxx`
   en el changelog: es lo que engancha la app con el resto de la suite. Solo si
   acepto.
6. Cierra con el resumen: estado general, que quedo baselineado y en stub (si hubo
   reconstruccion), y los proximos pasos (completar con /requerimientos:incremento,
   auditar con /auditar, planificar y construir).

No modifiques ningun archivo del codigo: este pipeline solo lee y escribe en .dev/.
