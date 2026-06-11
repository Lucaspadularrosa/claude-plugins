# Guía de uso — De la idea al plan de ejecución con agentes IA

Esta guía explica cómo usar los plugins `requirements-pipeline` y `planning-pipeline`
juntos: desde un documento de dominio (o ninguna documentación) hasta un plan de
ejecución donde varios agentes de Claude Code construyen features en paralelo, con
trazabilidad y auditoría completas en todo el recorrido.

```
material de dominio          requisitos auditables           plan para agentes IA
(docs, carpetas o nada)  →   (LEL, escenarios, requisitos,  →  (tareas, lotes paralelos,
                              diseño técnico, changelog)        briefs por feature)
```

---

## 1. Instalación

Una sola vez por usuario:

```bash
/plugin marketplace add Lucaspadularrosa/claude-plugins
/plugin install requirements-pipeline@lpadularrosa-dev-plugins
/plugin install planning-pipeline@lpadularrosa-dev-plugins
```

(`lpadularrosa-dev-plugins` es el nombre del marketplace declarado en
`.claude-plugin/marketplace.json`; verificalo con `/plugin` si los comandos varían en
tu versión de Claude Code.)

Requisitos: Claude Code con soporte de plugins, y **Python 3.8+** para extraer texto
de documentos. Para leer PDF: `pip install pypdf`. Word (`.docx`), Markdown y texto
plano no necesitan nada.

En tus proyectos no hay que copiar ninguna carpeta: los plugins viven fuera del
proyecto y solo generan salidas en `.dev/requirements/` y `.dev/plan/`.

---

## 2. Conceptos en un minuto

| Concepto | Qué es |
|---|---|
| **LEL** | El vocabulario del dominio (sujetos, objetos, verbos, estados), con definiciones trazables a las fuentes. Es un artefacto vivo: crece con cada documento o entrevista. |
| **Mapa del producto** | Todas las features candidatas (`FG-xx`) con sus escenarios en borrador (`stub`), priorizadas. Amplitud completa, profundidad cero: se elabora solo lo que decidas. |
| **Incremento** | Elaborar y *baselinear* un grupo de features: escenarios completos, requisitos con criterios Gherkin, inspección y diseño técnico. Lo baselineado es lo único que se planifica. |
| **Changelog** | La historia de la línea de base: cada descubrimiento (`DSC`), incremento (`INC`) y cambio (`CR`), con qué agregó/modificó y qué versiones quedaron. Es lo que conecta requisitos con planificación. |
| **Lotes** | El plan agrupa las features en lotes (`BATCH-1`, `BATCH-2`...): todas las del mismo lote se construyen **en paralelo**, una rama y un agente por feature. Antes del primer lote se mergea la **ronda de contratos** (las firmas/API que las features comparten). |
| **progress.json** | El estado del build (`pending`/`in_progress`/`done` por feature y tarea). Es lo que protege lo construido cuando los requisitos cambian. |

Regla de oro del sistema: **los ids nunca cambian, nada se borra** (lo eliminado se
deprecia) y **nada baselineado se modifica sin tu confirmación**.

---

## 3. Los comandos

| Comando | Plugin | Para qué |
|---|---|---|
| `/requerimientos:descubrir [rutas]` | requirements | Pasada panorámica: LEL + mapa del producto. Acepta documentos, carpetas o nada. Re-ejecutable cada vez que llega material. |
| `/requerimientos:incremento <features>` | requirements | Elabora y baselinea las features elegidas. |
| `/requerimientos:cambio <texto o doc>` | requirements | Cambio puntual sobre lo baselineado, con confirmación previa. |
| `/requerimientos <rutas>` | requirements | Modo completo clásico: descubrir + elaborar todo en una corrida. |
| `/planificar` | planning | Genera el plan de ejecución de lo baselineado: tareas, lotes paralelos, briefs. |
| `/replanificar` | planning | Actualiza el plan cuando los requisitos cambiaron, sin tocar lo construido. |

