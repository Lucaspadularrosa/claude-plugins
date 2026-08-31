---
name: manual-usuario
description: Publica el manual de usuario (.dev/manual/*.md del build-pipeline) como sitio HTML estatico offline en docs/manual/, con render determinista por script. Usar cuando el usuario quiere publicar, exportar o regenerar el manual de usuario en HTML.
---

# Manual de usuario — publicacion HTML

Convierte las guias Markdown de `.dev/manual/` en un sitio HTML estatico en
`docs/manual/` (una pagina por guia + `index.html`). Todo lo hace el script
`render_manual.py`: cobertura, titulo y render son deterministas, cero tokens. Vos
solo interpretas su stdout y hablas con el usuario (el por que del diseño y la
seguridad del render estan en el README del plugin).

## Procedimiento

1. **Cobertura** (sin leer ningun archivo):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/manual-usuario/scripts/render_manual.py" --solo-cobertura
```

   (si `python3` no existe: `python`, despues `py -3`; si `${CLAUDE_PLUGIN_ROOT}`
   no esta definida, ubica el script dentro del plugin `manual-usuario` instalado).
   Imprime `cobertura: completa|parcial` y, si es parcial, que falta:
   - `done sin guia`: docs best-effort que fallaron o features sin superficie de
     usuario; sugeri **`/documentar`** (build-pipeline) para generarlas.
   - `guias de features no done`: estas publicando desde una rama con trabajo sin
     mergear.
   - `features pendientes`: el plan no termino; el manual saldria incompleto.
   - `sin progress.json`: proyecto fuera de la suite; anotalo y segui.

   Si no hay guias (`Sin guias .md`), explicale al usuario que el manual lo escribe el
   build (`/construir` / `/construir-lote`) y no hay nada que publicar todavia.
   Con cobertura completa (exit 0), segui sin preguntar. Con parcial (exit 2), mostra
   el estado tal cual lo imprimio el script y **pregunta si publicar igual**: un
   manual parcial es valido, pero se publica a sabiendas.

2. **Render**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/manual-usuario/scripts/render_manual.py" --titulo-auto
```

   `--titulo "Nombre"` solo si el usuario dijo el nombre del producto (si no,
   `--titulo-auto` lo saca del product-map o del repo); `--acento "#rrggbb"` si pidio
   color de marca; `--salida DIR` para otra carpeta. Por defecto lee `.dev/manual/`
   y publica en `docs/manual/`.

3. **Cierre**: mostra el conteo de paginas, donde quedo `index.html`, la cobertura
   del paso 1 y los **avisos** del script (links o imagenes externas neutralizadas:
   vienen del Markdown y pueden ameritar corregir la guia). Sugeri abrir
   `docs/manual/index.html`. Si el usuario quiere versionarlo, commit aparte
   (`docs: manual de usuario publicado en HTML`); si el proyecto sirve estaticos,
   ofrece copiarlo ahi preguntando antes.

## Reglas

- No leas las guias ni `progress.json` ni `product-map.json`: el script ya los cruzo.
- No edites los `.md` de `.dev/manual/` (son del build-pipeline) ni el HTML generado
  (es derivado y se regenera entero). Ajustes estables van al script o a las guias.
- El render es fiel: los avisos de recursos externos se muestran siempre.
