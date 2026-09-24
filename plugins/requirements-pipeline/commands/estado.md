---
description: "Dice en que estado esta la suite en este proyecto: que pipelines corrieron, que features estan en cada etapa, que bloquea y que conviene hacer. Tambien enruta: contale que queres hacer y te dice por donde. Solo lectura."
argument-hint: "[ruta al proyecto] [o contame que queres hacer, entre comillas]"
---

Estado de la suite para: `$ARGUMENTS`

Corre el script y mostra su salida tal cual (si `$ARGUMENTS` es una intencion en
texto y no una ruta, corre el script sobre `.`):

```bash
suite-status "${ARGUMENTS:-.}/.dev"
```

**Si ademas te dije que quiero hacer** ("necesito sacar el alta de proveedores
hoy", "quiero documentar lo que construimos la semana pasada"), cruza eso con la
salida del script y recomendame un comando, con una linea de por que. El `Sugerido`
del script sale solo del estado de los artefactos: no sabe lo que quiero. Para
enrutar usa la tabla de triage de la skill `requirements-pipeline` (seccion "Por
donde empezar"), incluidas sus contraindicaciones: si lo que pido es urgente pero
toca el modelo de datos central o son varias features, decimelo y recomendame el
ciclo formal igual.

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
