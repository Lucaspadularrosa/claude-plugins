# Pipeline: Auditoria (bugs, seguridad y mejoras, verificados)

Audita un codebase en tres dimensiones y somete cada hallazgo relevante a
**verificacion adversarial** antes de reportarlo: un agente esceptico intenta
refutarlo leyendo el codigo real. El reporte final tiene señal, no ruido.

---

## Flujo

```
codigo de la aplicacion              <- ENTRADA (no se modifica nada)
contexto opcional: .dev/requirements/ (linea de base), .dev/build/stack-profile.json,
                   .dev/recovery/state-report.json (audit_signals)
        |
        v  EN PARALELO (segun alcance)
[bug-hunter]            -> .dev/audit/findings-bugs.json
[security-auditor]      -> .dev/audit/findings-security.json
[improvement-scout]     -> .dev/audit/findings-improvements.json
        |
        v  VERIFICACION ADVERSARIAL (en paralelo, por hallazgo high/medium)
[finding-verifier] x N      cada uno intenta REFUTAR un hallazgo leyendo el codigo:
                            guard rio arriba? framework ya mitiga? escenario
                            inalcanzable? codigo muerto? retorno irreal?
                            En la duda -> refutado.
        |
        v  [orquestador consolida]
.dev/audit/audit-report.json + .md   confirmados (severidad ajustada) /
                                     necesitan respuesta humana /
                                     descartados con su razon / low sin verificar
        |
        v  CIERRE: convertir confirmados en trabajo trazable
           (/requerimientos:cambio -> /replanificar -> /construir) o encarar directo
```

---

## Agentes

| Agente | Dimension | Definicion |
|---|---|---|
| `bug-hunter` | Correctitud: logica rota, casos borde, estado, errores tragados, divergencia con requisitos | `agents/bug-hunter.md` |
| `security-auditor` | Seguridad defensiva: authz/authn, inyeccion, secretos, validacion, exposicion de datos | `agents/security-auditor.md` |
| `improvement-scout` | Mejoras con retorno: tests donde duele, duplicacion, rendimiento, deuda, simplificaciones | `agents/improvement-scout.md` |
| `finding-verifier` | Esceptico profesional: un hallazgo por invocacion, veredicto confirmed/refuted/needs_human | `agents/finding-verifier.md` |

La orquestacion vive en `skills/audit-pipeline/SKILL.md`.

---

## Reglas clave

- **Solo lectura**: la auditoria no corrige; correr tests existentes si, modificar
  archivos no.
- **Verificacion adversarial obligatoria** para `high`/`medium`; en la duda el
  hallazgo se descarta (queda en la seccion de descartados, con la razon, por
  transparencia). Los `low` se reportan sin verificar.
- **Seguridad defensiva**: vectores e impacto, no exploits; secretos señalados, nunca
  copiados al reporte.
- **Con linea de base, audita contra ella**: divergencias codigo-requisito, permisos
  no otorgados por los requisitos. Sin linea de base funciona igual.
- **Los hallazgos se convierten en trabajo**: cada confirmado tiene evidencia
  `archivo:linea` y fix propuesto, y puede registrarse como change request de la
  suite (`/requerimientos:cambio`) para planificarse y construirse con trazabilidad.

---

## Como iniciar

```
/auditar                      (las tres dimensiones, todo el repo)
/auditar seguridad            (solo seguridad)
/auditar bugs src/api/        (una dimension, un alcance)
```

O en lenguaje natural ("busca bugs en esta app", "revisa la seguridad",
"que mejoras le harias a este codigo").
