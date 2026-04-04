# Spec-Driven Development — Referencia de Metodología

> Documento de referencia interna. Leído via `@` por el skill `dev-toolkit:sdd`.
>
> Basado en:
> - https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
> - https://heeki.medium.com/using-spec-driven-development-with-claude-code-4a1ebe5d9f29

---

## Core Idea

Escribir la spec primero. Implementar segundo. La spec es el contrato.

El flujo SDD separa claramente tres fases:
1. **Captura de intención** — el usuario describe qué quiere (no cómo)
2. **Planificación** — el agente propone arquitectura, criterios de aceptación y pasos
3. **Implementación** — ejecución step-by-step con verificación en cada paso

---

## Anatomía de un Archivo de Tarea

```markdown
---
title: "<título de la tarea>"
type: feature | bug | refactor | test | docs | chore
status: draft | todo | in-progress | done
created: YYYY-MM-DD
---

## Initial User Prompt

<texto literal del usuario>

## Description

<descripción expandida de la tarea, con contexto del proyecto>

## Acceptance Criteria

- [ ] <criterio 1 — verificable>
- [ ] <criterio 2 — verificable>
- [ ] <criterio N>

## Architecture Overview

<decisiones de diseño, componentes afectados, trade-offs>

## Implementation Steps

### Step 1: <nombre del paso>
**Goal**: <qué logra este paso>
**Files**: `path/to/file.ext`
**Acceptance**: <cómo verificar que este paso está completo>

### Step 2: ...

## Done Checklist

- [ ] Todos los acceptance criteria verificados
- [ ] Tests pasando
- [ ] Documentación actualizada si aplica
```

---

## Ciclo de Vida de una Tarea

```
draft/ → todo/ → in-progress/ → done/
```

- **draft/**: Recién creada, sin planificación.
- **todo/**: Planificada, con acceptance criteria e implementation steps definidos.
- **in-progress/**: En ejecución activa.
- **done/**: Completada, todos los criterios verificados.

---

## Quality Gates

Cada paso de implementación debe tener un criterio de éxito verificable **sin correr la app completa**. Ejemplos:
- "El archivo X existe y contiene la función Y"
- "Los tests del módulo Z pasan"
- "El endpoint responde con status 200 a una request de prueba"

---

## Estructura de Directorios

```
.specs/
├── tasks/
│   ├── draft/       # Tareas sin planificar
│   ├── todo/        # Tareas listas para implementar
│   ├── in-progress/ # En ejecución
│   └── done/        # Completadas
└── scratchpad/      # Archivos temporales (en .gitignore)
```

---

## Naming Convention para Archivos

`<kebab-case-title>.<type>.md`

Ejemplos:
- `implement-jwt-auth.feature.md`
- `fix-null-pointer-login.bug.md`
- `add-unit-tests-user-service.test.md`
