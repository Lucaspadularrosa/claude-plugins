# Guía de uso — De la idea (o de la app heredada) al sistema construido

Esta guía explica cómo usar la suite completa: requisitos, planificación, build,
comprensión de apps existentes y auditoría. Hay dos puertas de entrada y todo
converge en los mismos artefactos trazables:

```
GREENFIELD: material de dominio     →  requisitos auditables  →  plan  →  build en
            (docs, carpetas o nada)    (LEL, escenarios,         paralelo (cualquier
                                        changelog)                stack)

BROWNFIELD: app existente           →  línea de base           →  auditoría, cambios,
            (vibe-coding, legacy)      reconstruida desde         incrementos, plan
                                       el código                   y build
```

---

## 1. Instalación

Una sola vez por usuario:

```bash
/plugin marketplace add Lucaspadularrosa/claude-plugins
/plugin install requerimientos@lpadularrosa-dev-plugins
/plugin install planning-pipeline@lpadularrosa-dev-plugins
/plugin install build-pipeline@lpadularrosa-dev-plugins
/plugin install recovery-pipeline@lpadularrosa-dev-plugins
/plugin install audit-pipeline@lpadularrosa-dev-plugins
```

(`lpadularrosa-dev-plugins` es el nombre del marketplace declarado en
`.claude-plugin/marketplace.json`; verificalo con `/plugin` si los comandos varían en
tu versión de Claude Code.)

Requisitos: Claude Code con soporte de plugins, y **Python 3.8+** para extraer texto
de documentos. Para leer PDF: `pip install pypdf`. Word (`.docx`), Markdown y texto
plano no necesitan nada.

En tus proyectos no hay que copiar ninguna carpeta: los plugins viven fuera del
proyecto y solo generan salidas bajo `.dev/` (requirements, plan, features, build,
recovery, audit — ver la tabla de la sección 7).

---

## 2. Conceptos en un minuto

| Concepto | Qué es |
|---|---|
| **LEL** | El vocabulario del dominio (sujetos, objetos, verbos, estados), con definiciones trazables a las fuentes. Es un artefacto vivo: crece con cada documento o entrevista. |
| **Mapa del producto** | Todas las features candidatas (`FG-xx`) con sus escenarios en borrador (`stub`), priorizadas. Amplitud completa, profundidad cero: se elabora solo lo que decidas. |
| **Incremento** | Elaborar y *baselinear* un grupo de features: escenarios completos, requisitos con criterios Gherkin, inspección y diseño técnico. Lo baselineado es lo único que se planifica. |
| **Changelog** | La historia de la línea de base: cada descubrimiento (`DSC`), incremento (`INC`), cambio (`CR`) y recuperación desde código (`REC`), con qué agregó/modificó y qué versiones quedaron. Es lo que conecta requisitos con planificación. |
| **Lotes** | El plan agrupa las features en lotes (`BATCH-1`, `BATCH-2`...): todas las del mismo lote se construyen **en paralelo**, una rama y un agente por feature. Antes del primer lote se mergea la **ronda de contratos** (las firmas/API que las features comparten). |
| **progress.json** | El estado del build: `pending`/`in_progress`/`done` por feature; las tareas suman `blocked` y `cancelled`. Es lo que protege lo construido cuando los requisitos cambian. |

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
| `/construir <feature>` | build | Construye una feature en su rama, con tu aprobación del plan de implementación. Cualquier stack. |
| `/construir-lote [BATCH-n]` | build | Construye un lote completo en paralelo (un agente por feature, en worktrees), sin pausas. |
| `/comprender [ruta]` | recovery | Comprende una app existente: qué hace, en qué estado está, qué falta. Reconstruye la línea de base con evidencia al código. |
| `/auditar [alcance]` | audit | Bugs, seguridad y mejoras, con verificación adversarial de cada hallazgo. Funciona en cualquier repo. |

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

### Caso F — Heredás una app existente (vibe-codeada, legacy, sin documentación)

```
/comprender
```

El pipeline de comprensión lee el código (solo lectura, no toca nada): inventaría el
stack y la estructura, extrae qué hace la app con evidencia `archivo:línea`,
**reconstruye la línea de base de requisitos** en `.dev/requirements/` (lo que el
código demuestra completo queda baselineado; lo que está a medias queda en stub con lo
que falta documentado), y te entrega dos cosas: el **reporte de estado honesto** (qué
está completo, a medias o muerto) y el **cuestionario del dueño** — preguntas sin
tecnicismos sobre lo que el código decidió y nadie validó. Respondelas y la
reconstrucción se afina.

A partir de ahí la app está adentro de la suite:

```
/auditar                                  bugs, seguridad y mejoras, verificados
/requerimientos:cambio "arreglar SEC-001 y BUG-003"   hallazgos → trabajo trazable
/requerimientos:incremento FG-07          completar la feature que estaba a medias
/planificar  →  /construir-lote           planificar y construir lo que falta
```

