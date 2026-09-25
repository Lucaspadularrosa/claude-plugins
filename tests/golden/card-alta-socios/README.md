# Tarjeta de buena fe con silencios conocidos

Fixture para el camino rapido (`/tarjeta`). A diferencia de
`tests/adversarial/fixtures/card-injection/`, este pedido **no tiene trampas**: es un
mail corto, honesto y razonable de un cliente real cualquiera.

Su valor es que ya sabemos que se le escapa, porque se construyo de verdad. Sobre esta
fuente se corrio el circuito completo (tarjeta -> build -> promocion) y aparecieron
cinco decisiones que el pedido no resuelve y el codigo tuvo que tomar igual.

## Como correrlo

Lanza un subagente con `plugins/planning-pipeline/agents/card-authoring.md` sobre
`pedido-001.txt` (FG-01, tag FT01), despues `validate_card.py`, y despues otro con
`plugins/planning-pipeline/agents/card-inspection.md` con la tarjeta y la fuente.

## Criterio de aprobacion

**La tarjeta** (card-authoring) tiene que:

- Preguntar, con su `default_assumption`, como se identifica al socio para darlo de
  baja: la fuente nunca lo dice y la operacion no se puede escribir sin eso.
- Preguntar si el email se normaliza (mayusculas, espacios) y si la unicidad alcanza a
  los socios inactivos.
- Preguntar quien esta autorizado a dar de alta y a dar de baja.
- Dejar afuera, explicito, lo que no esta en el pedido (persistencia, reactivacion,
  edicion, filtros del listado).
- No inventar campos del socio mas alla de nombre y email.

**La inspeccion** (card-inspection) tiene que encontrar, como minimo:

- `CARD-INSP-002`, **persistencia**: el pedido da el historial de fin de anio como la
  razon de no borrar socios, asi que mandar la persistencia a `out_of_scope` contradice
  el motivo del requisito. En la corrida real esto aparecio recien al final de la
  promocion, cuando ya estaba construido.
- `CARD-INSP-002` / `CARD-INSP-003`, **casos de borde de la baja**: que pasa al dar de
  baja a alguien que no existe, o que ya esta inactivo. En la corrida real el
  implementador los decidio solo.
- `CARD-INSP-003`, **regla con criterios solo del camino feliz**.

Lo que **no** tiene que reportar como silencio: identidad, normalizacion y
autorizacion, si la tarjeta ya las pregunto. Reportar una pregunta existente como
silencio es un falso positivo y le quita valor a la inspeccion.

## Linea de base

- **2026-09-25** (rama `feature/tarjeta-camino-rapido`): la inspeccion dio 4 high y 3
  medium, y encontro los tres items de arriba. No marco como silencio ninguna de las
  tres preguntas que la tarjeta ya tenia. Ademas encontro dos cosas que no estaban en
  el criterio: "con su estado" en el listado como inferencia no declarada, y dos
  terminos del dominio (historial, estadisticas de fin de anio) sin glosa en el
  vocabulario.
