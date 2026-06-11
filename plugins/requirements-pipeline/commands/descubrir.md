---
description: Pasada panoramica de requisitos. Incorpora documentos, carpetas o una vision sin documento, y construye o actualiza el mapa del producto (features y escenarios stub priorizados). Re-ejecutable cada vez que llega material nuevo.
argument-hint: "[rutas a documentos o carpetas; vacio para arrancar sin documento]"
---

Ejecuta el modo DESCUBRIR de la skill `requirements-pipeline` sobre: `$ARGUMENTS`

1. Resolve las entradas: cada ruta puede ser un archivo (`.docx`, `.pdf`, `.md`,
   `.txt`) o una carpeta (procesa todos los archivos soportados que contenga,
   recursivo). Si no di ninguna ruta, arrancamos sin documento: pedime la vision del
   producto (que problema resuelve, para quien, que me imagino) y guardala como fuente
   en `.dev/requirements/sources/`. Tene en cuenta que sin documento el cuestionario
   de elicitacion va a ser mas largo: esta bien, las respuestas son la fuente.
2. Registra el descubrimiento (`DSC-xxx`) en `changelog.json` y extrae cada fuente con
   el script de la skill.
3. Corre `requirements-intake` (incremental si ya hay artefactos previos) ->
   `lel-authoring` (update si ya hay LEL) -> `lel-inspection`.
4. Corre `stakeholder-questionnaire` en modo elicitacion y hace la PAUSA: mostrame las
   preguntas y espera mis respuestas. Aplica las respuestas al LEL y reinspecciona.
5. Corre `product-mapping`: el mapa con las features y escenarios stub, priorizados.
   Lo que se solape con algo ya baselineado queda como propuesta pendiente, NO se
   aplica: mostramelo.
6. Cierra la entrada del changelog y mostrame `product-map.md` con tu sugerencia de
   que features elaborar primero (`/requerimientos:incremento ...`).
