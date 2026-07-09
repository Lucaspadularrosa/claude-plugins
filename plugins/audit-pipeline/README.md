# Audit Pipeline — Plugin de Claude Code

Plugin que audita un codebase en tres dimensiones — **bugs** de correctitud,
**seguridad** (defensiva, del codigo propio) y **mejoras** de alto retorno — con una
diferencia clave: **cada hallazgo relevante se verifica adversarialmente antes de
llegar a tu reporte**. Un agente esceptico intenta refutarlo leyendo el codigo real
(¿hay una validacion rio arriba? ¿el framework ya lo mitiga? ¿el escenario es
alcanzable?); en la duda, el hallazgo se descarta. Lo que te llega confirmado, es
real.

## Uso

```
/auditar                      las tres dimensiones, todo el repo
/auditar seguridad            una dimension
/auditar bugs src/api/        dimension + alcance acotado
```

Funciona **standalone en cualquier repo** — no necesita el resto de la suite. Es de
solo lectura: no modifica un archivo (correr tus tests existentes si esta permitido).

## Que produce

`.dev/audit/audit-report.md` (+ `.json`), con:

- **Confirmados**, por severidad y dimension, cada uno con evidencia `archivo:linea`,
  el escenario o vector concreto, el veredicto del verificador y el fix propuesto.
- **Necesitan tu respuesta**: hallazgos cuya verdad depende de algo que el codigo no
  contiene (una regla de negocio que solo vos conoces), con la pregunta exacta.
- **Descartados**: lo que el verificador refuto y por que — transparencia total, podes
  discrepar.
- Los `low` sin verificar (no justifican el costo de verificacion), aparte.

## Integrado con la suite (opcional, recomendado)

Si el proyecto tiene la linea de base (`.dev/requirements/`, generada por
`requerimientos` o reconstruida por `recovery-pipeline`), la auditoria sube de
nivel:

- **Audita contra lo que el sistema deberia hacer**: divergencias codigo-requisito,
  endpoints que permiten lo que ningun requisito otorga.
- **Los hallazgos se convierten en trabajo trazable**: los confirmados que elijas se
  registran via `/requerimientos:cambio` (citando `BUG-xxx`/`SEC-xxx`/`IMP-xxx`),
  entran al plan con `/replanificar` y se arreglan con `/construir` — encontrar el
  problema y arreglarlo quedan en el mismo sistema auditable.
- Las señales que dejo `/comprender` (`audit_signals` del state-report) son el punto
  de partida de los auditores.

> Nota: Claude Code trae `/security-review` y `/code-review` integrados, excelentes
> para revisar un diff o branch. Este plugin apunta a otra cosa: auditar la
> aplicacion completa, contra su linea de base, con verificacion adversarial y
> salida estructurada convertible en trabajo planificable.

## Estructura del plugin

```
audit-pipeline/
  .claude-plugin/plugin.json
  agents/
    bug-hunter.md            correctitud: logica rota, casos borde, estado
    security-auditor.md      seguridad defensiva: authz, inyeccion, secretos, exposicion
    improvement-scout.md     mejoras con retorno concreto, priorizadas por valor/esfuerzo
    finding-verifier.md      el esceptico: intenta refutar cada hallazgo high/medium
  skills/audit-pipeline/SKILL.md
  commands/auditar.md
  PIPELINE.md
  README.md
```

## Garantias

- **Tasa de aciertos sobre volumen**: pocos hallazgos solidos antes que checklist de
  ruido; en la duda, descartado.
- **Todo refutable**: cada hallazgo cita archivo:linea y un escenario/vector concreto;
  cada veredicto cita lo que el verificador leyo.
- **Seguridad responsable**: defensiva, sin exploits funcionales, sin secretos
  copiados al reporte.

Ver `PIPELINE.md` para el diagrama y las reglas.
