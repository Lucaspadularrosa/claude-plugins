# Pipeline: Comprension (recovery de apps existentes)

El camino inverso de `requirements-pipeline`: del **codigo** hacia una linea de base
de requisitos formal. Para apps con documentacion baja o nula (vibe-coding, legacy,
prototipos que crecieron).

---

## Flujo

```
codigo de la aplicacion          <- ENTRADA (no se modifica nada)
        |
        v  [code-inventory]
.dev/recovery/code-inventory.json     (stack, layout, modulos, entry points,
                                       señales de salud, contradicciones con la doc)
        |
        v  [behavior-extraction]
.dev/recovery/behavior-map.json       (capacidades observables con su flujo, reglas,
                                       vocabulario, entidades; estado de implementacion
                                       complete|partial|skeleton|dead; evidencia
                                       archivo:linea)
        |
        v  [baseline-reconstruction]   + entrada REC-xxx en changelog.json
.dev/requirements/*                   (mapa del producto, LEL, escenarios, requisitos,
                                       data-model, diseno tecnico - formato estandar
                                       de la suite, evidencia apuntando al codigo;
                                       lo completo queda baselined, lo parcial en stub)
        |
        v  [gap-analysis]
.dev/recovery/state-report.json/.md   (estado real por feature + huecos + señales
.dev/recovery/owner-questions.md       para auditoria + cuestionario al dueño)
        |
        v  PAUSA con el dueño -> respuestas -> [baseline-reconstruction, update]
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
| `baseline-reconstruction` | Emite la linea de base en formato `.dev/requirements/` | `agents/baseline-reconstruction.md` |
| `gap-analysis` | Estado real, huecos y cuestionario al dueño | `agents/gap-analysis.md` |

La orquestacion vive en `skills/recovery-pipeline/SKILL.md`.

---

## Reglas clave

- **Solo lectura sobre el codigo**: las unicas escrituras son `.dev/recovery/` y
  `.dev/requirements/`.
- **Nada sin evidencia**: todo lo reconstruido cita archivo:linea; lo dudoso es
  pregunta abierta, no afirmacion. Comportamiento observable, no intencion.
- **Compatible con la suite**: la linea de base reconstruida es indistinguible en
  forma de una nacida de documentos; los pipelines de requisitos, planificacion y
  build la consumen sin adaptacion. La corrida queda en el changelog como `REC-xxx`
  (kind `recovery`).
- **Estados honestos**: el codigo completo queda `baselined`; lo parcial queda `stub`
  con lo que falta documentado — listo para elaborarse como incremento.
- La PAUSA con el dueño nunca se saltea ni se inventan respuestas.

---

## Como iniciar

```
/comprender               (el proyecto actual)
/comprender ruta/al/repo
```

O en lenguaje natural ("entende esta aplicacion", "¿en que estado esta esta app?").
