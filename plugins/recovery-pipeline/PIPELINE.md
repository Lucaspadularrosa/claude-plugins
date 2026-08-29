# Pipeline: Comprension (recovery de apps existentes)

El camino inverso de `requerimientos`: del **codigo** hacia la comprension formal.
Para apps con documentacion baja o nula (vibe-coding, legacy, prototipos que
crecieron). Entrega en dos tiempos: primero el **diagnostico** (siempre), despues la
**linea de base** (opt-in).

---

## Flujo

```
codigo de la aplicacion          <- ENTRADA (no se modifica nada)
        |
        v  [scan_repo.py]  (script: stack, layout, entry points EXACTOS, salud, git)
        v  [code-inventory] (haiku: rellena solo lo semantico)
.dev/recovery/code-inventory.json     (+ .md por script)
        |
        v  [behavior-extraction]           <= 15 entry points: una pasada (opus)
        |                                  > 15: nucleo compartido (sonnet,
        |                                  shared-core.json) + tandas PARALELAS por
        |                                  modulo que lo citan + [behavior-merge]
.dev/recovery/behavior-map.json       (capacidades con flujo, reglas, vocabulario,
                                       entidades; estado complete|partial|skeleton|
                                       dead; evidencia archivo:linea; .md por script)
        |
        v  [sample_capabilities.py] (script: <= 13 capacidades)
        v  [evidence-spot-check] (haiku, sobre la muestra)
.dev/recovery/evidence-check.json     (lo refutado vuelve a behavior-extraction en
                                       modo correccion con sonnet, una ronda; no se
                                       re-verifica: gap-analysis aplica "evidencia
                                       refutada manda")
        |
        v  [slice_behavior_map.py] (script: proyeccion sin flujos)
        v  [gap-analysis] (sonnet, sobre la tajada)
        v  [render_recovery_docs.py + render_state_report.py]
.dev/recovery/state-report.json/.md   (estado real por feature + huecos + señales
.dev/recovery/state-report.html        para auditoria; el .html es el reporte
.dev/recovery/owner-questions.json/.md compartible + cuestionario al dueño)
        |
        v  PAUSA con el dueño: responde en sesion o circula el cuestionario
        |  (respuestas -> owner-answers.md, el registro canonico)
        |
        v  OPT-IN: ¿reconstruir la linea de base?
        |     si -> [baseline-reconstruction] en PARALELO por modo:
        |             mecanica (sonnet): lel + data-model
        |             juicio (opus): product-map + scenarios + requirements
        |           despues cierre (sonnet): technical-design
        |           + entrada REC-xxx en changelog.json
        |           + [validate_baseline_refs.py] (referencias cruzadas, exit code)
        |           + [backfill_feature_ids.py] (FG-xx del reporte por cruce de CAP;
        |             gap-analysis solo si hubo grupos partidos/unidos)
        |     no -> el diagnostico queda completo; se puede reconstruir despues
        |
        v  CIERRE: estado + proximos pasos
           (incrementos para completar, /auditar, /planificar, /construir)
```

---

## Agentes

| Agente | Rol | Definicion |
|---|---|---|
| `code-inventory` (haiku) | Completa el esqueleto de `scan_repo.py` con lo semantico | `agents/code-inventory.md` |
| `behavior-extraction` (opus; sonnet en nucleo y correccion) | Que hace la app, observablemente | `agents/behavior-extraction.md` |
| `behavior-merge` (sonnet) | Consolida las tandas paralelas (solo apps grandes) | `agents/behavior-merge.md` |
| `evidence-spot-check` (haiku) | Verificacion adversarial de la muestra | `agents/evidence-spot-check.md` |
| `gap-analysis` (sonnet) | Estado real, huecos y cuestionario, sobre la tajada | `agents/gap-analysis.md` |
| `baseline-reconstruction` (sonnet/opus/sonnet por modo) | Emite la linea de base en `.dev/requirements/` (opt-in) | `agents/baseline-reconstruction.md` |

La orquestacion vive en `skills/recovery-pipeline/SKILL.md`. Los scripts
deterministas (esqueleto del inventario, muestra, tajada, renders, validacion y
backfill) viven en `skills/recovery-pipeline/scripts/`; ningun agente escribe `.md`.

---

## Reglas clave

- **Solo lectura sobre el codigo**: las unicas escrituras son `.dev/recovery/` y
  `.dev/requirements/`.
- **Nada sin evidencia**: todo lo reconstruido cita archivo:linea; lo dudoso es
  pregunta abierta, no afirmacion. Comportamiento observable, no intencion. El
  spot-check verifica una muestra de esa evidencia antes de que nada se apoye en
  ella.
- **Diagnostico primero, linea de base opt-in**: el usuario recibe el estado real de
  su app sin comprometerse con la suite; `.dev/requirements/` solo se escribe si lo
  pide (o si ya existia y hay que actualizarla).
- **Compatible con la suite**: la linea de base reconstruida es indistinguible en
  forma de una nacida de documentos; los pipelines de requisitos, planificacion y
  build la consumen sin adaptacion. La corrida queda en el changelog como `REC-xxx`
  (kind `recovery`).
- **Estados honestos**: el codigo completo queda `baselined`; lo parcial queda `stub`
  con lo que falta documentado — listo para elaborarse como incremento.
- La PAUSA con el dueño nunca se saltea ni se inventan respuestas; el cuestionario es
  un entregable circulante (los stakeholders pueden responder dias despues).

---

## Como iniciar

```
/comprender               (el proyecto actual)
/comprender ruta/al/repo
```

O en lenguaje natural ("entende esta aplicacion", "¿en que estado esta esta app?").
