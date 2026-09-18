# Claude Plugins — Requisitos, Planificación y Build para agentes IA

Marketplace de plugins de Claude Code que cubre el ciclo completo de un sistema, con
dos puertas de entrada: **greenfield** (de la idea o los documentos a la app) y
**brownfield** (de una app existente — incluso vibe-codeada y sin documentación — a
una línea de base comprensible, auditable y extensible). En el medio: plan de
ejecución con features en paralelo, build agnóstico de stack y trazabilidad de punta
a punta.

**→ [Guía de uso completa](GUIA-DE-USO.md)** — instalación, flujos típicos, pausas y
cómo ejecutar el plan con agentes en paralelo.

## Plugins

| Plugin | Qué hace |
|---|---|
| `requerimientos` | Pipeline iterativo de ingeniería de requisitos (método LEL y Escenarios de Leite, Hadad, Kaplan y Doorn). Descubre el mapa del producto desde documentos, carpetas o una entrevista sin documento; elabora y baselinea features por incrementos; absorbe cambios con confirmación y changelog. |
| `planning-pipeline` | Convierte la línea de base de requisitos en un plan de ejecución para agentes IA: tareas dimensionadas para una pasada de agente, lotes de features paralelas (ronda de contratos + lotes), inspección del plan y un brief por feature. `/replanificar` absorbe cambios de requisitos sin tocar lo construido. |
| `build-pipeline` | Ejecuta el plan en cualquier lenguaje o framework: detecta el stack y su base de seguridad por evidencia, implementa cada feature en su rama con un **piso de seguridad OWASP por construcción**, verifica los criterios de aceptación y ese piso (un `security-gate` + audit de dependencias) antes de cada PR, construye lotes completos en paralelo (un agente por feature en worktrees), genera la **guía de usuario final** de cada feature (`.dev/manual/`, Markdown) y mantiene el progreso para la replanificación. |
| `manual-usuario` | Publica el manual de usuario que el build va escribiendo en `.dev/manual/` como un **sitio HTML estático navegable** en `docs/manual/` (offline, sin dependencias externas): una página por guía + índice, con render determinístico vía script. Lo único de la suite que sale de `.dev/`. |
| `recovery-pipeline` | Comprende una app ya desarrollada (aunque no tenga documentación): qué hace, en qué estado está, qué falta y qué hay que decidir. Reconstruye la línea de base de requisitos con evidencia `archivo:línea`, compatible con toda la suite. |
| `audit-pipeline` | Audita el codebase en tres dimensiones — bugs, seguridad defensiva y mejoras — con verificación adversarial de cada hallazgo antes de reportarlo. Los confirmados se convierten en change requests planificables. |
| `metrics-pipeline` | Cosecha las **métricas de proceso** de la suite sobre cualquier proyecto que la usó: un script determinista lee los artefactos que los pipelines ya dejaron (cero tokens, cero instrumentación, retroactivo) y un analista opcional dice qué mejorar. Con export a un JSONL central para comparar versiones del plugin entre proyectos. |

## Instalación

```bash
/plugin marketplace add Lucaspadularrosa/claude-plugins
/plugin install requerimientos@lpadularrosa-dev-plugins
/plugin install planning-pipeline@lpadularrosa-dev-plugins
/plugin install build-pipeline@lpadularrosa-dev-plugins
/plugin install manual-usuario@lpadularrosa-dev-plugins
/plugin install recovery-pipeline@lpadularrosa-dev-plugins
/plugin install audit-pipeline@lpadularrosa-dev-plugins
/plugin install metrics-pipeline@lpadularrosa-dev-plugins
```

Requisitos: Python 3.8+ (extracción de documentos); para PDF, `pip install pypdf`.

**Dependencia entre plugins**: `planning`, `build`, `recovery` y `audit` usan cuatro
ejecutables que provee `requerimientos` (`suite-pipeline-version`, `suite-stage-check`,
`suite-render-index` y `suite-render-baseline-docs`), que Claude Code pone en el `PATH` mientras ese plugin
esté instalado y habilitado. Sin él, esos pasos se saltean y quedan anotados; el resto
funciona igual. No se alcanzan por ruta relativa: en una instalación normal cada plugin
vive en `~/.claude/plugins/cache/<marketplace>/<nombre>/<versión>/` y una ruta relativa
entre plugins no resuelve.

## Los dos flujos

**Greenfield** — de la idea a la app:

```
/requerimientos:descubrir docs/           # mapa del producto (docs, carpetas o nada)
/requerimientos:incremento FG-01 FG-02    # elaborar y baselinear el MVP
/planificar                               # tareas + lotes paralelos + briefs
/construir-lote                           # construir el lote en paralelo (cualquier stack)
/replanificar                             # cuando los requisitos cambien
```

**Brownfield** — de la app existente (vibe-codeada, legacy) al control:

```
/comprender                               # qué es, qué hace, en qué estado está
/auditar                                  # bugs, seguridad y mejoras, verificados
/requerimientos:cambio "fix BUG-003..."   # convertir hallazgos en trabajo trazable
/requerimientos:incremento FG-07          # completar lo que estaba a medias
/planificar  +  /construir-lote           # y construir
```

Ver la [guía de uso](GUIA-DE-USO.md) para los flujos completos (arrancar sin
documento, material nuevo a mitad del build, cambios puntuales) y los README de cada
plugin para el detalle técnico.

## QA de la suite

- `python scripts/validate.py` — todo **carga** y todo **coincide**: marketplace,
  plugin.json y los frontmatters de agentes/comandos/skills (atrapa el YAML que
  des-registra un comando o le da todas las tools a un agente), más tres invariantes
  contra la deriva entre copias: los bloques obligatorios de cada agente, el modelo
  que declaran `SKILL.md` y `PIPELINE.md` contra el frontmatter, y los prefijos de id
  que prometen los prompts contra los que verifica `check-artifacts.py`. Corre en CI.
- `python scripts/check-version-bump.py` — todo **llega**: un plugin que cambia sube
  su versión. El caché se indexa por versión, así que un fix sin bump no le llega a
  quien ya tiene esa versión instalada. Corre en CI sobre cada PR.
- `python scripts/check-artifacts.py <proyecto>` — todo **cumple contrato**: verifica
  los artefactos `.dev/` que una corrida real generó (ids, enums, referencias
  cruzadas, cobertura de lotes).
- [`tests/golden/`](tests/golden/README.md) — todo **funciona**: el test dorado, una
  corrida completa de la suite sobre una visión fija, con checklist por etapa. Se
  corre a mano antes de mergear cambios de comportamiento en los prompts.
