---
description: Registra y aplica un cambio puntual sobre requisitos ya baselineados (un pedido del stakeholder, un mail, un documento corto), con veredictos, confirmacion previa y trazabilidad completa.
argument-hint: <descripcion del cambio o ruta a un documento corto>
---

Ejecuta el modo CAMBIO de la skill `requirements-pipeline` para: `$ARGUMENTS`

Segui la skill tal cual (CR en el changelog, veredictos `new|modified|deprecated|
already_covered` decididos sobre las tajadas, PAUSA DE CONFIRMACION antes de tocar
nada baselineado, aplicacion en modo actualizacion, inspecciones, cierre por script).
Si cito ids de auditoria o desvios del build, usa esos hallazgos como fuente. Si el
cambio afecta features ya planificadas o en construccion, decimelo explicito.
