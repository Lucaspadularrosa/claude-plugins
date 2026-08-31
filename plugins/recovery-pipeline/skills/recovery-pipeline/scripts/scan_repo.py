#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Esqueleto determinista del inventario: repo -> code-inventory.skeleton.json.

Todo lo que en el inventario es globs, greps contables y `git log` lo calcula este
script sin tokens: manifiestos y lockfiles (stack con evidencia), layout de primer
nivel con conteos, candidatos a entry points por patron de framework, presencia de
tests, LOC estimadas, TODO/FIXME, archivos enormes y señales de git. El agente
`code-inventory` (haiku) parte de este esqueleto y rellena SOLO lo semantico:
`responsibility` de cada modulo, `description` de cada entry point, servicios
externos, contradicciones con la doc y preguntas abiertas.

El conteo de entry points que imprime es exacto: es el disparador del particionado
en tandas de `behavior-extraction` (el umbral ya no lo estima un modelo a ojo).

Nunca lee `.env` reales ni copia valores: solo nombres de archivos y patrones.
Solo stdlib, Python 3.8+. Solo lectura sobre el repo.

Uso:
  python scan_repo.py [raiz] [--salida ARCHIVO] [--json]
  python scan_repo.py --self-test

  raiz      por defecto el directorio actual
  --salida  por defecto <raiz>/.dev/recovery/code-inventory.skeleton.json

Salida: la ruta escrita y una linea con lenguaje, frameworks, entry points exactos,
tests y LOC. Exit 1 ante error de IO.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

IGNORE_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt", "target", "__pycache__",
               ".venv", "venv", "env", ".dev", "coverage", ".cache", ".idea", ".vscode", "bin", "obj", ".terraform"}
MANIFESTS = [
    ("package.json", "javascript", "backend|frontend"), ("composer.json", "php", "backend"),
    ("pyproject.toml", "python", "backend"), ("requirements.txt", "python", "backend"), ("Pipfile", "python", "backend"),
    ("go.mod", "go", "backend"), ("Gemfile", "ruby", "backend"), ("pom.xml", "java", "backend"),
    ("build.gradle", "java", "backend"), ("build.gradle.kts", "kotlin", "backend"), ("Cargo.toml", "rust", "backend"),
    ("mix.exs", "elixir", "backend"), ("pubspec.yaml", "dart", "frontend"),
]
LOCKFILES = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "composer.lock", "poetry.lock",
             "Pipfile.lock", "uv.lock", "go.sum", "Gemfile.lock", "Cargo.lock", "mix.lock"]
