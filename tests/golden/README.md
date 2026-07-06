# Test dorado de la suite

Una corrida completa de la suite sobre una vision fija (`vision.md`, la
turnera de Lupe), verificada etapa por etapa. Es lo que convierte "los
archivos dicen X" en "los agentes hacen X": los prompts son contratos en
prosa, y la unica forma de saber que una edicion no rompio el comportamiento
es correrlos de verdad.

`scripts/validate.py` (CI) garantiza que todo **carga**; este test garantiza
que todo **funciona**. La mitad mecanica (contratos JSON, ids, referencias
cruzadas) la automatiza `scripts/check-artifacts.py`; la mitad semantica (si
los requisitos capturan la vision) se revisa a mano con la checklist de cada
etapa.

## Cuando correrlo

Antes de mergear un cambio que altere el **comportamiento** de un pipeline
(skills, agentes, contratos). No hace falta para typos, docs o cambios del
validador. Cuesta una corrida completa de la suite en tokens: es deliberado
que sea manual y no CI.

## Preparacion

```bash
mkdir /tmp/golden-run && cd /tmp/golden-run
git init
cp <ruta-al-marketplace>/tests/golden/vision.md .
claude   # con los 5 plugins instalados desde la rama a probar
```

## Etapas

Despues de cada etapa, correr el verificador de contratos desde la raiz del
marketplace:

```bash
python scripts/check-artifacts.py /tmp/golden-run --stage <etapa>
```

### 1. `/requerimientos:descubrir vision.md` — etapa `requirements`

Ademas del verificador, comprobar a mano:

- El mapa tiene entre 5 y 8 features (reservas, seña/pagos, cancelacion,
  recordatorios, administracion de Lupe, bloqueo por ausencias, reportes) y
  ninguna inventada fuera de la vision.
- El LEL capturo los simbolos del dominio: turno, seña, ausencia, servicio,
  peluquero, cliente, dueña. "Tres ausencias en seis meses" y "24 horas de
  anticipacion" aparecen en nociones/impactos, no perdidos.
- `changelog.json` tiene su `DSC-001` con status `applied`.

### 2. `/requerimientos:incremento` (elegir reservas + cancelacion) — etapa `requirements`

- Las features elegidas quedaron `baselined` en el mapa; las demas siguen `stub`.
- La regla de no-superposicion de turnos existe como requisito con criterios
  Gherkin; la devolucion de seña tiene los dos casos (mas/menos de 24 h).
- Hay al menos un RNF (mobile, historial que no se borra) con `metric`.
- El diseño tecnico salio (data-model + technical-design): existe la entidad
  turno con su relacion a peluquero y servicio.

### 3. `/planificar` — etapa `plan`

- El verificador es el chequeo fuerte aca (cobertura de lotes, dependencias,
  briefs). A mano: los briefs de `.dev/features/` traen requisitos con sus
  AC, criterios de cierre de feature y el Vocabulario del LEL.

### 4. `/construir-lote` — etapa `build`

- Los checks del verificador mas: el proyecto compila y sus tests pasan
  (correr el comando de test del `stack-profile.json` a mano), hay un PR (o
  rama) por feature, commits con `[T-xxx]`, y el CI del proyecto quedo
  bootstrapeado si no existia.
- Los veredictos de `.dev/build/reviews/` y `security/` existen y `passed`
  refleja lo que el resumen conto.

### 5. `/auditar` (opcional, cierre del circuito)

- La auditoria corre sobre lo construido sin romperse y sus hallazgos citan
  `AUD-001/...`.

## Criterio de aprobacion

La corrida pasa si: `check-artifacts.py` da 0 problemas en cada etapa, la
checklist manual no encontro nada grave, y ninguna etapa requirio intervenir
a mano por fuera de las pausas diseñadas (aprobaciones, preguntas al
stakeholder). Cualquier desvio es un bug de prompt: arreglarlo en el plugin,
no en la corrida.

Guardar el resumen de la corrida (fecha, rama, resultado por etapa) en el PR
que motivo el test.
