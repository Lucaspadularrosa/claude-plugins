---
description: "Arranca aca si tenes documentos del cliente, una carpeta de material, o solo la idea. Lee lo que le des (o te entrevista si no hay nada escrito) y arma el mapa de lo que el producto tiene que hacer, con las features priorizadas por valor. Barato y a lo ancho, sin meterse en detalle. Re-ejecutable cada vez que llega material nuevo."
argument-hint: "[rutas a documentos o carpetas; vacio para arrancar sin documento]"
---

Ejecuta el modo DESCUBRIR de la skill `requirements-pipeline` sobre: `$ARGUMENTS`

Segui la skill tal cual (version del pipeline por script, extraccion, intake en
paralelo por fuente, LEL, inspeccion por script + juicio, cuestionario y mapa en
paralelo, PAUSA obligatoria con mis respuestas, cierre por script). Si no di ninguna
ruta, arrancamos sin documento: pedime la vision y guardala como fuente. Al cerrar,
mostrame `product-map.md` y tu sugerencia de que elaborar primero.