CONFIG_SIGNALS = [
    ("docker-compose.yml", "infra", "docker-compose"), ("docker-compose.yaml", "infra", "docker-compose"), ("Dockerfile", "infra", "docker"),
    (".github/workflows", "infra", "github-actions"), (".gitlab-ci.yml", "infra", "gitlab-ci"),
    ("prisma/schema.prisma", "database", "prisma"), ("drizzle.config.ts", "database", "drizzle"), ("knexfile.js", "database", "knex"),
    ("alembic.ini", "database", "alembic"), ("db/schema.rb", "database", "activerecord"), ("migrations", "database", "migraciones"),
    ("jest.config.js", "testing", "jest"), ("jest.config.ts", "testing", "jest"), ("vitest.config.ts", "testing", "vitest"),
    ("pytest.ini", "testing", "pytest"), ("phpunit.xml", "testing", "phpunit"), ("playwright.config.ts", "testing", "playwright"),
    ("cypress.config.js", "testing", "cypress"), ("next.config.js", "frontend", "next"), ("next.config.mjs", "frontend", "next"),
    ("nuxt.config.ts", "frontend", "nuxt"), ("vite.config.ts", "frontend", "vite"), ("angular.json", "frontend", "angular"),
    ("artisan", "backend", "laravel"), ("manage.py", "backend", "django"), ("config/routes.rb", "backend", "rails"),
]
DEP_FRAMEWORKS = {
    "express": "express", "fastify": "fastify", "koa": "koa", "@nestjs/core": "nestjs", "next": "next", "react": "react",
    "vue": "vue", "nuxt": "nuxt", "svelte": "svelte", "@angular/core": "angular", "hono": "hono", "prisma": "prisma",
    "@prisma/client": "prisma", "mongoose": "mongoose", "sequelize": "sequelize", "typeorm": "typeorm", "knex": "knex",
    "jest": "jest", "vitest": "vitest", "mocha": "mocha", "django": "django", "flask": "flask", "fastapi": "fastapi",
    "sqlalchemy": "sqlalchemy", "pytest": "pytest", "laravel/framework": "laravel", "symfony/framework-bundle": "symfony",
    "rails": "rails", "sinatra": "sinatra", "gin-gonic/gin": "gin", "gorilla/mux": "gorilla", "labstack/echo": "echo",
    "actix-web": "actix", "axum": "axum", "rocket": "rocket",
}
CODE_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".php", ".rb", ".go", ".java", ".kt", ".rs", ".ex", ".exs",
            ".cs", ".swift", ".dart", ".vue", ".svelte"}
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e)(/|$)|\.(test|spec)\.[a-z]+$|_test\.(go|py|rb|php)$|test_[^/]+\.py$", re.I)
ROUTE_PATTERNS = [
    ("http_route", re.compile(r"\b(?:app|router|server|fastify|api)\.(get|post|put|patch|delete|all|route)\(\s*['\"`]([^'\"`]+)")),
    ("http_route", re.compile(r"@(?:app|router|bp|blueprint|api)\.(?:route|get|post|put|patch|delete)\(\s*['\"]([^'\"]+)")),
    ("http_route", re.compile(r"\b(?:Route|\$router|\$app)::(get|post|put|patch|delete|any|resource|apiResource|match)\(\s*['\"]([^'\"]+)")),
    ("http_route", re.compile(r"^\s*(get|post|put|patch|delete|resources?|namespace|scope)\s+['\":]([^'\",\s]+)", re.M)),
    ("http_route", re.compile(r"\b(?:path|re_path|url)\(\s*r?['\"]([^'\"]*)")),
    ("http_route", re.compile(r"\b(?:HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\(\s*\"([^\"]+)")),
    ("http_route", re.compile(r"@(Get|Post|Put|Patch|Delete|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)\(\s*['\"]?([^'\")]*)")),
]
CLI_PATTERNS = [re.compile(r"\.command\(\s*['\"]([^'\"]+)"), re.compile(r"add_parser\(\s*['\"]([^'\"]+)"), re.compile(r"@click\.command\(\)")]
JOB_PATTERNS = [re.compile(r"\b(?:cron|schedule|setInterval|Bull|Queue|worker|celery\.task|@task|sidekiq|ActiveJob)\b", re.I)]
PAGE_DIRS = ("pages", "app", "src/pages", "src/app", "src/routes", "routes", "resources/views", "templates")


