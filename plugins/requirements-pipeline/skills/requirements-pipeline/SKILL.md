---
name: requirements-pipeline
description: Pipeline iterativo de ingenieria de requisitos con el metodo LEL y Escenarios. Descubre el mapa del producto desde documentos, carpetas o una entrevista sin documento; elabora y baselinea features por incrementos; y absorbe cambios sobre lo ya baselineado, todo trazable y auditable. Usar cuando el usuario quiere generar requisitos desde documentacion o una vision, agregar material nuevo, o profundizar features para planificar y construir.
---

# Pipeline de Ingenieria de Requisitos (LEL y Escenarios, iterativo)

Esta skill convierte material de dominio en una linea de base de requisitos trazable,
aplicando el metodo LEL y Escenarios de Leite, Hadad, Kaplan y Doorn — pero de forma
**iterativa e incremental**, no en cascada: la linea de base de Leite es una estructura
que evoluciona, y este pipeline la hace evolucionar por rebanadas.

El principio: **amplitud temprana y barata, profundidad recien cuando hace falta.**
Primero se descubre el mapa completo del producto (features y escenarios stub); despues
se elaboran y baselinean solo las features elegidas, incremento por incremento; el
material nuevo que llega despues (documentos, charlas) entra al mismo circuito sin
romper nada de lo construido.

Vos, el agente principal, sos el orquestador: ejecutas la extraccion, delegas cada
etapa al subagente correspondiente con la herramienta Task, mantenes el changelog y
manejas las pausas con el usuario.

## Subagentes (en `agents/` del plugin)

| Subagente | Rol | Participa en |
|---|---|---|
| `requirements-intake` | Clasifica el material en inventario, candidatos LEL y contexto | descubrir, cambio |
| `lel-authoring` | Construye o actualiza el LEL | descubrir, cambio |
| `lel-inspection` | Checklist de defectos del LEL | descubrir, cambio |
| `stakeholder-questionnaire` | Preguntas al stakeholder; en descubrimiento, elicitacion | descubrir, cambio |
| `product-mapping` | Mapa del producto: features y escenarios stub priorizados | descubrir |
| `scenario-modeling` | Elabora en profundidad los escenarios de las features del incremento | incremento |
| `requirements-specification` | Especifica los requisitos de las features del incremento | incremento, cambio |
| `requirements-inspection` | Audita la especificacion (cobertura de lo elaborado) | incremento, cambio |
| `technical-design` | Extiende el modelo de datos y el diseno con lo que el incremento necesita | incremento, cambio |
| `design-inspection` | Audita el diseno y la normalizacion | incremento, cambio |

Todos los archivos se generan en `.dev/requirements/` del proyecto actual.

## Artefactos de control

Ademas de los artefactos del metodo (LEL, escenarios, requisitos, diseno), el pipeline
mantiene dos artefactos de control. **Los escribis vos, el orquestador**, no los
subagentes:

### `product-map.json` (lo escribe `product-mapping`; vos actualizas los estados)

El backlog: features `FG-xx` y escenarios `SCN-xx` con `status`
`stub -> elaborated -> baselined` (o `deprecated`). Los ids nacen en el mapa y son
estables para siempre. Al cerrar un incremento, actualizas los estados de las features
elaboradas.

### `changelog.json` (lo escribis vos)

La historia de la linea de base. Una entrada por corrida:

```json
{
  "version": 1,
  "entries": [
    {
      "id": "DSC-001 | INC-001 | CR-001 | REC-001",
      "kind": "discovery|increment|change_request|recovery",
      "date": "YYYY-MM-DD",
      "status": "in_progress|applied|rejected",
      "sources": ["sources/vision.txt"],
      "feature_ids": ["FG-01"],
      "verdicts": [
        {"kind": "new|modified|deprecated|already_covered", "target_kind": "requirement|scenario|feature|symbol|entity", "target_id": "RF-007", "covered_by": "RF-012", "confirmed_by_user": true, "resolution": "applied|rejected"}
      ],
      "artifact_versions": {"lel.json": {"before": "2", "after": "3"}},
      "notes": "string"
    }
  ]
}
```

