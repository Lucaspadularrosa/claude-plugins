---
description: "Todo el ciclo de requisitos en una sola corrida, para proyectos chicos o cuando el documento ya esta cerrado y no va a cambiar. Si el trabajo es iterativo, conviene /requerimientos:descubrir y despues /requerimientos:incremento."
argument-hint: <rutas a documentos o carpetas>
---

Genera la linea de base de requisitos completa a partir de: `$ARGUMENTS`

Es el modo COMPLETO de la skill `requirements-pipeline`: DESCUBRIR mas un unico
INCREMENTO con todas las features del mapa, con sus entradas `DSC-xxx` e `INC-xxx` en
el changelog. Segui la skill tal cual, con sus pausas (cuestionario, mockups de UI,
cambios sobre lo baselineado). Al cerrar, lista los archivos generados con el conteo
de simbolos, defectos, escenarios, requisitos, entidades y decisiones, y las preguntas
abiertas que siguen bloqueando. Si no indique ninguna ruta, sugerime
`/requerimientos:descubrir` (soporta arrancar sin documento) o pedime las rutas.
