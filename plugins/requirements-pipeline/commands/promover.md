---
description: "Promueve a linea de base formal una feature que se construyo por el camino rapido: convierte su tarjeta y el codigo ya escrito en LEL, escenarios, requisitos y diseno, y salda la deuda de documentacion."
argument-hint: <FG-01 FG-02 ... o vacio para ver que hay pendiente de promover>
---

Ejecuta el modo PROMOVER de la skill `requirements-pipeline` para: `$ARGUMENTS`

Segui la skill tal cual (entrada del changelog, tajada de la tarjeta mas el diff de
sus commits, los cuatro agentes en modo actualizacion en paralelo escribiendo deltas
con los ids provisionales de la tarjeta, `apply_delta.py --mapa-salida`,
`promote_card.py`, inspecciones de requisitos y diseno, cierre por script).

Si no nombre features, mostrame las tarjetas en estado `built` sin promover, de la
mas vieja a la mas nueva, y recomendame por cual empezar.

Las preguntas abiertas de la tarjeta van al cuestionario del stakeholder: no las
respondas vos. Y si el codigo hace algo que la tarjeta no dice, gana el codigo —
avisame cual es la diferencia.
