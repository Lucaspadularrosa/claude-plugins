---
description: Registra y aplica un cambio puntual sobre requisitos ya baselineados (un pedido del stakeholder, un mail, un documento corto), con veredictos, confirmacion previa y trazabilidad completa.
argument-hint: <descripcion del cambio o ruta a un documento corto>
---

Ejecuta el modo CAMBIO de la skill `requirements-pipeline` para: `$ARGUMENTS`

1. Registra el change request (`CR-xxx`) en `changelog.json` y archiva la fuente en
   `.dev/requirements/sources/cr/` (mi texto o el documento extraido).
2. Lee lo existente (LEL, mapa, requisitos, diseno) y determina el veredicto de cada
   pedido: `new` (no existia), `modified` (toca algo baselineado), `deprecated`
   (elimina algo) o `already_covered` (ya estaba cubierto: el CR queda respondido sin
   tocar nada). Si hay vocabulario nuevo, pasa la fuente por intake + LEL +
   inspeccion.
3. PAUSA DE CONFIRMACION: mostrame los veredictos con el antes/despues. Nada
   `modified` ni `deprecated` se aplica sin mi OK explicito, uno por uno.
4. Aplica los confirmados con los agentes en modo actualizacion, preservando ids; lo
   deprecado cambia de status, nunca se borra. Corre `requirements-inspection` (y
   `design-inspection` si el diseno cambio) con sus lazos (tope: 3 pasadas).
5. Cierra la entrada del changelog con los veredictos confirmados y las versiones.
   Si el cambio afecta features ya planificadas o en construccion, decimelo explicito
   en el resumen.
