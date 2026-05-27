---
description: Genera el flujo completo de requisitos (LEL, inspeccion, preguntas, escenarios y requisitos) a partir de un documento de dominio.
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
5. Al final, lista los archivos generados en `.dev/requirements/` con un resumen del
   conteo de simbolos, defectos, escenarios y requisitos.

Si no indique una ruta de documento, pedimela antes de empezar.