Todos funcionan también en lenguaje natural ("genera los requisitos a partir de estos
documentos", "los requisitos cambiaron, actualiza el plan").

---

## 4. Flujos típicos

### Caso A — Arrancás con documentos (el caso común)

```
/requerimientos:descubrir docs/vision.docx docs/anexos/
```

Podés pasar varios archivos y carpetas (de una carpeta toma todos los `.docx`, `.pdf`,
`.md` y `.txt`). El pipeline extrae el texto, arma el LEL, lo inspecciona y **te hace
un cuestionario** (ver sección 5). Respondelo y al final tenés el **mapa del
producto** en `.dev/requirements/product-map.md`: las features priorizadas con sus
escenarios en borrador.

Elegí qué entra al MVP y elaborálo:

```
/requerimientos:incremento FG-01 FG-02 FG-05
```

Esto profundiza solo esas features (escenarios completos, requisitos, inspección con
lazo de corrección, diseño técnico de lo que tocan). Te va a preguntar si hay mockups
de UI para las pantallas. Al terminar, esas features quedan **baselineadas**.

```
/planificar
```

Genera `.dev/plan/`: las tareas, la ronda de contratos, los lotes paralelos y un brief
por feature en `.dev/features/`. El resumen te dice cuántos agentes en paralelo
aprovecha el plan (`max_parallel_degree`) y cuántos turnos lleva (`critical_path`).
A construir (sección 6).

### Caso B — No tenés ningún documento

```
/requerimientos:descubrir
```

Sin argumentos, el pipeline te pide la **visión** (qué problema resuelve, para quién,
qué te imaginás) y te entrevista. El cuestionario va a ser **más largo** de lo normal:
es esperable, tus respuestas son la fuente del dominio y quedan archivadas con la
misma trazabilidad que un documento. De ahí en adelante, igual que el Caso A.

### Caso C — El build está en marcha y llega material nuevo

```
/requerimientos:descubrir docs/facturacion.docx
```

Siempre seguro: agrega features nuevas al mapa y enriquece el LEL. Si el documento
**se pisa con algo ya baselineado**, no lo aplica: te lo muestra como propuesta y
decidís vos. Cuando quieras construir lo nuevo:

```
/requerimientos:incremento FG-09
/replanificar
```

`/replanificar` integra lo nuevo al plan **sin frenar nada**: lo terminado queda
intacto, lo que está en curso conserva su lote, y lo nuevo entra donde el grafo de
dependencias lo permita — incluso en paralelo con lo que ya corre.

### Caso D — Un cambio puntual ("el login ahora necesita 2FA")

```
/requerimientos:cambio "el login ahora requiere segundo factor por SMS"
/replanificar
```

El pipeline determina qué es nuevo, qué modifica algo existente y qué ya estaba
cubierto, **te muestra el antes/después y espera tu OK** por cada modificación. Después
`/replanificar` ajusta el plan: si la tarea afectada no se empezó, se reescribe; si ya
se construyó, se crea una tarea de ajuste (la historia no se reescribe).

### Caso E — Proyecto chico con un documento cerrado

```
/requerimientos docs/especificacion.docx
/planificar
```

El modo completo clásico: descubre y elabora todo en una corrida. Queda registrado en
el changelog igual, así que si después llega material nuevo el proyecto sigue por los
modos incrementales sin fricción.

---

## 5. Las pausas: qué te va a preguntar y cómo responder

El pipeline se detiene y te espera en estos puntos (nunca inventa tus respuestas):

1. **Cuestionario al stakeholder** (en descubrir). Te muestra
   `stakeholder-questions.md` con preguntas agrupadas por rol y prioridad. Responder
   las `high` destraba las definiciones bloqueantes; podés contestar en el chat o
   llevar el archivo al stakeholder y volver con las respuestas. También podés decir
   "no hay dudas, seguí".
2. **Mockups de UI** (en incremento, si hay pantallas). Si tenés HTML, CSS, wireframes
   o capturas, pasale la carpeta: las toma como diseño autoritativo. Si no, propone
   las pantallas de forma abstracta.
3. **Confirmación de cambios sobre lo baselineado** (en incremento y cambio). Te
   muestra el antes/después de cada requisito que se modificaría o depreciaría, uno
   por uno. Solo se aplica lo que confirmás.
4. **Conflictos de replanificación**. Si un cambio afecta trabajo ya construido o en
   curso (ej.: se deprecó un requisito cuya tarea está `done`), te presenta el
   conflicto con una sugerencia y decidís vos.

---

## 6. Ejecutar el plan con agentes en paralelo

El plan está pensado para una flota de instancias de Claude Code (una por PC, licencia
o agente), una rama por feature. El orden operativo sale de
`.dev/plan/execution-plan.md`:

1. **Ronda de contratos** (`BATCH-0`): ejecutá y mergeá primero las tareas-contrato.
   Son chicas (definen APIs, tipos, schemas compartidos); un solo agente las resuelve.
2. **Por cada lote, en orden** (`BATCH-1`, `BATCH-2`...): lanzá un agente por feature
   del lote, **todos a la vez**, cada uno en su rama. A cada agente dale su brief:
   `.dev/features/{feature}.md` — es autosuficiente: tareas en orden de ejecución,
   criterios de aceptación Gherkin, diseño relevante, contratos que consume y con
   quién corre en paralelo.
3. **Cuando el lote mergea, arranca el siguiente.** Si hay menos agentes que features
   en el lote, empezá por las de prioridad `high` (el orden dentro del lote es libre;
   entre lotes no).
4. **Mantené `.dev/plan/progress.json` al día**: marcá cada feature/tarea
   `in_progress` al arrancarla y `done` al mergearla. Es lo que le permite a
   `/replanificar` no pisar lo construido. Si usás un pipeline de build propio,
   sumale ese paso al cierre de cada feature.

---

## 7. Dónde mirar cada cosa

| Quiero ver... | Archivo |
|---|---|
| El mapa del producto y qué está baselineado | `.dev/requirements/product-map.md` |
| El vocabulario del dominio | `.dev/requirements/lel.md` |
| Los requisitos con sus criterios | `.dev/requirements/requirements.md` |
| La historia de cambios (quién trajo qué) | `.dev/requirements/changelog.json` |
| Si los requisitos/diseño pasaron las auditorías | `.dev/requirements/*-inspection.md` |
| Los lotes y el paralelismo del plan | `.dev/plan/execution-plan.md` |
| Si el plan pasó la auditoría | `.dev/plan/plan-inspection.md` |
| El estado del build | `.dev/plan/progress.json` |
| Qué construir para una feature | `.dev/features/{feature}.md` |

La trazabilidad funciona en ambas direcciones: desde una tarea podés volver hasta la
sección del documento que la originó (tarea → requisito → escenario → símbolo del LEL
→ fuente), y desde un documento o CR podés ver todo lo que produjo (changelog).

---

## 8. Preguntas frecuentes

**El PDF no se extrae.** Instalá una biblioteca: `pip install pypdf`. Los `.doc`
viejos convertilos a `.docx` primero.

**¿Puedo correr `/planificar` con features sin elaborar?** Sí: planifica solo lo
baselineado. Lo que está en `stub` en el mapa no entra al plan hasta que lo elabores
con un incremento.

**El plan dice que está desactualizado (defecto PLAN-CHECK-007).** Hay incrementos o
CRs que el plan no absorbió. Corré `/replanificar`.

**Rechacé una propuesta de cambio, ¿se pierde?** No: queda `rejected` en el changelog,
con su fuente archivada. Si cambiás de idea, la podés retomar con
`/requerimientos:cambio`.

**¿Qué pasa si dos documentos se contradicen?** El pipeline no decide solo: lo
registra como pregunta abierta o propuesta y te lo muestra en la pausa que
corresponda.

**¿Puedo partir un incremento grande?** Sí, y conviene: incrementos chicos (2–4
features) mantienen las pausas cortas y el plan rodando. La unidad mínima es una
feature.

**¿Cómo empiezo de cero en otro proyecto?** Nada que copiar: entrá al proyecto y corré
`/requerimientos:descubrir`. Todo lo generado queda en `.dev/` de ese proyecto.

---

## 9. Referencias

- `plugins/requirements-pipeline/README.md` y `PIPELINE.md` — detalle del pipeline de
  requisitos (método LEL y Escenarios, modos, agentes, contratos de archivos).
- `plugins/planning-pipeline/README.md` y `PIPELINE.md` — detalle del pipeline de
  planificación (lotes, contratos, replanificación, checks de auditoría).
- `plugins/feature-pipeline/README.md` — pipeline de build independiente (lee
  requerimientos de `/features/` con su propio formato; hoy no engancha directo con
  los briefs de `.dev/features/`).