`/auditar` también funciona solo, en cualquier repo sin la suite: tres dimensiones
(bugs de correctitud, seguridad defensiva, mejoras de alto retorno) y cada hallazgo
`high`/`medium` pasa por un **verificador adversarial** que intenta refutarlo leyendo
el código antes de reportártelo — en la duda se descarta, así el reporte tiene señal y
no ruido. Los descartados quedan listados con su razón, por transparencia.

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

## 6. Ejecutar el plan: el build

El plugin `build-pipeline` es el ejecutor nativo del plan, **agnóstico de stack**: la
primera vez detecta cómo se desarrolla tu proyecto (manifiestos, configs, CI,
CLAUDE.md) y lo registra en `.dev/build/stack-profile.json` — comandos de test/lint/
build, layout y convenciones. En la misma pasada deriva la **base de seguridad** del
stack (`.dev/build/security-baseline.json`): la superficie de ataque, las categorías
OWASP Top 10 aplicables y el mecanismo nativo del framework para cada una. Funciona con
cualquier lenguaje o framework, incluso en proyectos greenfield (deriva los perfiles del
diseño técnico y la primera feature crea el esqueleto).

Dos formas de ejecutar, combinables:

- **`/construir-lote`** — una sola sesión ejecuta el lote completo: mergea primero la
  ronda de contratos si está pendiente, crea un git worktree por feature y lanza un
  subagente por feature **en paralelo**, sin pausas. Cada feature termina en su PR;
  el control humano queda ahí. Cuando los PRs mergean, el siguiente lote se
  desbloquea.
- **`/construir <feature>`** — una instancia de Claude Code construye una feature, con
  una pausa para que **apruebes el plan de implementación** antes de codear. Ideal
  para repartir un lote entre varias PCs/licencias: cada instancia toma una feature
  distinta del mismo lote.

En ambos modos: cada tarea se implementa **con el piso de seguridad OWASP aplicado por
construcción** y **se verifica contra sus criterios Gherkin** (tests con el framework del
proyecto) antes de pasar a la siguiente, con un commit `[T-xxx]` por tarea; antes del PR,
un agente revisor audita el diff contra el brief (cobertura, **cierre por requisito**
— cada requisito del brief con sus criterios de aceptación demostrados, no solo los
de las tareas —, scope, tests corridos de verdad) y un `security-gate` verifica el
piso de seguridad (OWASP + audit de
dependencias); con ambos en verde, un `user-docs-writer` escribe la **guía de usuario
final** de la feature (`docs/usuario/{slug}.html`, HTML standalone en el vocabulario
del LEL — best-effort, nunca bloquea el PR) y viaja en el mismo PR; y `progress.json`
se actualiza en cada transición (`done` = mergeado), que
es lo que le permite a `/replanificar` no pisar lo construido. La auditoría profunda de
seguridad sigue estando en `/auditar` (`audit-pipeline`), al que el gate deriva lo que
excede el piso.

Si preferís usar tu propio pipeline de build, los briefs de `.dev/features/` son
autosuficientes: respetá el orden de lotes de `execution-plan.md` y mantené
`progress.json` al día.

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
| Cómo se desarrolla este proyecto (stack, comandos) | `.dev/build/stack-profile.json` |
| El manual de usuario de lo construido | `docs/usuario/index.html` (y una guía por feature) |
| La base de seguridad del stack (superficie, OWASP, tooling) | `.dev/build/security-baseline.json` |
| El veredicto de review de una feature construida | `.dev/build/reviews/{feature}.json` |
| El veredicto de seguridad (piso OWASP) de una feature | `.dev/build/security/{feature}.json` |
| El estado real de una app comprendida | `.dev/recovery/state-report.md` |
| Qué hace la app, con evidencia al código | `.dev/recovery/behavior-map.md` |
| Las preguntas pendientes del dueño | `.dev/recovery/owner-questions.md` |
| Los hallazgos de auditoría confirmados | `.dev/audit/audit-report.md` |

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
- `plugins/build-pipeline/README.md` y `PIPELINE.md` — detalle del pipeline de build
  (perfil de stack por evidencia, modos feature/lote, reviewer, worktrees).
- `plugins/recovery-pipeline/README.md` y `PIPELINE.md` — detalle del pipeline de
  comprensión (inventario, extracción de comportamiento, reconstrucción, estado).
- `plugins/audit-pipeline/README.md` y `PIPELINE.md` — detalle del pipeline de
  auditoría (tres dimensiones, verificación adversarial, conversión en trabajo).
- `archive/feature-pipeline/` — el pipeline de build de la primera generación,
  retirado del marketplace (su rol lo cubren `build-pipeline` y `audit-pipeline`).
