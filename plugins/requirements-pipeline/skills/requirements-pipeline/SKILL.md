---
name: requirements-pipeline
description: Genera un flujo completo de ingenieria de requisitos (LEL, inspeccion, preguntas a stakeholders, escenarios, requisitos funcionales y no funcionales, y diseno tecnico con modelo de datos y arquitectura) a partir de un documento de dominio en Word, PDF o Markdown. Usar cuando el usuario quiere convertir documentacion o una especificacion en requisitos estructurados y trazables.
---

# Pipeline de Ingenieria de Requisitos (LEL y Escenarios)

Esta skill orquesta la conversion de un documento de dominio en una linea de base de
requisitos trazable, aplicando el metodo LEL y Escenarios de Leite, Hadad, Kaplan y Doorn.

Vos, el agente principal, sos el orquestador: ejecutas el script de extraccion y delegas
cada etapa al subagente correspondiente con la herramienta Task. Cada subagente lee y
escribe archivos; vos encadenas las etapas y manejas la pausa con el stakeholder.

## Subagentes (en `.claude/agents/`)

| Orden | Subagente | Lee | Escribe |
|---|---|---|---|
| 1 | `requirements-intake` | texto del documento | `source-inventory.json`, `lel-candidates.json`, `supporting-context.json` |
| 2 | `lel-authoring` | los 3 archivos de intake | `lel.json`, `lel.md` |
| 3 | `lel-inspection` | `lel.json` | `lel-inspection.json`, `lel-inspection.md` |
| 4 | `stakeholder-questionnaire` | `lel.json`, `lel-inspection.json` | `stakeholder-questions.json`, `stakeholder-questions.md` |
| 5 | `scenario-modeling` | `lel.json`, `lel-inspection.json` | `scenarios.json`, `scenarios.md` |
| 6 | `requirements-specification` | `scenarios.json`, `lel.json` | `requirements.json`, `requirements.md` |
| 7 | `technical-design` | `requirements.json`, `supporting-context.json`, `lel.json`, mockups de UI (opcional) | `data-model.json`, `technical-design.json` (+ `.md`) |
| 8 | `design-inspection` | `data-model.json`, `technical-design.json`, `requirements.json` | `design-inspection.json`, `design-inspection.md` |

Todos los archivos se generan en `.dev/requirements/` del proyecto actual.

## Procedimiento

### Paso 0 - Documento de entrada

Identifica la ruta del documento (Word, PDF, Markdown o texto). Si el usuario no la dio,
preguntala antes de seguir.

### Paso 1 - Extraer el texto

Crea `.dev/requirements/sources/` y extrae el texto con el script de esta skill. El script
vive en la subcarpeta `scripts/` de la skill; usa la variable `${CLAUDE_SKILL_DIR}`, que
apunta a la carpeta de la skill tanto si esta instalada como plugin como si esta suelta
en `.claude/skills/`:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/extract_document.py" \
  "<ruta-del-documento>" ".dev/requirements/sources/<nombre>.txt"
