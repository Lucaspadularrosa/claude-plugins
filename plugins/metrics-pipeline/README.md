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
- **Señales** (`signals` en el JSON): la tabla de umbrales de la suite (metrica ->
  umbral -> pipeline sospechoso) la aplica el script, no el modelo. El resumen, la
  muestra y las señales disparadas salen por stdout: el orquestador nunca abre el
  JSON.
- **Analisis** (`metrics-analyst`, haiku): agente opcional y explicito. Lee SOLO el
  `metrics.json` ya digerido y redacta `analysis.md`: prioriza las señales
  disparadas, propone la correccion concreta en la suite, con honestidad sobre el
  tamaño de la muestra.
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

## Piezas

| Pieza | Que hace | Tokens |
|---|---|---|
| `scripts/metrics_harvest.py` | Cosecha `.dev/*` + git -> `metrics.json` + `.html`; imprime resumen y señales | Cero |
| `metrics-analyst` (agente, haiku) | Lee SOLO `metrics.json` y escribe `analysis.md` | Acotado, a demanda |
| `--export` del script | Apendea el registro compacto al JSONL central | Cero |

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
  agents/metrics-analyst.md      diagnostico sobre el metrics.json (opt-in, haiku)
  skills/metrics-pipeline/
    SKILL.md
    scripts/metrics_harvest.py   la cosecha determinista (cero tokens; --self-test)
  commands/metricas.md
  README.md
```

## Relacion con los otros plugins

Los lee a todos y no toca a ninguno: ni un paso ni un token agregado a sus flujos.
Si un diagnostico requiere que un artefacto guarde algo que hoy no guarda (p. ej. un
historial de rondas), eso se propone como cambio de contrato al mantenedor — decision
explicita, nunca instrumentacion silenciosa.

## Cambios

- **1.1.0**: el script imprime siempre el resumen, la muestra y las señales por
  stdout (el modo `solo-datos` ya no requiere abrir el JSON); umbrales precalculados
  en `signals`; analista en haiku, solo redaccion y priorizacion.
