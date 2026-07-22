---
description: Publica el manual de usuario (docs/usuario/*.md) como un sitio HTML estatico navegable, offline y sin dependencias, con render determinista por script.
argument-hint: "[opcional: nombre del producto para el titulo del sitio]"
---

Publica el manual de usuario en HTML. Producto: `$ARGUMENTS`

Segui la skill `manual-usuario`:

1. Verifica que `docs/usuario/` tenga guias `.md` (las escribe el build-pipeline);
   si no hay, decime que todavia no hay manual que publicar.
2. Usa como titulo del sitio el producto indicado, o derivalo del product-map / repo.
3. Corre `render_manual.py` del plugin (default: salida en `docs/usuario/html/`).
4. Mostrame cuantas paginas se generaron, donde quedo `index.html` y los avisos del
   script (recursos externos neutralizados) si los hubo.