Ids consecutivos por tipo: `DSC-001` descubrimientos, `INC-001` incrementos, `CR-001`
cambios, `REC-001` recuperaciones (las escribe `recovery-pipeline` cuando reconstruye
la linea de base desde codigo existente). Registra la entrada con
`status: in_progress` al arrancar la corrida y cerrala (`applied` o `rejected`) al
terminar, con las versiones antes/despues de cada artefacto tocado. En los
`verdicts`, `resolution` registra si ese cambio confirmado quedo `applied` o
`rejected` (el rechazo tambien se conserva); `target_kind: feature` cubre tanto las
features del mapa como los `feature_group` de la especificacion (son el mismo
objeto). El changelog es lo
que le permite al pipeline de planificacion saber **que** cambio, no solo que algo
cambio.

## Entradas soportadas

El material de dominio puede llegar como:

- **Uno o varios archivos**: `.docx`, `.pdf`, `.md`, `.txt`.
- **Una o varias carpetas**: usa Glob para listar dentro de cada carpeta (recursivo)
  todos los archivos de esos tipos y procesalos todos. Informa cuales encontraste y
  cuales extensiones ignoraste.
- **Sin documento**: el usuario arranca solo con una vision conversada. Pedile que la
  cuente (que problema resuelve, para quien, que se imagina), guarda ese texto como
  fuente y segui el flujo normal. En este caso el cuestionario de elicitacion va a ser
  **mas largo** — es esperable y deseable: las respuestas son la fuente.

Extraccion: para cada archivo, crea `.dev/requirements/sources/` y corre:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/requirements-pipeline/scripts/extract_document.py" \
  "<ruta-del-archivo>" ".dev/requirements/sources/<nombre>.txt"
