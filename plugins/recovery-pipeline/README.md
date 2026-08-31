# Recovery Pipeline — Plugin de Claude Code

Plugin que **comprende una aplicacion ya desarrollada** — aunque no tenga
documentacion — y, si queres, la incorpora a la suite de requisitos/planificacion/
build. Pensado para el caso vibe-coding: alguien tuvo una idea, la prompteo, y hoy
tiene un codebase que funciona (en parte) pero nadie sabe con precision que hace, que
falta, ni que decisiones se tomaron en el camino.

## Que te da `/comprender`

Primero, **el diagnostico** (siempre, sin comprometerte con nada):

1. **Que es esta app**: stack, estructura, modulos, puntos de entrada, señales de
   salud — todo por evidencia del codigo (la doc, si existe, se contrasta: el codigo
   manda).
2. **Que hace**: las capacidades observables con sus flujos, reglas de negocio,
   vocabulario y entidades, cada una con evidencia `archivo:linea` y su estado real:
   completa, a medias, esqueleto o muerta. En apps grandes la extraccion corre en
   **tandas paralelas** y se consolida. Una muestra de la evidencia pasa por un
   **spot-check adversarial** (se intenta refutar leyendo el codigo citado) antes de
   que nada se apoye en ella.
3. **El estado honesto y las preguntas**: un reporte de estado por feature (que falta
   exactamente) — en Markdown y en un **HTML compartible**, autocontenido y offline,
   para mandarselo a un socio o stakeholder — y un cuestionario para el dueño
   redactado sin tecnicismos ("la pantalla de reportes existe pero no muestra datos:
   ¿la terminamos, la sacamos, o era de otra idea?"). Lo respondes en el momento o lo
   circulas y traes las respuestas despues.

Despues, **la linea de base** (opt-in): si queres completar lo que esta a medias,
planificar, construir o auditar con trazabilidad, el pipeline reconstruye mapa del
producto, LEL, escenarios, requisitos, modelo de datos y diseno tecnico en
`.dev/requirements/` — **el mismo formato que produce `requerimientos`**, con la
trazabilidad apuntando al codigo. Lo que el codigo demuestra completo queda
baselineado; lo incompleto queda en stub.

## Por que importa el formato

Porque despues de reconstruir, **todo lo demas ya funciona**:

```
/comprender                          diagnostico + (opt-in) la app entra a la suite
/requerimientos:incremento FG-07     completar lo que estaba a medias
/planificar  +  /construir-lote      planificar y construir lo nuevo
/auditar                             bugs, seguridad y mejoras sobre lo que hay
/requerimientos:cambio               cambios sobre lo reconstruido
```

La cadena de trazabilidad queda completa en ambas direcciones: requisito → escenario
→ simbolo del LEL → `archivo:linea`; y cada corrida que reconstruye linea de base
queda registrada en el changelog (`REC-xxx`).

## Uso

```
/comprender                  (el proyecto actual)
/comprender ruta/al/repo
```

El pipeline es de **solo lectura** sobre tu codigo: no modifica un solo archivo
fuente. Escribe en `.dev/recovery/` (inventario, mapa de comportamiento, spot-check,
reporte de estado, cuestionario) y — solo si optaste por la linea de base —
`.dev/requirements/`.

Tiene una pausa: el cuestionario del dueño. Responderlo afina la comprension y la
reconstruccion (features que se confirman, se recortan o se descartan); tambien podes
responderlo mas tarde y re-correr `/comprender`.

## Estructura del plugin

```
recovery-pipeline/
  .claude-plugin/plugin.json
  agents/
    code-inventory.md          completa el esqueleto del inventario (haiku, solo lo semantico)
    behavior-extraction.md     que hace la app, con archivo:linea (nucleo compartido,
                               pasada unica, tandas paralelas o modo correccion)
    behavior-merge.md          consolida las tandas paralelas (solo apps grandes)
    evidence-spot-check.md     verificacion adversarial de la muestra (haiku)
    gap-analysis.md            estado real + huecos + cuestionario, sobre la tajada
    baseline-reconstruction.md linea de base en tres pasadas por modo (sonnet/opus/sonnet)
  skills/recovery-pipeline/
    SKILL.md
    scripts/scan_repo.py               repo -> esqueleto del inventario (entry points exactos)
    scripts/sample_capabilities.py     behavior-map -> muestra determinista del spot-check
    scripts/slice_behavior_map.py      behavior-map -> proyeccion para gap-analysis
    scripts/render_recovery_docs.py    los JSON -> code-inventory/behavior-map/state-report/owner-questions .md
    scripts/render_state_report.py     state-report.json -> HTML compartible
    scripts/validate_baseline_refs.py  referencias cruzadas de la linea de base (exit code)
    scripts/backfill_feature_ids.py    completa los FG-xx del state-report por cruce de CAP
  commands/comprender.md
  PIPELINE.md
  README.md
```

## Economia de tokens

- Lo que es globs, greps y `git log` lo hace `scan_repo.py`; el agente de
  inventario (haiku) solo rellena lo semantico.
- Los agentes escriben **solo JSON**; los `.md` los regeneran los scripts. Nada del
  diagnostico se emite dos veces por modelo.
- El spot-check recibe la muestra ya cortada (<= 13 capacidades) y `gap-analysis`
  una proyeccion sin flujos: nadie relee el behavior-map entero salvo la
  reconstruccion.
- En apps grandes, una pasada barata deriva el nucleo compartido (entidades,
  vocabulario, guards) y las tandas lo citan en vez de re-derivarlo N veces.
- Modelo por modo: opus solo para descubrir y juzgar; correccion con diagnostico
  hecho y mapeo de campos en sonnet; verificacion sobre tajada en haiku.
- La linea de base se valida y se engancha al reporte por script (exit code), sin
  re-invocar agentes completos.

## Relacion con los otros plugins

- `requerimientos`: produce el mismo tipo de linea de base desde documentos;
  este la produce desde codigo. Conviven: una app comprendida puede seguir creciendo
  con `:descubrir` / `:incremento` / `:cambio`.
- `audit-pipeline`: la comprension releva *señales* (algo huele mal aca) y las deja en
  el state-report; la auditoria las investiga a fondo con verificacion adversarial.
- `planning-pipeline` / `build-pipeline`: consumen lo baselineado, venga de documentos
  o de codigo.

Ver `PIPELINE.md` para el diagrama y las reglas.
