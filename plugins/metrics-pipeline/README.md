# Metrics Pipeline — Plugin de Claude Code

Plugin que mide **como esta funcionando la suite** (requisitos, planificacion, build,
recovery, audit) sobre un proyecto real, para corregir los pipelines con datos y no
con intuicion. Su principio de diseño: **telemetria cero**.

## Por que telemetria cero

Instrumentar los flujos cobraria un peaje de tokens en cada corrida, pagado por quien
usa la suite, para un beneficio del mantenedor. No hace falta: todos los artefactos
de la suite ya llevan `summary` y `pipeline_version` — **los artefactos son el log de
eventos**. Este plugin los cosecha a demanda:

- **Cosecha** (`metrics_harvest.py`): script determinista, solo stdlib, cero tokens.
  Lee `.dev/requirements/` (baseline, inspecciones, changelog y churn de la
  baseline), `.dev/plan/`, `.dev/build/` (reviews y gates por feature),
  `.dev/recovery/` (tasa de refutados del spot-check), `.dev/audit/` y el git log
  (commits `[T-xxx]`). Emite `.dev/metrics/metrics.json` + `metrics.html`
  (autocontenido, offline). Retroactivo: funciona sobre cualquier proyecto que ya
  uso la suite, sin re-correr nada.
- **Analisis** (`metrics-analyst`): agente dedicado, opcional y explicito. Lee SOLO
  el `metrics.json` ya digerido (nunca los artefactos crudos ni el codigo) y escribe
  `analysis.md`: que señal apunta a que pipeline, que corregir, con honestidad sobre
  el tamaño de la muestra.
- **Export** (`--export ruta.jsonl`): apendea el registro compacto del proyecto a un
  JSONL central tuyo, fuera de los repos. Con varios proyectos acumulados, compara
  versiones del plugin: "¿bajo la tasa de refutados con recovery 2.0?".

## Las metricas que importan (de friccion, no de volumen)

| Metrica | Señal sobre |
|---|---|
| Tasa refutados del evidence-check (recovery) | Calidad de extraccion de comportamiento |
| Hallazgos y rondas por feature en reviews (build) | Calidad de briefs e implementer |
| Hallazgos del gate de seguridad por feature | Si la base de seguridad llega al implementer |
| Señal/ruido del audit (confirmados vs propuestos) | Ruido de las dimensiones de auditoria |
| Churn de la baseline (CRs sobre lo baselineado, y a cuantos dias) | Si se baselinea antes de tiempo |
| Defectos por tipo en las inspecciones | Reglas que faltan en los prompts autores |

## Uso

```
/metricas                        cosecha + analisis
/metricas solo-datos             solo la cosecha (cero tokens de modelo)
/metricas export                 ademas apendea al JSONL central
/metricas ruta/al/proyecto       sobre otro proyecto
```

## Estructura del plugin

```
metrics-pipeline/
  .claude-plugin/plugin.json
  agents/metrics-analyst.md      diagnostico sobre el metrics.json (opt-in)
  skills/metrics-pipeline/
    SKILL.md
    scripts/metrics_harvest.py   la cosecha determinista (cero tokens)
  commands/metricas.md
  README.md
```

## Relacion con los otros plugins

Los lee a todos y no toca a ninguno: ni un paso ni un token agregado a sus flujos.
Si un diagnostico requiere que un artefacto guarde algo que hoy no guarda (p. ej. un
historial de rondas), eso se propone como cambio de contrato al mantenedor — decision
explicita, nunca instrumentacion silenciosa.
