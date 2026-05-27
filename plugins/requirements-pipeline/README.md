# Requirements Pipeline — Plugin de Claude Code

Plugin que convierte un documento de dominio (Word, PDF o Markdown) en una linea de base
de requisitos trazable: LEL, inspeccion, preguntas a stakeholders, escenarios, requisitos
funcionales y no funcionales, diseno tecnico e inspeccion del diseno. Aplica el metodo
**LEL y Escenarios** de Leite, Hadad, Kaplan y Doorn.

## Que tenes que poner en tu proyecto

**Nada.** Esa es la idea de empaquetarlo como plugin. El plugin se instala una vez y queda
disponible en todos tus proyectos. No copias carpetas `.claude/` a cada repo.

Lo unico que aparece en cada proyecto donde lo uses son las **salidas** que el pipeline
genera, en `.dev/requirements/`. El plugin en si vive fuera del proyecto.

## Estructura del plugin

```
requirements-pipeline/
  .claude-plugin/
    plugin.json                  manifiesto del plugin
  agents/                        los 8 subagentes del pipeline
    requirements-intake.md
    lel-authoring.md
    lel-inspection.md
    stakeholder-questionnaire.md
    scenario-modeling.md
    requirements-specification.md
    technical-design.md
    design-inspection.md
  skills/
    requirements-pipeline/
      SKILL.md                   orquestacion del pipeline
      scripts/
        extract_document.py      extrae texto de .docx / .pdf / .md / .txt
  commands/
    requerimientos.md            slash command de entrada
  PIPELINE.md                    diagrama y reglas del flujo
  README.md                      este archivo
```

## Instalacion

Este plugin se distribuye en el marketplace `plugins-claude`. Con el marketplace agregado:

```bash
claude plugin install requirements-pipeline@plugins-claude
```

Por defecto el plugin queda disponible de forma global (en todos los proyectos). Para
acotarlo a un proyecto, instalalo con `--scope project`. Despues de instalar, si hace
falta, recarga con `/reload-plugins`.

Los comandos exactos del CLI pueden variar segun la version de Claude Code: verificalos
con `/plugin` o `claude plugin --help`.

## Requisitos

- **Claude Code** con soporte de plugins, subagentes y skills.
- **Python 3.8+** para el script de extraccion.
- Para leer **PDF**: `pip install pypdf` (o `pdfminer.six`). Word (`.docx`), Markdown y
  texto plano no necesitan dependencias.

## Uso

En cualquier proyecto, con el plugin instalado:

```
/requerimientos docs/especificacion.docx
```

O en lenguaje natural (la skill se activa sola):

```
Genera los requisitos a partir de este documento: docs/especificacion.pdf
```

El pipeline corre las 8 etapas y tiene tres puntos de interaccion: una **pausa** para que
respondas el cuestionario al stakeholder, una **consulta** sobre si hay mockups de UI
antes del diseno, y un **lazo de correccion** del diseno. Todo se escribe en
`.dev/requirements/` del proyecto.

## Etapas

```
documento -> intake -> LEL -> inspeccion -> preguntas -> [PAUSA] ->
escenarios -> requisitos -> diseno -> inspeccion de diseno
```

| # | Subagente | Produce |
|---|---|---|
| 1 | `requirements-intake` | inventario, candidatos LEL, contexto de soporte |
| 2 | `lel-authoring` | Lexico Extendido del Lenguaje |
| 3 | `lel-inspection` | checklist de defectos del LEL |
| 4 | `stakeholder-questionnaire` | preguntas para el stakeholder |
| 5 | `scenario-modeling` | escenarios trazables al LEL |
| 6 | `requirements-specification` | requisitos funcionales y no funcionales |
| 7 | `technical-design` | modelo de datos y diseno tecnico |
| 8 | `design-inspection` | inspeccion del diseno y normalizacion |

Ver `PIPELINE.md` para el diagrama completo y las reglas de orquestacion.

## Salidas (en `.dev/requirements/` del proyecto)

| Archivo | Contenido |
|---|---|
| `source-inventory.json` | Inventario de secciones del documento |
| `lel-candidates.json` | Candidatos a simbolos del LEL |
| `supporting-context.json` | Contexto de soporte (modelo de datos, API, UI, stack) |
| `lel.json` / `lel.md` | Lexico Extendido del Lenguaje |
| `lel-inspection.json` / `.md` | Checklist de defectos del LEL |
| `stakeholder-questions.json` / `.md` | Cuestionario para el stakeholder |
| `scenarios.json` / `scenarios.md` | Escenarios trazables al LEL |
| `requirements.json` / `requirements.md` | Requisitos funcionales y no funcionales |
| `data-model.json` / `data-model.md` | Modelo de datos: entidades, campos y relaciones |
| `technical-design.json` / `technical-design.md` | Arquitectura, API, pantallas y decisiones (ADRs) |
| `design-inspection.json` / `design-inspection.md` | Inspeccion del diseno y normalizacion |