```

Si `${CLAUDE_SKILL_DIR}` no estuviera definida, ubica `extract_document.py` dentro de la
carpeta `scripts/` de esta skill y ejecutalo igual.

Si el documento es PDF y el script informa que falta una biblioteca, instala una:
`pip install pypdf`. Para `.md` o `.txt` el script solo copia el texto.

### Paso 2 - Etapas 1 a 4 (intake -> LEL -> inspeccion -> preguntas)

Invoca, en orden y de a una, las etapas 1 a 4 con la herramienta Task, delegando al
subagente por su nombre. A cada subagente pasale: la ruta del archivo de texto extraido
(solo a `requirements-intake`) y la instruccion de leer sus entradas y escribir sus
salidas en `.dev/requirements/`. Espera a que cada subagente termine antes de lanzar el
siguiente: cada etapa consume el archivo de la anterior.

### Paso 3 - PAUSA OBLIGATORIA con el stakeholder

Cuando `stakeholder-questionnaire` termina, NO sigas automaticamente. Mostrale al usuario
el contenido de `.dev/requirements/stakeholder-questions.md` y pedile que lo responda o
que lo lleve al stakeholder.

- Si el usuario aporta respuestas: guardalas en `.dev/requirements/stakeholder-answers.md`
  (una respuesta por `QST-xxx`). Volve a invocar `lel-authoring` en modo actualizacion,
  indicandole que lea el `lel.json` previo, el `lel-inspection.json` y el
  `stakeholder-answers.md`, y que aplique TODAS las respuestas y TODOS los defectos
  confirmados. Despues volve a invocar `lel-inspection` sobre el LEL actualizado.
  Verifica el cierre del lazo: si la nueva inspeccion reporta referencias colgadas a
  preguntas resueltas o respuestas `QST-xxx` sin aplicar, volve a invocar `lel-authoring`
  con ese detalle hasta que el lazo cierre. Recien entonces segui.
- Si el usuario dice que no hay dudas o pide continuar: segui sin el lazo de respuestas.

Nunca inventes respuestas del stakeholder.

### Paso 4 - Etapas 5 a 8 (escenarios -> requisitos -> diseno -> inspeccion de diseno)

Invoca, en orden y de a una: `scenario-modeling` y luego `requirements-specification`,
sobre la ultima version de `lel.json`.

Antes de invocar `technical-design`, PREGUNTALE al usuario si tiene assets de diseno de
UI para usar en las pantallas: mockups HTML, wireframes, hojas de estilo CSS o capturas.
Pueden estar en cualquier carpeta; lo mas probable es que esten junto al documento de
entrada o en una subcarpeta.

- Si el usuario indica una ubicacion: pasasela a `technical-design` para que tome esos
  mockups como diseno autoritativo de las pantallas.
- Si el usuario dice que no hay: invoca `technical-design` igual, sin assets de UI; las
  pantallas se proponen de forma abstracta.

`technical-design` lee `requirements.json`, `supporting-context.json`, `lel.json` y, si
los hay, los assets de UI; reconecta el contexto de soporte que el intake habia separado
para esta etapa.

Cuando `technical-design` termina, invoca `design-inspection` sobre `data-model.json` y
`technical-design.json`. Es el segundo par de ojos del diseno: revisa la estructura del
modelo de datos y, cuando el stack es relacional, la normalizacion en formas normales.

- Si la inspeccion devuelve `passed: true`, el diseno cierra.
- Si reporta defectos `high` o `medium`, volve a invocar `technical-design` en modo
  correccion, indicandole que lea `design-inspection.json` y aplique las correcciones
  propuestas. Despues volve a invocar `design-inspection`. Repeti hasta que el diseno
  pase o solo queden defectos `low`.

### Paso 5 - Cierre

Informa al usuario los archivos generados en `.dev/requirements/` y resalta el conteo de
simbolos del LEL, defectos del LEL y del diseno, escenarios, requisitos, entidades del
modelo de datos y decisiones de diseno, mas las preguntas abiertas que siguen bloqueando.

## Reglas de orquestacion

- El pipeline es estrictamente secuencial: no lances una etapa sin el archivo de entrada
  de la anterior.
- La pausa del Paso 3 nunca se saltea.
- Ningun paso debe inventar vocabulario: los escenarios usan simbolos del LEL y los
  requisitos trazan a escenarios.
- Si un subagente falla o produce un archivo vacio, detene el pipeline e informa al
  usuario en vez de continuar con datos incompletos.
- Despues de cada etapa, valida que el archivo de salida sea JSON valido y que los ids
  que referencia (simbolos, escenarios, episodios, requisitos) existan. Si hay
  referencias colgadas o el subagente se salteo un paso, volve a invocarlo con el
  detalle del problema antes de continuar.

## Estructura `.dev/requirements/` resultante

```
.dev/requirements/
  sources/                      texto extraido del documento (entrada)
  source-inventory.json         inventario de secciones
  lel-candidates.json           candidatos a simbolos del LEL
  supporting-context.json       contexto de soporte
  lel.json / lel.md             Lexico Extendido del Lenguaje
  lel-inspection.json / .md     checklist de defectos del LEL
  stakeholder-questions.json/.md cuestionario para el stakeholder
  stakeholder-answers.md        respuestas del stakeholder (si las hubo)
  scenarios.json / scenarios.md Escenarios trazables al LEL
  requirements.json / .md       requisitos funcionales y no funcionales
  data-model.json / .md         modelo de datos (entidades y relaciones)
  technical-design.json / .md   arquitectura, API, pantallas y decisiones (ADRs)
  design-inspection.json / .md  inspeccion del diseno y normalizacion
```
