# Pipeline: Ingenieria de Requisitos

Pipeline para transformar un documento de dominio (Word, PDF o Markdown) en una linea de
base de requisitos trazable, aplicando el metodo LEL y Escenarios de Leite, Hadad, Kaplan
y Doorn. Es portable: vive en una carpeta `.claude/` y no depende de ninguna aplicacion.

---

## Flujo

```
documento de dominio (.docx / .pdf / .md)
        |
        v  [extract_document.py]
.dev/requirements/sources/{doc}.txt
        |
        v  [requirements-intake]
.dev/requirements/source-inventory.json
.dev/requirements/lel-candidates.json
.dev/requirements/supporting-context.json
        |
        v  [lel-authoring]
.dev/requirements/lel.json + lel.md
        |
        v  [lel-inspection]
.dev/requirements/lel-inspection.json + .md      (checklist de defectos)
        |
        v  [stakeholder-questionnaire]
.dev/requirements/stakeholder-questions.json + .md

        PAUSA OBLIGATORIA
             -> Presentar las preguntas al stakeholder
             -> Esperar respuestas explicitas
             -> Si hay respuestas: lel-authoring (update) -> lel-inspection
             -> Si no hay dudas: continuar

        v  [scenario-modeling]
.dev/requirements/scenarios.json + scenarios.md
        |
        v  [requirements-specification]
.dev/requirements/requirements.json + requirements.md

        CONSULTA DE UI
             -> Preguntar al usuario si hay mockups HTML, CSS o
                wireframes para usar en las pantallas
             -> Si los hay: technical-design los toma como diseno autoritativo

        v  [technical-design]  (+ mockups de UI si existen)
.dev/requirements/data-model.json + data-model.md
.dev/requirements/technical-design.json + technical-design.md
        |
        v  [design-inspection]
.dev/requirements/design-inspection.json + .md   (normalizacion + diseno)
        -> Si hay defectos high/medium: technical-design (correccion) -> design-inspection
        <- FIN (LEL + inspeccion + escenarios + requisitos + diseno + inspeccion de diseno)
```

---

## Agentes del pipeline

| Agente | Rol | Dispatch | Definicion |
|---|---|---|---|
| `requirements-intake` | Clasifica el documento en inventario, candidatos LEL y contexto | Secuencial | `.claude/agents/requirements-intake.md` |
| `lel-authoring` | Construye el Lexico Extendido del Lenguaje | Secuencial | `.claude/agents/lel-authoring.md` |
| `lel-inspection` | Inspecciona el LEL y produce el checklist de defectos | Secuencial | `.claude/agents/lel-inspection.md` |
| `stakeholder-questionnaire` | Arma las preguntas para el stakeholder | Secuencial | `.claude/agents/stakeholder-questionnaire.md` |
| `scenario-modeling` | Deriva los Escenarios desde el LEL | Secuencial | `.claude/agents/scenario-modeling.md` |
| `requirements-specification` | Especifica requisitos funcionales y no funcionales | Secuencial | `.claude/agents/requirements-specification.md` |
| `technical-design` | Produce el modelo de datos y el diseno tecnico (arquitectura, API, ADRs) | Secuencial | `.claude/agents/technical-design.md` |
| `design-inspection` | Inspecciona el diseno y la normalizacion del modelo de datos | Secuencial (al final) | `.claude/agents/design-inspection.md` |

La orquestacion vive en la skill `.claude/skills/requirements-pipeline/SKILL.md`.

---

## Reglas de orquestacion

### Dispatch secuencial (todo el pipeline)
- Cada etapa consume el archivo que produjo la anterior. No hay paralelismo.
- No invocar una etapa si falta el archivo de entrada que necesita.

### Punto de pausa obligatorio - NUNCA saltear
- Despues de `stakeholder-questionnaire`, SIEMPRE presentar las preguntas al usuario y
  esperar respuestas explicitas.
- Esta PROHIBIDO inventar respuestas del stakeholder.

### Lazo de respuestas - condicional
- Si no hay preguntas o el stakeholder no responde, saltear el lazo e ir directo a
  `scenario-modeling`.
- Si hay respuestas, volver a `lel-authoring` (modo update) y luego `lel-inspection`,
  antes de modelar los escenarios.

### Consulta de mockups de UI - antes del diseno
- Antes de invocar `technical-design`, el orquestador SIEMPRE le pregunta al usuario si
  tiene mockups HTML, CSS, wireframes o capturas para las pantallas.
- Si los hay, `technical-design` los toma como diseno autoritativo de las pantallas y
  reconcilia mockup contra requisitos. Si no, propone las pantallas de forma abstracta.

### Lazo de correccion del diseno - condicional
- `design-inspection` revisa el diseno; cuando el stack es relacional, incluye la
  normalizacion en formas normales (1FN, 2FN, 3FN).
- Si reporta defectos `high` o `medium`, volver a `technical-design` en modo correccion
  y luego re-inspeccionar, hasta que el diseno pase.

### Trazabilidad
- Ningun paso inventa vocabulario. Los escenarios usan simbolos del LEL; los requisitos
  trazan a escenarios, episodios y simbolos.

---

## Como iniciar el pipeline

Con el slash command:

```
/requerimientos ruta/al/documento.docx
```

O en lenguaje natural (la skill se activa sola):

```
"Genera los requisitos a partir de este documento: ruta/al/documento.pdf"
```

El agente principal:
1. Extrae el texto del documento a `.dev/requirements/sources/`.
2. Encadena `requirements-intake` -> `lel-authoring` -> `lel-inspection` ->
   `stakeholder-questionnaire`.
3. Presenta el cuestionario y espera (PAUSA).
4. Aplica respuestas si las hay, continua con `scenario-modeling` ->
   `requirements-specification`, pregunta si hay mockups de UI, corre `technical-design`
   y cierra con `design-inspection` (con su lazo de correccion).
5. Lista los archivos generados.

---

## Estructura esperada en cada proyecto

```
.claude/
  agents/         los 8 subagentes del pipeline
  skills/
    requirements-pipeline/   skill de orquestacion + script de extraccion
  commands/
    requerimientos.md        slash command de entrada

.dev/
  requirements/   <- salidas generadas por el pipeline
```
