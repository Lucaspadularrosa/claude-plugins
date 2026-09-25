---
description: "Camino rapido: convierte un documento corto o un pedido urgente en UNA feature lista para construir, sin pasar por el ciclo completo de requisitos. Para cuando hay que sacarlo ya. Los documentos formales se generan despues con /promover."
argument-hint: "<ruta a un documento corto, o el pedido en texto>"
---

Ejecuta el modo TARJETA de la skill `planning-pipeline` para: `$ARGUMENTS`

Segui la skill tal cual (version del pipeline por script, reserva del `FG-xx`, archivo
de la fuente, `card-authoring`, `validate_card.py` hasta verde, `card-inspection`
contra la fuente, PAUSA UNICA con la tarjeta y los defectos de la inspeccion,
proyeccion por script con `card_to_partial.py` + `merge_tasks.py` +
`compute_execution_plan.py`, brief y `validate_plan.py --briefs`, y registro de la
deuda en el changelog).

En la pausa mostrame por separado lo que necesita una decision mia de lo que quedo
anotado, y las preguntas abiertas con el supuesto con el que va a seguir el build si no
las contesto.

Antes de arrancar, decime si esto **no** deberia ir por el atajo: mas de una feature,
cambios en el modelo de datos central, requisitos que hay que acordar con un tercero, o
dominio sin vocabulario comun. En ese caso recomendame el ciclo formal y espera mi
decision.

Al cerrar, mostrame la tarjeta, el comando para construir y que queda pendiente de
promover.