```

Si `python3` no existe (tipico en Windows), proba `python` y despues `py -3`. Si
`${CLAUDE_PLUGIN_ROOT}` no estuviera definida, ubica `extract_document.py` en la
subcarpeta `scripts/` de esta skill. Para PDF puede hacer falta `pip install pypdf`.
Si la extraccion de un archivo falla (dependencia ausente, archivo ilegible), informa
el error y pregunta al usuario si continuar sin ese archivo o resolverlo primero;
nunca sigas en silencio con una fuente a medias.
La vision sin documento y las respuestas de entrevistas se guardan tambien en
`sources/` (`vision-001.txt`, `entrevista-001.txt`): toda fuente queda archivada.

---

## Modo DESCUBRIR (`/requerimientos:descubrir [rutas...]`)

Cuando: al arrancar el proyecto, y **cada vez que llega material nuevo** (documentos,
charlas con funcionalidades nuevas). Es siempre seguro: solo agrega al mapa y enriquece
el vocabulario; nunca modifica lo baselineado (eso queda como propuesta).

1. Registra `DSC-xxx` en el changelog (`in_progress`). Resolve y extrae las entradas
   (archivos, carpetas o vision conversada).
2. Invoca `requirements-intake`: pasale **todas** las rutas de texto extraido. En
   re-descubrimiento, indicale que es modo incremental (lee lo previo, continua ids,
   marca candidatos que coinciden con simbolos existentes).
3. Invoca `lel-authoring` (modo actualizacion si ya hay LEL) y luego `lel-inspection`.
4. Invoca `stakeholder-questionnaire` en **modo elicitacion**: ademas de los defectos
   del LEL, genera preguntas para completar el dominio. Cuanto menos material, mas
   preguntas (sin documento: entrevista completa).
5. **PAUSA OBLIGATORIA**: presenta `stakeholder-questions.md` al usuario y espera.
   - Si responde: guarda las respuestas en `.dev/requirements/stakeholder-answers.md`
     (una respuesta por `QST-xxx`) y archiva una copia en `sources/`
     (`entrevista-NNN.txt`): las respuestas son una fuente mas. Aplicalas SIEMPRE al
     LEL con `lel-authoring` (update) y reinspecciona; si ademas traen dominio nuevo
     sustancial (tipico sin documento), pasalas antes por `requirements-intake`
     incremental. Si el dominio sigue fino, podes ofrecer otra ronda de preguntas;
     no fuerces mas de dos rondas seguidas sin avanzar al mapa.
   - Si dice que no hay dudas: segui.
   - Nunca inventes respuestas.
6. Invoca `product-mapping`: construye o actualiza `product-map.json` (features y stubs
   nuevos; solapamientos con lo baselineado como `pending_proposals`).
7. Si hay `pending_proposals`, mostraselas al usuario: las acepta (quedan para resolver
   en un `/requerimientos:cambio` o en el proximo incremento) o las rechaza.
8. Cierra la entrada `DSC-xxx` (versiones de artefactos, features descubiertas).
   Mostrale al usuario el mapa (`product-map.md`) y sugerile el proximo paso:
   `/requerimientos:incremento <features prioritarias>`.

## Modo INCREMENTO (`/requerimientos:incremento <FG-xx ...>`)

Cuando: el usuario decide que features elaborar y baselinear. La unidad del incremento
es la **feature** (calza con los lotes, briefs y ramas del pipeline de planificacion).
Si el usuario nombra features en lenguaje natural, resolvelas contra el mapa; si una no
existe o esta `deprecated`, frena y aclaralo.

1. Registra `INC-xxx` (`in_progress`) con las `feature_ids`.
2. Invoca `scenario-modeling` en modo profundizacion: indicale las features y que lea
   `product-map.json`. Elabora **solo** los escenarios stub de esas features,
   conservando sus `SCN-xx`; los escenarios nuevos que descubra usan ids que continuan
   y los reporta para que los sumes al mapa.
3. Invoca `requirements-specification` en modo incremento: deriva requisitos solo de
   esas features, conservando los `FG-xx` del mapa. `requirements.json` es acumulativo:
   lo de incrementos anteriores se preserva intacto. Si la elaboracion implica
   **modificar o deprecar algo baselineado**, el agente NO lo aplica: lo reporta en
   `proposed_baseline_changes`. Al cerrar esta etapa, marca en `product-map.json` las
   features del incremento y sus escenarios como `elaborated`: la inspeccion
   (REQ-CHECK-012) valida contra ese estado.
4. **PAUSA DE CONFIRMACION** (solo si hay `proposed_baseline_changes` — `PBC-xxx` de
   la especificacion — o `pending_proposals` — `PROP-xxx` del mapa — aceptadas que
   tocan esto; son la misma pausa): mostra el antes/despues de cada
   cambio propuesto sobre lo baselineado y espera el OK del usuario por cada uno. Los
   confirmados se aplican re-invocando al agente que corresponda con la lista exacta;
   los rechazados quedan `rejected` en el changelog. Lo nuevo no requiere confirmacion.
5. Invoca `requirements-inspection` (audita todo lo elaborado, no solo este
   incremento). Lazo de correccion: defectos `high`/`medium` rebotan a
   `requirements-specification` (modo correccion) y se reinspecciona, con tope de
   **3 pasadas**: si no pasa, presenta los defectos remanentes al usuario y decidi
   con el (aceptar anotado, corregir a mano, abortar).
6. Diseño tecnico, SIEMPRE — tambien si el incremento no tiene pantallas: el modelo
   de datos y el diseño son precondicion de `/planificar`.
   - Solo si alguna feature del incremento tiene pantallas: pregunta antes al usuario
     si hay mockups de UI (HTML, CSS, wireframes, capturas) para ellas.
   - Invoca `technical-design` en modo incremental (extiende modelo de datos y diseno
     solo con lo que estas features necesitan, preservando ids y decisiones previas)
     y despues `design-inspection`, con su lazo de correccion (mismo tope de 3
     pasadas).
7. Cierra: marca las features y escenarios del incremento como `baselined` en
   `product-map.json`, cierra la entrada `INC-xxx` (`applied`, con verdicts y
   versiones). Informa el resumen y sugeri el paso siguiente: `/planificar` (primera
   vez) o re-planificar (si ya hay plan, el pipeline de planificacion detecta los
   incrementos no absorbidos via changelog).

## Modo CAMBIO (`/requerimientos:cambio <descripcion-o-ruta>`)

Cuando: un cambio puntual sobre lo ya baselineado, sin material grande de por medio
("el login ahora necesita 2FA", un mail del stakeholder, un documento corto que
modifica algo existente).

1. Registra `CR-xxx` (`in_progress`). Guarda la fuente (texto del usuario o documento
   extraido) en `sources/cr/`.
2. Analiza el alcance leyendo lo existente (LEL, mapa, requisitos): para cada pedido
   del CR determina el veredicto: `new` (no existia: va al mapa o directo al
   incremento), `modified` (toca algo baselineado), `deprecated` (elimina algo) o
   `already_covered` (ya estaba cubierto; el CR queda respondido sin tocar nada).
   Si el alcance amerita vocabulario nuevo, corre `requirements-intake` +
   `lel-authoring` (update) + `lel-inspection` sobre la fuente del CR.
3. **PAUSA DE CONFIRMACION**: presenta los veredictos con antes/despues. Nada
   `modified` ni `deprecated` se aplica sin OK explicito del usuario.
4. Aplica los confirmados re-invocando los agentes que correspondan en modo
   actualizacion (`scenario-modeling`, `requirements-specification`,
   `technical-design`), siempre preservando ids; lo deprecado cambia a
   `status: deprecated`, **nunca se borra**.
5. Corre `requirements-inspection` (y `design-inspection` si el diseno cambio), con sus
   lazos de correccion (mismo tope de 3 pasadas que el incremento).
6. Cierra la entrada `CR-xxx` con los verdicts (incluyendo `confirmed_by_user`) y las
   versiones. Si el cambio afecta features ya planificadas o construidas, decilo
   explicito en el resumen: el pipeline de planificacion lo va a levantar del changelog.

## Modo COMPLETO (`/requerimientos <documento>`)

El flujo clasico en cascada, util para proyectos chicos o documentos cerrados:
equivale a DESCUBRIR + un unico INCREMENTO con **todas** las features del mapa.
Registra igual su `DSC-xxx` e `INC-xxx` en el changelog: si despues llega material
nuevo, el proyecto sigue por los modos incrementales sin fricciones. Si el proyecto
ya tiene features baselineadas, no las re-elabores: el modo completo aplica solo a lo
no baselineado (ante la duda, deriva a los modos incrementales).

---

## Reglas de orquestacion

- Cada etapa consume el archivo que produjo la anterior; no lances una etapa sin su
  entrada.
- Las pausas (elicitacion y confirmacion) nunca se saltean. Nunca inventes respuestas
  del stakeholder ni confirmaciones del usuario.
- **Ids estables, siempre**: nada se renumera ni se borra. Lo eliminado se deprecia.
  Los ids nuevos continuan las secuencias existentes.
- **Nada baselineado cambia sin confirmacion del usuario.** Lo nuevo fluye directo.
- Versionado: toda reescritura de un artefacto incrementa su `version`; los
  `*_version_ref` citan la `version` del archivo referenciado; el changelog registra
  antes/despues por corrida.
- Si un subagente falla o produce un archivo vacio, detene el pipeline e informa, no
  continues con datos incompletos. Despues de cada etapa valida que la salida sea JSON
  valido y que los ids referenciados existan.
- Si al arrancar encontras en `changelog.json` una entrada previa con
  `status: in_progress` (una corrida interrumpida), no abras otra en silencio:
  mostrasela al usuario y pregunta si retomarla o cerrarla como `rejected` antes de
  empezar la nueva.
- El pipeline de planificacion consume lo `baselined` (via `requirements.json` +
  `technical-design.json` + `data-model.json`) y usa `changelog.json` para detectar que
  incrementos aun no absorbio.

## Estructura `.dev/requirements/` resultante

```
.dev/requirements/
  sources/                      toda fuente archivada (documentos, vision, entrevistas, CRs)
  source-inventory.json         inventario de secciones (acumulativo)
  lel-candidates.json           candidatos a simbolos del LEL
  supporting-context.json       contexto de soporte
  lel.json / lel.md             Lexico Extendido del Lenguaje (vivo)
  lel-inspection.json / .md     checklist de defectos del LEL
  stakeholder-questions.json/.md cuestionario (defectos + elicitacion)
  stakeholder-answers.md         respuestas del stakeholder (una por QST-xxx)
  product-map.json / .md        mapa del producto: features y stubs con estado
  changelog.json                historia: DSC / INC / CR con veredictos y versiones
  scenarios.json / scenarios.md Escenarios elaborados (acumulativo)
  requirements.json / .md       requisitos (acumulativo)
  requirements-inspection.json/.md inspeccion de los requisitos
  data-model.json / .md         modelo de datos (acumulativo)
  technical-design.json / .md   arquitectura, API, pantallas, ADRs (acumulativo)
  design-inspection.json / .md  inspeccion del diseno
```
