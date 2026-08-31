# Manual de Usuario — Plugin de Claude Code

Plugin que **publica el manual de usuario** de un producto construido con la suite:
toma las guias Markdown que el `build-pipeline` va escribiendo en `.dev/manual/`
(una por feature, mas el indice derivado `README.md`) y las convierte en un **sitio
HTML estatico navegable** en `docs/manual/`: una pagina por guia + `index.html`.

La division del trabajo es deliberada:

- **El Markdown es la fuente de verdad y vive en `.dev/`**, como todo artefacto de
  la suite. Lo escribe el `user-docs-writer` del build-pipeline dentro del PR de
  cada feature: diffeable, revisable, renderiza en GitHub. Este plugin no lo toca.
  Lo unico de cara al usuario final es la publicacion (`docs/manual/`).
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

## Cobertura antes de publicar

`render_manual.py --solo-cobertura` cruza las guias presentes (frontmatter `fg`)
contra `.dev/plan/progress.json` (si existe) e imprime el estado; el agente no
abre ninguna guia ni el plan. Con el plan completo y cada feature `done` con su
guia, `/publicar-manual` publica directo;
con huecos — features sin guia, features sin mergear, guias de trabajo no
integrado — muestra el estado y **pregunta antes de publicar**. Un manual parcial
es valido (crece con el producto, lote a lote), pero se publica a sabiendas, no
por accidente. Para features construidas antes de que el build documentara,
sugiere `/documentar` (build-pipeline), que genera las guias retroactivamente.

## Uso

```
/publicar-manual                     titulo derivado del product-map o del repo
/publicar-manual Club Deportivo Sur  titulo explicito del sitio
```

O directo, sin agente:

```bash
python plugins/manual-usuario/skills/manual-usuario/scripts/render_manual.py --solo-cobertura
python plugins/manual-usuario/skills/manual-usuario/scripts/render_manual.py \
  --titulo-auto --acento "#0a7d55"          # o --titulo "Mi Producto"
```

Flags: `--cobertura [progress.json]`, `--solo-cobertura` (exit 2 si es parcial),
`--titulo-auto` (product-map `project.name` o nombre del repo), `--verbose`
(lista cada pagina), `--self-test`.

Entrada (default): `.dev/manual/`. Salida (default): `docs/manual/` — `index.html`
(del `README.md` derivado del build, o sintetizado desde el frontmatter de las
guias) + una pagina por guia.

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

Guias en `.dev/manual/*.md` con frontmatter (`feature`, `fg`, `titulo`, `resumen`)
— las genera el `build-pipeline` en cada PR de feature. Sin guias no hay manual que
publicar.

## Cambios

- **1.1.0**: cobertura y titulo resueltos por el script (`--solo-cobertura`,
  `--titulo-auto`); el agente ya no lee guias, `progress.json` ni `product-map.json`.
  Salida por defecto sin listar paginas (`--verbose` para el detalle).
