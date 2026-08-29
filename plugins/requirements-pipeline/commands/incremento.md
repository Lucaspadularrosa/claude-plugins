---
description: "Elabora y baselinea las features elegidas del mapa del producto: escenarios completos, requisitos con su inspeccion y diseno tecnico delta. La unidad del incremento es la feature."
argument-hint: <FG-01 FG-02 ... o nombres de features del mapa>
---

Ejecuta el modo INCREMENTO de la skill `requirements-pipeline` para: `$ARGUMENTS`

Segui la skill tal cual (tajadas por script, escenarios y requisitos en paralelo por
feature con merge por script, PAUSA DE CONFIRMACION si algo baselineado cambiaria,
inspeccion de requisitos y diseno tecnico en paralelo, inspecciones por script +
juicio con tope de 3 pasadas, compuerta de cierre por script). Si no elegi features,
recomendame el incremento por valor y espera mi eleccion. Al cerrar, mostrame el
resumen y el paso siguiente (`/planificar` o replanificar).
