---
name: manual-usuario
description: Publica el manual de usuario que el build-pipeline escribe en docs/usuario/ (guias Markdown por feature + indice) como un sitio HTML estatico navegable, offline y sin dependencias externas, con un render determinista por script. Usar cuando el usuario quiere publicar, exportar o entregar el manual de usuario en HTML, o regenerarlo porque hay guias nuevas.
---

# Manual de usuario — publicacion HTML

Esta skill convierte las guias Markdown de `docs/usuario/` (las escribe el
`user-docs-writer` del `build-pipeline`; el indice `README.md` lo deriva su
orquestador) en un **sitio HTML estatico**: una pagina por guia + `index.html`,
navegable offline, sin JavaScript ni requests externos.

La conversion NO la hace un agente: la hace un script **determinista** (mismo
Markdown -> mismo sitio, cero tokens). El script ademas escapa todo HTML embebido
y neutraliza links e imagenes externas: el sitio publicado no puede ejecutar nada
ni llamar afuera, venga lo que venga en los .md.

## Procedimiento

1. Verifica que exista `docs/usuario/` con al menos una guia `.md`. Si no hay,
   explicale al usuario que el manual lo va escribiendo el build
   (`/construir` / `/construir-lote` generan una guia por feature) y no hay nada
   que publicar todavia.
2. Determina el nombre del producto para el titulo del sitio: el que el usuario
   diga, o derivalo de `.dev/requirements/product-map.json` si existe (si no, del
   nombre del repo). Si el usuario pidio un color de marca, pasalo en `--acento`.
3. Corre el render:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/manual-usuario/scripts/render_manual.py" docs/usuario --titulo "{producto}"
```

   (Si `${CLAUDE_PLUGIN_ROOT}` no estuviera definida, ubica `render_manual.py`
   dentro del plugin `manual-usuario` instalado. Flags: `--salida DIR` para otra
   carpeta de salida — default `docs/usuario/html/` —, `--acento "#rrggbb"` para
   el color de marca.)

4. Mostra el resultado: cuantas paginas se generaron, donde quedo `index.html`, y
   los **avisos** del script si los hubo (links o imagenes externas neutralizadas:
   eso viene del Markdown y puede ameritar corregir la guia). Sugerile al usuario
   abrir `docs/usuario/html/index.html` en el navegador.
5. Si la salida quedo dentro del repo y el usuario quiere versionarla, commit
   aparte (`docs: manual de usuario publicado en HTML`); si el proyecto ya sirve
   estaticos (GitHub Pages, carpeta public del stack), ofrece copiarla ahi —
   preguntando antes, sin asumir el deploy.

## Reglas

- No edites los `.md` de `docs/usuario/` desde esta skill: la fuente de verdad es
  del build-pipeline. Si una guia esta mal, el arreglo va por
  `/construir` (correccion de la feature) o a mano en el PR de la guia — no en el
  HTML generado.
- No retoques el HTML generado a mano: es derivado; se regenera entero en cada
  corrida. Cualquier ajuste estable va en el script o en las guias.
- El render es fiel: si el script reporta avisos de recursos externos, mostralos —
  son senal de que una guia rompio la regla de autocontencion.
