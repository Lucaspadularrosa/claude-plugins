#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render determinista del manual de usuario: docs/usuario/*.md -> sitio HTML estatico.

Toma las guias Markdown que escribe el build-pipeline (user-docs-writer) y las
convierte en un sitio navegable offline: una pagina por guia + index.html.
Mismo input -> mismo sitio; sin tokens de modelo, sin red, sin dependencias.

Seguridad por construccion: TODO el texto crudo se escapa (html.escape) antes de
aplicar el formato inline. HTML embebido en un .md (un <script>, un iframe) sale
como texto visible, jamas como markup. Los links y las imagenes externas (http/https)
se neutralizan a texto plano: el sitio no hace ningun request externo.

Markdown soportado (el subconjunto que el user-docs-writer emite): frontmatter
plano, encabezados #..######, parrafos, listas - / 1. (dos niveles), tablas,
blockquotes, cercas de codigo, hr, y en linea: **negrita**, *cursiva*, `codigo`,
[links](relativos.md) e ![imagenes](relativas).

Solo stdlib, Python 3.8+. No modifica los .md.

Uso:
  python render_manual.py [carpeta-md] [--salida DIR] [--titulo "Nombre"] [--acento "#0a7d55"]
  python render_manual.py --self-test

  carpeta-md  por defecto docs/usuario
  --salida    por defecto {carpeta-md}/html
  index.html  sale de README.md (el indice derivado del build) si existe;
              si no, se sintetiza desde el frontmatter de las guias.

