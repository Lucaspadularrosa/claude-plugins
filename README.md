# Claude Plugins — Requisitos y Planificación para agentes IA

Marketplace de plugins de Claude Code que cubre el ciclo completo: de la idea (con o
sin documentación) a un plan de ejecución donde varios agentes construyen features en
paralelo, con trazabilidad y auditoría de punta a punta.

**→ [Guía de uso completa](GUIA-DE-USO.md)** — instalación, flujos típicos, pausas y
cómo ejecutar el plan con agentes en paralelo.

## Plugins

| Plugin | Qué hace |
|---|---|
| `requirements-pipeline` | Pipeline iterativo de ingeniería de requisitos (método LEL y Escenarios de Leite, Hadad, Kaplan y Doorn). Descubre el mapa del producto desde documentos, carpetas o una entrevista sin documento; elabora y baselinea features por incrementos; absorbe cambios con confirmación y changelog. |
| `planning-pipeline` | Convierte la línea de base de requisitos en un plan de ejecución para agentes IA: tareas dimensionadas para una pasada de agente, lotes de features paralelas (ronda de contratos + lotes), inspección del plan y un brief por feature. `/replanificar` absorbe cambios de requisitos sin tocar lo construido. |
| `feature-pipeline` | Pipeline de build end-to-end independiente (spec → branch → código → tests → review → PR) para proyectos con requerimientos en `/features/`. |

## Instalación

```bash
/plugin marketplace add Lucaspadularrosa/claude-plugins
/plugin install requirements-pipeline@lpadularrosa-dev-plugins
/plugin install planning-pipeline@lpadularrosa-dev-plugins
```

Requisitos: Python 3.8+ (extracción de documentos); para PDF, `pip install pypdf`.

## El flujo en cuatro líneas

```
/requerimientos:descubrir docs/           # mapa del producto (docs, carpetas o nada)
/requerimientos:incremento FG-01 FG-02    # elaborar y baselinear el MVP
/planificar                               # tareas + lotes paralelos + briefs
/replanificar                             # cuando los requisitos cambien
```

Ver la [guía de uso](GUIA-DE-USO.md) para los flujos completos (arrancar sin
documento, material nuevo a mitad del build, cambios puntuales) y los README de cada
plugin para el detalle técnico.
