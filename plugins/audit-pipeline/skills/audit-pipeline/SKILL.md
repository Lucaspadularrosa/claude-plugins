---
name: audit-pipeline
description: Audita una aplicacion existente en tres dimensiones, bugs de correctitud, seguridad (defensiva) y mejoras de alto retorno, con verificacion adversarial de cada hallazgo antes de reportarlo. Funciona solo o sobre la linea de base reconstruida por recovery-pipeline. Usar cuando el usuario quiere encontrar bugs, revisar seguridad o relevar mejoras en un codebase.
---

# Pipeline de Auditoria (bugs, seguridad y mejoras, con verificacion)

Esta skill audita un codebase en tres dimensiones — **bugs** (correctitud),
**seguridad** (defensiva, del codigo propio) y **mejoras** (deuda, rendimiento, tests)
— y somete cada hallazgo relevante a **verificacion adversarial**: un agente esceptico
intenta refutarlo leyendo el codigo real antes de que llegue al reporte. El resultado
es señal, no ruido.

Funciona standalone en cualquier repo. Si el proyecto tiene la linea de base de la
suite (`.dev/requirements/`, generada por `requirements-pipeline` o reconstruida por
`recovery-pipeline`), la auditoria la usa: divergencias codigo-requisito, permisos que
los requisitos no otorgan, y los hallazgos confirmados pueden convertirse en trabajo
planificable.

**Relacion con el piso de seguridad del build.** Si el codigo se construyo con
`build-pipeline`, ya trae un **piso de seguridad OWASP por construccion**, verificado
feature por feature por su `security-gate` (prevencion). Esta auditoria es el nivel
**profundo y complementario**: analisis adversarial, cadenas de explotacion y cobertura
que el piso no persigue. No se pisan — el gate previene lo tipico y deriva aca lo que
excede el piso (`deferred_to_audit` en `.dev/build/security/*.json`). Corre `/auditar`
cuando quieras esa pasada profunda, sin importar como se construyo el codigo.

Vos, el agente principal, sos el orquestador: delegas en los subagentes con la
herramienta Task (en paralelo cuando se puede), consolidas y reportas.

## Subagentes (en `agents/` del plugin)

| Subagente | Dimension | Escribe |
|---|---|---|
| `bug-hunter` | Correctitud | `.dev/audit/findings-bugs.json` |
| `security-auditor` | Seguridad defensiva | `.dev/audit/findings-security.json` |
| `improvement-scout` | Mejoras de alto retorno | `.dev/audit/findings-improvements.json` |
| `finding-verifier` | Verificacion adversarial de UN hallazgo | (veredicto al orquestador) |

## Procedimiento (`/auditar [alcance]`)

### Paso 1 - Alcance y contexto

- Alcance: `bugs`, `seguridad`, `mejoras`, una ruta/modulo, o nada (= las tres
  dimensiones sobre todo el repo). Resolvelo desde los argumentos del usuario.
- Contexto disponible (pasaselo a los auditores que corresponda): el stack-profile y la
  **base de seguridad** (`.dev/build/security-baseline.json`), los veredictos del
  `security-gate` con lo que dejo para auditoria profunda (`.dev/build/security/*.json`,
  campo `deferred_to_audit`), la linea de base (`.dev/requirements/`) y las señales del
  recovery (`.dev/recovery/state-report.json`, campo `audit_signals`), si existen.
  Ninguno es obligatorio. Arrancar por los `deferred_to_audit` del gate es un buen
  punto de partida cuando existen.

### Paso 2 - Dimensiones en paralelo

Lanza los auditores de las dimensiones elegidas **en paralelo** (una sola tanda de
llamadas Task): son de solo lectura y no se pisan. Espera a que terminen y valida sus
JSON.

### Paso 3 - Verificacion adversarial

Para **cada hallazgo `high` y `medium`** de las tres dimensiones, lanza un
`finding-verifier` (en paralelo, tandas de hasta ~6 para no saturar) con el hallazgo
completo. Los `low` no se verifican (no justifican el costo): se reportan como
`unverified`.

- `confirmed`: entra al reporte final, con la severidad ajustada si el verificador la
  cambio.
- `refuted`: NO entra al reporte principal; queda en la seccion de descartados con la
  razon (transparencia: el usuario puede discrepar).
- `needs_human`: entra en una seccion propia con la pregunta exacta que lo resolveria.

### Paso 4 - Reporte consolidado

Escribi vos (orquestador) `.dev/audit/audit-report.json` y `.dev/audit/audit-report.md`:

```json
{
  "version": 1,
  "metadata": {"created_at": "string", "scope": "string", "dimensions": ["bugs", "security", "improvements"], "baseline_available": false},
  "summary": {
    "confirmed": {"high": 0, "medium": 0, "low_unverified": 0},
    "refuted": 0, "needs_human": 0
  },
  "confirmed_findings": [{"finding": {}, "verification": {}}],
  "needs_human": [{"finding": {}, "question": "string"}],
  "refuted_findings": [{"finding_id": "string", "refutation_basis": "string", "reasoning": "string"}],
  "low_unverified": [{}],
  "warnings": ["string"]
}
```

El `.md` arranca con el resumen ejecutivo (confirmados por severidad y dimension, lo
mas grave primero), despues cada hallazgo confirmado con su evidencia, veredicto y fix
propuesto; al final, los que necesitan tu respuesta y los descartados con su razon.

Versionado: `version` +1 por reescritura (re-auditorias).

### Paso 5 - Cierre y conversion en trabajo

Mostrale al usuario el resumen y ofrece los caminos para los confirmados:

- **Arreglar via la suite** (si hay linea de base): los hallazgos que elija se
  registran como change request — sugerile `/requerimientos:cambio` citando los ids
  (`BUG-xxx`/`SEC-xxx`/`IMP-xxx`) — y de ahi `/replanificar` + `/construir`. Asi el
  fix queda trazable de punta a punta.
- **Arreglar directo** (sin suite): priorizar los `high` y encarar; los hallazgos
  tienen fix propuesto y evidencia.
- Responder los `needs_human` para destrabar esos veredictos.

## Reglas de orquestacion

- **Solo lectura sobre el codigo**: la auditoria no corrige nada; correr tests
  existentes esta permitido, modificar archivos no.
- La verificacion adversarial nunca se saltea para `high`/`medium`. En la duda, el
  hallazgo se descarta: el reporte vale por su tasa de aciertos.
- Seguridad es **defensiva**: vectores e impacto si, exploits funcionales no; secretos
  señalados, nunca copiados.
- Si una dimension falla, reporta las otras igual y deja constancia.
- Re-auditorias: los archivos se reescriben completos (la auditoria es una foto, no un
  historial); el changelog de la suite no se toca — la conversion en trabajo pasa por
  `/requerimientos:cambio`.

## Estructura resultante

```
.dev/audit/
  findings-bugs.json            hallazgos crudos de correctitud
  findings-security.json        hallazgos crudos de seguridad
  findings-improvements.json    hallazgos crudos de mejoras
  audit-report.json / .md       reporte consolidado y verificado (lo que se lee)
```
