---
name: dev-toolkit:tech-docs
description: Generate technical documentation. Subcommands: internal (team Markdown docs), html (end-user HTML feature docs). Analyzes project structure to produce accurate, complete documentation.
allowed-tools: Bash, Read, Write, Glob, Grep
argument-hint: "internal | html [--output <dir>]"
---

# Technical Documentation Generator

## User Input

```
$ARGUMENTS
```

Parse the first word as the subcommand. Parse `--output <dir>` if present.

---

## Subcommand Dispatch

| Input | Action |
|-------|--------|
| `internal` | Generate internal team documentation (Markdown) |
| `html [--output <dir>]` | Generate end-user HTML documentation |
| *(anything else)* | Show usage help |

---

## Phase 0: Project Discovery (Both Subcommands)

Before generating any docs, understand the project:

1. Read `CLAUDE.md`, `README.md` (if they exist).
2. Read `package.json` / `pyproject.toml` / `pom.xml` / `go.mod` to identify the stack.
3. List key source directories: `src/`, `app/`, `lib/`, `api/`, `routes/`, `controllers/`, `services/`.
4. Identify the main entry points and architectural layers.

---

## Subcommand: `internal`

**Goal**: Generate comprehensive technical documentation for the development team.

### Steps

1. **Identify modules/features**: Using Glob and Grep, find:
   - Route/controller files (API endpoints)
   - Service/business logic files
   - Data models/entities
   - Configuration files
   - Key utilities

2. **For each significant module**, generate a Markdown file in `docs/internal/<module-name>.md` containing:
   - **Overview**: What this module does and why it exists
   - **Architecture**: Key classes/functions, their responsibilities, data flow
   - **Dependencies**: External services, libraries, or other modules this depends on
   - **API / Interface**: Public functions, exported classes, HTTP endpoints
   - **Key Decisions**: Non-obvious design choices and their rationale
   - **Known Limitations / TODOs**: Technical debt or planned improvements

3. **Generate index**: Create `docs/internal/README.md` as a navigation index listing all generated docs with one-line descriptions.

4. **Output**: List all files created/updated.

---

## Subcommand: `html`

**Goal**: Generate end-user facing HTML documentation describing project features.

### Steps

1. **Identify user-facing features**: Scan for:
   - HTTP route definitions (GET /path, POST /path, etc.)
   - CLI commands (commander, argparse, cobra, etc.)
   - UI component entry points (React pages, Vue views)

2. **For each feature**, collect:
   - Feature name and description
   - How to access/use it (URL, CLI command, UI location)
   - Required inputs/parameters with types and descriptions
   - Expected output/response
   - Example usage

3. **Generate HTML**: Create a single self-contained `<output-dir>/index.html` (default: `docs/user-guide/`) with:
   - Navigation sidebar with feature list
   - Feature sections with usage examples
   - Embedded CSS (clean, readable, no external dependencies)
   - Responsive layout

   Use this HTML template structure:
   ```html
   <!DOCTYPE html>
   <html lang="en">
   <head>
     <meta charset="UTF-8">
     <title>[Project Name] — User Guide</title>
     <style>/* embedded CSS */</style>
   </head>
   <body>
     <nav><!-- feature list --></nav>
     <main><!-- feature sections --></main>
   </body>
   </html>
   ```

4. **Output**: Report the generated file path.

---

## Usage Help

```
dev-toolkit:tech-docs — Technical Documentation Generator

Usage:
  /dev-toolkit:tech-docs internal              Generate team docs (Markdown)
  /dev-toolkit:tech-docs html                  Generate user guide (HTML)
  /dev-toolkit:tech-docs html --output <dir>   Custom output directory

Output locations (default):
  internal → docs/internal/
  html     → docs/user-guide/index.html
```
