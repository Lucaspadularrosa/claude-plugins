---
description: "Para cuando llega un pedido que cambia algo ya acordado (un mail, un mensaje del cliente, un ajuste de alcance). Te muestra que se modifica, que se da de baja y que ya estaba cubierto, y no toca nada sin tu OK explicito."
argument-hint: <descripcion del cambio o ruta a un documento corto>
---

Ejecuta el modo CAMBIO de la skill `requirements-pipeline` para: `$ARGUMENTS`

Segui la skill tal cual (CR en el changelog, veredictos `new|modified|deprecated|
already_covered` decididos sobre las tajadas, PAUSA DE CONFIRMACION antes de tocar
nada baselineado, aplicacion en modo actualizacion, inspecciones, cierre por script).
Si cito ids de auditoria o desvios del build, usa esos hallazgos como fuente. Si el
cambio afecta features ya planificadas o en construccion, decimelo explicito.