def iter_files(root):
    for p in root.rglob("*"):
        if any(part in IGNORE_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            yield p


def read_text(p, limit=400_000):
    try:
        if p.stat().st_size > limit:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel(root, p):
    return str(p.relative_to(root)).replace("\\", "/")


def detect_stack(root):
    stack, langs, frameworks = [], {}, []
    for name, lang, layer in MANIFESTS:
        p = root / name
        if p.exists():
            langs[lang] = langs.get(lang, 0) + 1
            stack.append({"layer": layer.split("|")[0], "technology": lang, "version": "", "evidence": name})
            text = read_text(p)
            if name == "package.json":
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {}
                deps = {}
                for key in ("dependencies", "devDependencies"):
                    deps.update(data.get(key) or {})
                for dep, fw in DEP_FRAMEWORKS.items():
                    if dep in deps and fw not in frameworks:
                        frameworks.append(fw)
                        stack.append({"layer": "testing" if fw in ("jest", "vitest", "mocha") else "backend", "technology": fw, "version": str(deps[dep]), "evidence": "package.json"})
                if "typescript" in deps:
                    langs["typescript"] = langs.get("typescript", 0) + 1
            else:
                low = text.lower()
                for dep, fw in DEP_FRAMEWORKS.items():
                    if dep in low and fw not in frameworks:
                        frameworks.append(fw)
                        stack.append({"layer": "backend", "technology": fw, "version": "", "evidence": name})
    lockfiles = [l for l in LOCKFILES if (root / l).exists()]
    for path, layer, tech in CONFIG_SIGNALS:
        if (root / path).exists():
            stack.append({"layer": layer, "technology": tech, "version": "", "evidence": path})
            if layer in ("backend", "frontend") and tech not in frameworks:
                frameworks.append(tech)
    return stack, langs, frameworks, lockfiles


def scan_code(root):
    files = list(iter_files(root))
    code_files = [p for p in files if p.suffix.lower() in CODE_EXT]
    loc, todos, big, tests = 0, 0, [], 0
    ext_count = {}
    entry_points = []
    seen = set()
    for p in code_files:
        r = rel(root, p)
        ext_count[p.suffix.lower()] = ext_count.get(p.suffix.lower(), 0) + 1
        if TEST_RE.search(r):
            tests += 1
        text = read_text(p)
        lines = text.count("\n") + (1 if text else 0)
        loc += lines
        todos += len(re.findall(r"\b(TODO|FIXME|HACK|XXX)\b", text))
        if lines > 800:
            big.append({"path": r, "lines": lines})
        if TEST_RE.search(r):
            continue
        for kind, rx in ROUTE_PATTERNS:
            for m in rx.finditer(text):
                groups = [g for g in m.groups() if g]
                route = groups[-1] if groups else ""
                method = groups[0].upper() if len(groups) > 1 else ""
                path_label = ("%s %s" % (method, route)).strip()
                key = (kind, path_label, r)
                if key in seen or not route:
                    continue
                seen.add(key)
                line = text.count("\n", 0, m.start()) + 1
                entry_points.append({"kind": kind, "path": path_label, "evidence": "%s:%d" % (r, line)})
        for rx in CLI_PATTERNS:
            for m in rx.finditer(text):
                name = m.group(1) if m.groups() else p.stem
                key = ("cli", name, r)
                if key in seen:
                    continue
                seen.add(key)
                entry_points.append({"kind": "cli", "path": name, "evidence": "%s:%d" % (r, text.count("\n", 0, m.start()) + 1)})
        for rx in JOB_PATTERNS:
            m = rx.search(text)
            if m and ("job", r) not in seen:
                seen.add(("job", r))
                entry_points.append({"kind": "job", "path": r, "evidence": "%s:%d" % (r, text.count("\n", 0, m.start()) + 1)})
    for d in PAGE_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in {".tsx", ".jsx", ".vue", ".svelte", ".astro", ".blade.php", ".html"}:
                continue
            r = rel(root, p)
            if any(part in IGNORE_DIRS for part in p.relative_to(root).parts) or "components" in r:
                continue
            if p.stem in ("page", "index", "layout") or d.endswith("pages"):
                key = ("page", r)
                if key not in seen:
                    seen.add(key)
                    entry_points.append({"kind": "page", "path": r, "evidence": r})
    entry_points.sort(key=lambda e: (e["kind"], e["path"], e["evidence"]))
    for i, e in enumerate(entry_points, 1):
        e["id"] = "ENTRY-%03d" % i
        e["description"] = ""
    return {"files": len(files), "code_files": len(code_files), "loc": loc, "todos": todos, "big_files": sorted(big, key=lambda b: -b["lines"])[:10],
            "test_files": tests, "ext_count": ext_count, "entry_points": entry_points}


def layout(root):
    out = []
    for p in sorted(root.iterdir()):
        if p.name in IGNORE_DIRS or p.name.startswith("."):
            continue
        if p.is_dir():
            n = sum(1 for _ in iter_files(p))
            out.append({"path": p.name + "/", "purpose": "", "evidence": "%d archivos" % n})
    return out


def git_signals(root):
    def run(args):
        try:
            return subprocess.run(["git"] + args, cwd=str(root), capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    if not (root / ".git").exists():
        return {}
    commits = run(["rev-list", "--count", "HEAD"])
    last = run(["log", "-1", "--format=%cs"])
    first = run(["log", "--reverse", "--format=%cs", "--max-count=1"]) or run(["log", "--format=%cs"]).splitlines()[-1:] or ""
    if isinstance(first, list):
        first = first[0] if first else ""
    branches = run(["branch", "--list"]).count("\n") + (1 if run(["branch", "--list"]) else 0)
    return {"commits": int(commits) if commits.isdigit() else None, "first_commit": first, "last_commit": last, "branches": branches}


def build(root):
    stack, langs, frameworks, lockfiles = detect_stack(root)
    code = scan_code(root)
    primary = max(langs.items(), key=lambda kv: kv[1])[0] if langs else (max(code["ext_count"].items(), key=lambda kv: kv[1])[0].lstrip(".") if code["ext_count"] else "desconocido")
    ratio = code["test_files"] / code["code_files"] if code["code_files"] else 0
    test_presence = "none" if code["test_files"] == 0 else "sparse" if ratio < 0.1 else "moderate" if ratio < 0.3 else "extensive"
    docs = [n for n in ("README.md", "CLAUDE.md", "docs") if (root / n).exists()]
    health = []
    if code["test_files"] == 0:
        health.append({"signal": "No hay archivos de test", "severity": "warning", "evidence": "0 archivos con patron de test sobre %d de codigo" % code["code_files"]})
    if code["todos"] > 20:
        health.append({"signal": "%d TODO/FIXME/HACK en el codigo" % code["todos"], "severity": "warning", "evidence": "grep sobre archivos de codigo"})
    for b in code["big_files"][:5]:
        health.append({"signal": "Archivo enorme (%d lineas)" % b["lines"], "severity": "warning", "evidence": b["path"]})
    if not lockfiles and langs:
        health.append({"signal": "Sin lockfile: dependencias no fijadas", "severity": "warning", "evidence": "sin %s" % ", ".join(LOCKFILES[:4])})
    if (root / ".env").exists() and not (root / ".env.example").exists():
        health.append({"signal": ".env presente sin .env.example (no se leyo su contenido)", "severity": "info", "evidence": ".env"})
    git = git_signals(root)
    if git.get("commits") is not None:
        health.append({"signal": "Git: %s commits, primero %s, ultimo %s, %s ramas" % (git["commits"], git.get("first_commit") or "?", git.get("last_commit") or "?", git.get("branches")), "severity": "info", "evidence": "git log"})
    return {
        "version": 0,
        "metadata": {"created_at": None, "updated_at": None, "repo_root": str(root), "pipeline_version": None, "skeleton_by": "scan_repo"},
        "summary": {"primary_language": primary, "frameworks": frameworks, "loc_estimate": "~%d lineas en %d archivos de codigo" % (code["loc"], code["code_files"]),
                    "test_presence": test_presence, "docs_presence": "none" if not docs else "partial", "entry_point_count": len(code["entry_points"]),
                    "test_file_count": code["test_files"], "todo_count": code["todos"], "lockfiles": lockfiles},
        "stack": stack,
        "layout": layout(root),
        "entry_points": code["entry_points"],
        "modules": [],
        "data_stores": [],
        "external_services": [],
        "health_signals": health,
        "doc_contradictions": [],
        "open_questions": [],
        "warnings": ["Esqueleto generado por scan_repo.py: modulos, servicios externos, descripciones de entry points y contradicciones con la doc los completa el agente code-inventory."],
    }


def self_test():
    import tempfile

    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.18.0", "mongoose": "7"}, "devDependencies": {"jest": "29"}}), encoding="utf-8")
        (root / "package-lock.json").write_text("{}", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.js").write_text("const app = require('express')();\napp.get('/users', h);\napp.post('/users', h);\n// TODO x\n", encoding="utf-8")
        (root / "src" / "jobs.js").write_text("setInterval(tick, 1000);\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "x.js").write_text("app.get('/ignored', h)", encoding="utf-8")
        inv = build(root)
        checks.append(("lenguaje", inv["summary"]["primary_language"] == "javascript"))
        checks.append(("frameworks", "express" in inv["summary"]["frameworks"] and "jest" in inv["summary"]["frameworks"]))
        eps = inv["entry_points"]
        checks.append(("2 rutas + 1 job", inv["summary"]["entry_point_count"] == 3 and sum(1 for e in eps if e["kind"] == "http_route") == 2))
        checks.append(("ids consecutivos", [e["id"] for e in eps] == ["ENTRY-001", "ENTRY-002", "ENTRY-003"]))
        checks.append(("node_modules ignorado", not any("ignored" in e["path"] for e in eps)))
        checks.append(("sin tests -> señal", inv["summary"]["test_presence"] == "none" and any("test" in h["signal"].lower() for h in inv["health_signals"])))
        checks.append(("lockfile detectado", inv["summary"]["lockfiles"] == ["package-lock.json"]))
        checks.append(("determinista", json.dumps(build(root), sort_keys=True) == json.dumps(inv, sort_keys=True)))
    failed = [n for n, ok in checks if not ok]
    if failed:
        print("self-test FALLO: %s" % failed)
        return 1
    print("self-test OK (%d checks)" % len(checks))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raiz", nargs="?", default=".")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    root = Path(args.raiz).resolve()
    if not root.is_dir():
        print("error: no existe %s" % root)
        return 1
    inv = build(root)
    out = Path(args.salida) if args.salida else root / ".dev" / "recovery" / "code-inventory.skeleton.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(inv, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        print("error: %s" % e)
        return 1
    s = inv["summary"]
    print("esqueleto: %s" % out)
    print("lenguaje %s; frameworks %s; entry_points %d; tests %s (%d archivos); %s; todos %d" % (
        s["primary_language"], ", ".join(s["frameworks"]) or "-", s["entry_point_count"], s["test_presence"], s["test_file_count"], s["loc_estimate"], s["todo_count"]))
    if args.json:
        print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
