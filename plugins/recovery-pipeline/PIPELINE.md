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
        v  [code-inventory]
.dev/recovery/code-inventory.json     (stack, layout, modulos, entry points,
                                       señales de salud, contradicciones con la doc)
        |
        v  [behavior-extraction]           app chica: una pasada
        |                                  app grande: tandas PARALELAS por modulo
        |                                  (behavior-parts/tanda-NN.json, rangos de
        |                                  ids preasignados) + [behavior-merge]
.dev/recovery/behavior-map.json       (capacidades observables con su flujo, reglas,
                                       vocabulario, entidades; estado de implementacion
                                       complete|partial|skeleton|dead; evidencia
                                       archivo:linea)
        |
        v  [evidence-spot-check]
.dev/recovery/evidence-check.json     (verificacion adversarial por muestreo de la
                                       evidencia; lo refutado vuelve a
                                       behavior-extraction en modo correccion, una
                                       ronda)
        |
        v  [gap-analysis]
.dev/recovery/state-report.json/.md   (estado real por feature + huecos + señales
.dev/recovery/state-report.html        para auditoria; el .html es el reporte
.dev/recovery/owner-questions.md       compartible + cuestionario al dueño)
        |
        v  PAUSA con el dueño: responde en sesion o circula el cuestionario
        |  (respuestas -> owner-answers.md, el registro canonico)
        |
        v  OPT-IN: ¿reconstruir la linea de base?
        |     si -> [baseline-reconstruction] + entrada REC-xxx en changelog.json
        |           .dev/requirements/*  (mapa, LEL, escenarios, requisitos,
        |            data-model, diseno - formato estandar de la suite; lo completo
        |            baselined, lo parcial en stub)
        |           + [gap-analysis, update] (completa los FG-xx del reporte)
        |     no -> el diagnostico queda completo; se puede reconstruir despues
        |
        v  CIERRE: estado + proximos pasos
           (incrementos para completar, /auditar, /planificar, /construir)
```

---

## Agentes

| Agente | Rol | Definicion |
|---|---|---|
| `code-inventory` | Foto estructural por evidencia | `agents/code-inventory.md` |
| `behavior-extraction` | Que hace la app, observablemente | `agents/behavior-extraction.md` |
| `behavior-merge` | Consolida las tandas paralelas (solo apps grandes) | `agents/behavior-merge.md` |
| `evidence-spot-check` | Verificacion adversarial de evidencia por muestreo | `agents/evidence-spot-check.md` |
| `gap-analysis` | Estado real, huecos y cuestionario al dueño | `agents/gap-analysis.md` |
| `baseline-reconstruction` | Emite la linea de base en formato `.dev/requirements/` (opt-in) | `agents/baseline-reconstruction.md` |

La orquestacion vive en `skills/recovery-pipeline/SKILL.md`. El reporte compartible
lo genera `skills/recovery-pipeline/scripts/render_state_report.py` (determinista,
offline, sin dependencias).

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
