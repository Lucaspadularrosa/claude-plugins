---
description: Genera el flujo completo de requisitos (LEL, inspeccion, preguntas, escenarios, requisitos, inspeccion de requisitos y diseno tecnico) a partir de un documento de dominio.
argument-hint: <ruta-al-documento.docx|.pdf|.md>
---

Genera la linea de base de requisitos a partir del documento: `$ARGUMENTS`

Segui la skill `requirements-pipeline` de punta a punta:

1. Extrae el texto del documento a `.dev/requirements/sources/` con el script
   `extract_document.py` de la skill.
2. Encadena los subagentes en orden: `requirements-intake` -> `lel-authoring` ->
   `lel-inspection` -> `stakeholder-questionnaire`.
3. Hace la PAUSA obligatoria: mostrame `.dev/requirements/stakeholder-questions.md` y
   espera mis respuestas. Si respondo, actualiza el LEL y reinspecciona; si digo que
   no hay dudas, segui.
4. Continua con `scenario-modeling` y `requirements-specification`.
5. Corre `requirements-inspection` y su lazo de correccion: si reporta defectos `high`
   o `medium`, volve a `requirements-specification` en modo correccion y reinspecciona,
   hasta que la especificacion pase.
6. Preguntame si tengo mockups de UI (HTML, CSS, wireframes o capturas) para las
   pantallas. Despues corre `technical-design` (con los mockups como diseno
   autoritativo si los hay).
7. Cierra con `design-inspection` y su lazo de correccion: si reporta defectos `high` o
   `medium`, volve a `technical-design` en modo correccion y reinspecciona, hasta que el
   diseno pase.
8. Al final, lista los archivos generados en `.dev/requirements/` con un resumen del
   conteo de simbolos, defectos (LEL, requisitos y diseno), escenarios, requisitos,
   entidades del modelo de datos y decisiones, mas las preguntas abiertas que siguen
   bloqueando.

Si no indique una ruta de documento, pedimela antes de empezar.
