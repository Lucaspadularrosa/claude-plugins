---
description: "Dice en que estado esta la suite en este proyecto: que pipelines corrieron, que features estan en cada etapa, que bloquea y que conviene hacer. Solo lectura, cero tokens de modelo."
argument-hint: "[opcional: ruta al proyecto]"
---

Estado de la suite para: `$ARGUMENTS`

Corre el script y mostra su salida tal cual:

```bash
suite-status "${ARGUMENTS:-.}/.dev"
```

Reglas:

- **No leas los artefactos vos**. El script ya cruza `product-map.json`,
  `tasks.json`, `progress.json` y `changelog.json`. Leerlos a mano gasta contexto
  y puede contradecirlo.
- **`Sugerido` es una recomendacion, no un enrutado**. Se deriva de condiciones
  verificables sobre los artefactos, pero no sabe que quiere hacer el usuario.
  Mostrala y ofrecela; no lances el comando sugerido sin que te lo pidan.
- Si el usuario pregunta por un bloqueo puntual, `suite-status --json` trae el
  detalle por feature (`features[]`) y los ids involucrados.
- Si el comando no existe, el plugin `requerimientos` no esta instalado: decilo y
  no intentes reemplazarlo leyendo los artefactos a mano.
