# Manual de Usuario — Plugin de Claude Code

Plugin que **publica el manual de usuario** de un producto construido con la suite:
toma las guias Markdown que el `build-pipeline` va escribiendo en `docs/usuario/`
(una por feature, mas el indice derivado `README.md`) y las convierte en un **sitio
HTML estatico navegable**: una pagina por guia + `index.html`.

La division del trabajo es deliberada:

- **El Markdown es la fuente de verdad.** Lo escribe el `user-docs-writer` del
  build-pipeline dentro del PR de cada feature: diffeable, revisable, renderiza en
  GitHub. Este plugin no lo toca.
- **El HTML es una publicacion derivada.** La hace un script **determinista**
  (`render_manual.py`, solo stdlib de Python 3.8+): mismo Markdown -> mismo sitio,
  cero tokens de modelo, regenerable las veces que haga falta.

## Seguridad del render

El sitio publicado no puede ejecutar nada ni llamar afuera, venga lo que venga en
los `.md`:

- Todo HTML embebido en el Markdown se **escapa** (un `<script>` sale como texto
  visible, jamas como markup).
- Links e imagenes **externas** (http/https) se neutralizan a texto plano y se
  reportan como avisos: el sitio queda 100% offline, sin ningun request externo.
- Sin JavaScript: el sitio son paginas estaticas con CSS inline (variables CSS para
  la marca: `--acento` y compania).

Es el complemento mecanico de la frontera de confianza del `user-docs-writer`: aun
si una guia saliera contaminada, la publicacion no lo convierte en ejecucion.

## Uso

```
/publicar-manual                     titulo derivado del product-map o del repo
/publicar-manual Club Deportivo Sur  titulo explicito del sitio
```

O directo, sin agente:

```bash
python plugins/manual-usuario/skills/manual-usuario/scripts/render_manual.py docs/usuario \
  --titulo "Mi Producto" --acento "#0a7d55"
```

Salida (default): `docs/usuario/html/` — `index.html` (del `README.md` derivado del
build, o sintetizado desde el frontmatter de las guias) + una pagina por guia.

```
manual-usuario/
  .claude-plugin/plugin.json
  commands/publicar-manual.md        /publicar-manual [producto]
  skills/manual-usuario/
    SKILL.md                         orquestacion de la publicacion
    scripts/render_manual.py         render determinista (stdlib; --self-test incluido)
  README.md
```

## Que necesitas antes

Guias en `docs/usuario/*.md` con frontmatter (`feature`, `fg`, `titulo`, `resumen`)
— las genera el `build-pipeline` en cada PR de feature. Sin guias no hay manual que
publicar.