Salida: paginas generadas y avisos (recursos externos neutralizados). Exit 1 solo
ante errores de IO o self-test fallido.
"""

import argparse
import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- frontmatter


def parse_frontmatter(text):
    """Frontmatter YAML plano (clave: valor escalar). Devuelve (dict, resto)."""
    meta = {}
    if not text.startswith("---"):
        return meta, text
    lines = text.split("\n")
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip("\"'")
    if end is None:
        return {}, text
    return meta, "\n".join(lines[end + 1:])


# ------------------------------------------------------------------- inline

_EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")  # http:, https:, mailto:, etc.


def _rewrite_href(href, avisos):
    """Links relativos: .md -> .html (README -> index). Externos: None (neutralizar)."""
    if _EXTERNAL.match(href) or href.startswith("//"):
        avisos.append("link externo neutralizado: %s" % href)
        return None
    base, _, anchor = href.partition("#")
    if base.lower() == "readme.md":
        base = "index.html"
    elif base.lower().endswith(".md"):
        base = base[:-3] + ".html"
    return base + ("#" + anchor if anchor else "")


def render_inline(text, avisos):
    """Formato inline sobre texto YA escapado. El orden importa: codigo primero."""
    out = []
    # los code spans se procesan aparte para que nada mas los toque
    for i, part in enumerate(re.split(r"`([^`]+)`", text)):
        if i % 2 == 1:
            out.append("<code>%s</code>" % part)
            continue
        # imagenes antes que links (comparten sintaxis)
        def img(m):
            alt, src = m.group(1), m.group(2)
            if _EXTERNAL.match(src) or src.startswith("//"):
                avisos.append("imagen externa omitida: %s" % src)
                return alt
            return '<img src="../%s" alt="%s">' % (src, alt)

        def link(m):
            label, href = m.group(1), m.group(2)
            new = _rewrite_href(href, avisos)
            if new is None:
                return label
            return '<a href="%s">%s</a>' % (new, label)

        part = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", img, part)
        part = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, part)
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", part)
        out.append(part)
    return "".join(out)


# -------------------------------------------------------------------- blocks


def render_markdown(md, avisos):
    """Markdown (subconjunto) -> HTML. Todo el texto pasa por html.escape."""
    lines = md.split("\n")
    out = []
    i = 0
    para = []

    def flush_para():
        if para:
            out.append("<p>%s</p>" % render_inline(html.escape(" ".join(para)), avisos))
            del para[:]

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_para()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
            i += 1
            continue

        if not stripped:
            flush_para()
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>"
                       % (level, render_inline(html.escape(m.group(2)), avisos), level))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush_para()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote><p>%s</p></blockquote>"
                       % render_inline(html.escape(" ".join(quote)), avisos))
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            table = ["<table>"]
            body_rows = rows
            if len(rows) >= 2 and all(re.match(r"^:?-+:?$", c) for c in rows[1] if c):
                table.append("<thead><tr>%s</tr></thead>" % "".join(
                    "<th>%s</th>" % render_inline(html.escape(c), avisos) for c in rows[0]))
                body_rows = rows[2:]
            table.append("<tbody>")
            for r in body_rows:
                table.append("<tr>%s</tr>" % "".join(
                    "<td>%s</td>" % render_inline(html.escape(c), avisos) for c in r))
            table.append("</tbody></table>")
            out.append("".join(table))
            continue

        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            flush_para()
            i = _render_list(lines, i, out, avisos, indent=_indent_of(line))
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out)


def _indent_of(line):
    return len(line) - len(line.lstrip(" "))


def _render_list(lines, i, out, avisos, indent):
    """Lista (dos niveles via indentacion). Devuelve el indice siguiente."""
    ordered = bool(re.match(r"^\s*\d+\.\s+", lines[i]))
    tag = "ol" if ordered else "ul"
    out.append("<%s>" % tag)
    item_open = False
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if not m:
            # continuacion de item (linea indentada) o fin de la lista
            if line.strip() and _indent_of(line) > indent and item_open:
                out.append(" " + render_inline(html.escape(line.strip()), avisos))
                i += 1
                continue
            break
        cur = len(m.group(1))
        if cur > indent:
            i = _render_list(lines, i, out, avisos, indent=cur)
            continue
        if cur < indent:
            break
        if item_open:
            out.append("</li>")
        out.append("<li>%s" % render_inline(html.escape(m.group(3)), avisos))
        item_open = True
        i += 1
    if item_open:
        out.append("</li>")
    out.append("</%s>" % tag)
    return i


# ------------------------------------------------------------------- pagina

_CSS = """
:root {
  --fondo: #f6f7f9; --superficie: #ffffff; --acento: %(acento)s;
  --texto: #1c2430; --texto-suave: #5b6673; --borde: #e3e7ec;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--fondo); color: var(--texto);
  font: 16px/1.65 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
header.sitio {
  background: var(--superficie); border-bottom: 2px solid var(--acento);
  padding: 0.9rem 1.2rem;
}
header.sitio a { color: var(--texto-suave); text-decoration: none; font-size: 0.9rem; }
header.sitio a:hover { color: var(--acento); }
header.sitio .producto { font-weight: 700; color: var(--texto); margin-right: 0.75rem; }
main {
  max-width: 46rem; margin: 1.5rem auto 3rem; background: var(--superficie);
  border: 1px solid var(--borde); border-radius: 10px; padding: 2rem 2.4rem;
}
h1 { margin-top: 0; font-size: 1.7rem; }
h2 { font-size: 1.25rem; border-bottom: 1px solid var(--borde); padding-bottom: 0.3rem; }
a { color: var(--acento); }
code {
  background: var(--fondo); border: 1px solid var(--borde); border-radius: 4px;
  padding: 0.1em 0.35em; font-size: 0.92em;
}
pre { background: var(--fondo); border: 1px solid var(--borde); border-radius: 8px;
      padding: 0.9rem 1rem; overflow-x: auto; }
pre code { background: none; border: none; padding: 0; }
table { border-collapse: collapse; width: 100%%; margin: 1rem 0; }
th, td { border: 1px solid var(--borde); padding: 0.5rem 0.7rem; text-align: left; }
th { background: var(--fondo); }
blockquote { border-left: 3px solid var(--acento); margin: 1rem 0; padding: 0.2rem 1rem;
             color: var(--texto-suave); }
img { max-width: 100%%; }
footer.sitio { text-align: center; color: var(--texto-suave); font-size: 0.85rem;
               margin: 2rem 0; }
.resumen { color: var(--texto-suave); }
@media (max-width: 40rem) { main { margin: 0; border-radius: 0; padding: 1.2rem; } }
"""

_PAGE = """<!doctype html>
<html lang="%(lang)s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(titulo)s — %(producto)s</title>
<style>%(css)s</style>
</head>
<body>
<header class="sitio"><span class="producto">%(producto)s</span>%(nav)s</header>
<main>
%(cuerpo)s
</main>
<footer class="sitio">Manual de usuario — generado desde docs/usuario</footer>
</body>
</html>
"""


def build_page(titulo, producto, cuerpo, css, is_index, lang="es"):
    nav = "" if is_index else '<a href="index.html">&larr; Índice del manual</a>'
    return _PAGE % {
        "titulo": html.escape(titulo), "producto": html.escape(producto),
        "css": css, "nav": nav, "cuerpo": cuerpo, "lang": lang,
    }


# --------------------------------------------------------------------- main


def render_site(src_dir, out_dir, producto, acento):
    src = Path(src_dir)
    if not src.is_dir():
        print("No existe la carpeta de guias: %s" % src)
        return 1
    mds = sorted(p for p in src.glob("*.md") if p.name.lower() != "readme.md")
    readme = next((p for p in src.glob("*.md") if p.name.lower() == "readme.md"), None)
    if not mds and readme is None:
        print("Sin guias .md en %s — nada que publicar." % src)
        return 1

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    css = _CSS % {"acento": acento}
    avisos = []
    metas = []

    for page in mds:
        meta, body = parse_frontmatter(page.read_text(encoding="utf-8"))
        titulo = meta.get("titulo") or page.stem
        metas.append({"archivo": page.stem + ".html", "titulo": titulo,
                      "resumen": meta.get("resumen", "")})
        cuerpo = render_markdown(body, avisos)
        dest = out / (page.stem + ".html")
        dest.write_text(build_page(titulo, producto, cuerpo, css, is_index=False),
                        encoding="utf-8")
        print("pagina: %s" % dest)

    if readme is not None:
        _, body = parse_frontmatter(readme.read_text(encoding="utf-8"))
        cuerpo = render_markdown(body, avisos)
    else:
        items = "\n".join(
            '<li><a href="%s">%s</a><br><span class="resumen">%s</span></li>'
            % (html.escape(m["archivo"]), html.escape(m["titulo"]),
               html.escape(m["resumen"]))
            for m in metas)
        cuerpo = "<h1>%s — Manual de usuario</h1>\n<ul>\n%s\n</ul>" % (
            html.escape(producto), items)
    (out / "index.html").write_text(
        build_page("Manual de usuario", producto, cuerpo, css, is_index=True),
        encoding="utf-8")
    print("indice: %s" % (out / "index.html"))

    for a in sorted(set(avisos)):
        print("aviso: %s" % a)
    print("Listo: %d guia(s) + indice en %s" % (len(mds), out))
    return 0


def self_test():
    avisos = []
    md = "\n".join([
        "## Hola *mundo*",
        "",
        "Texto con **negrita**, `codigo` y un <script>alert(1)</script> embebido.",
        "",
        "- item uno",
        "- item [guia](otra-guia.md)",
        "",
        "| Col | Val |",
        "|---|---|",
        "| a | b |",
        "",
        "[externo](https://example.invalid/x) y ![pixel](https://example.invalid/p.gif)",
    ])
    out = render_markdown(md, avisos)
    checks = [
        ("<h2>Hola <em>mundo</em></h2>" in out, "encabezado + cursiva"),
        ("&lt;script&gt;" in out and "<script>" not in out, "HTML embebido escapado"),
        ('<a href="otra-guia.html">guia</a>' in out, "link .md reescrito a .html"),
        ("<strong>negrita</strong>" in out, "negrita"),
        ("<th>Col</th>" in out and "<td>a</td>" in out, "tabla"),
        ('href="https://' not in out and "<img" not in out, "externos neutralizados"),
        (len([a for a in avisos if "externo" in a or "externa" in a]) == 2, "avisos de externos"),
    ]
    ok = True
    for passed, name in checks:
        print("%s %s" % ("ok " if passed else "FALLO", name))
        ok = ok and passed
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default="docs/usuario",
                    help="carpeta con las guias .md (default: docs/usuario)")
    ap.add_argument("--salida", default=None, help="carpeta de salida (default: {carpeta}/html)")
    ap.add_argument("--titulo", default="Manual de usuario", help="nombre del producto")
    ap.add_argument("--acento", default="#0a7d55", help="color de acento CSS")
    ap.add_argument("--self-test", action="store_true", help="corre el self-test y sale")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    out_dir = args.salida or str(Path(args.carpeta) / "html")
    return render_site(args.carpeta, out_dir, args.titulo, args.acento)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
