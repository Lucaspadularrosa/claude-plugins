---
description: Flujo completo de requisitos en una corrida (descubrir + elaborar todas las features). Util para proyectos chicos o documentos cerrados; para trabajo iterativo usa /requerimientos:descubrir e /requerimientos:incremento.
argument-hint: <rutas a documentos o carpetas>
---

Genera la linea de base de requisitos completa a partir de: `$ARGUMENTS`

Es el modo COMPLETO de la skill `requirements-pipeline`: equivale a DESCUBRIR mas un
unico INCREMENTO con todas las features del mapa. Registra igual el descubrimiento
(`DSC-xxx`) y el incremento (`INC-xxx`) en `changelog.json`, asi el proyecto puede
seguir despues por los modos incrementales. Acepta varios documentos y carpetas.

Segui la skill de punta a punta:

1. Extrae el texto de cada documento (las carpetas se expanden a sus archivos
   soportados) a `.dev/requirements/sources/` con el script `extract_document.py`.
2. Encadena los subagentes en orden: `requirements-intake` -> `lel-authoring` ->
   `lel-inspection` -> `stakeholder-questionnaire`.
3. Hace la PAUSA obligatoria: mostrame `.dev/requirements/stakeholder-questions.md` y
   espera mis respuestas. Si respondo, actualiza el LEL y reinspecciona; si digo que
   no hay dudas, segui.
4. Corre `product-mapping` para dejar el mapa del producto registrado, y continua con
   `scenario-modeling` y `requirements-specification` sobre TODAS las features.
5. Corre `requirements-inspection` y su lazo de correccion: si reporta defectos `high`
   o `medium`, volve a `requirements-specification` en modo correccion y reinspecciona,
   hasta que la especificacion pase.
6. Preguntame si tengo mockups de UI (HTML, CSS, wireframes o capturas) para las
   pantallas. Despues corre `technical-design` (con los mockups como diseno
   autoritativo si los hay).
7. Cierra con `design-inspection` y su lazo de correccion: si reporta defectos `high` o
   `medium`, volve a `technical-design` en modo correccion y reinspecciona, hasta que el
   diseno pase.
8. Marca todo el mapa como `baselined`, cierra las entradas del changelog y lista los
   archivos generados en `.dev/requirements/` con un resumen del conteo de simbolos,
   defectos (LEL, requisitos y diseno), escenarios, requisitos, entidades del modelo de
   datos y decisiones, mas las preguntas abiertas que siguen bloqueando.

Si no indique ninguna ruta, sugerime usar `/requerimientos:descubrir` (que soporta
arrancar sin documento) o pedime las rutas antes de empezar.
