# Feature Pipeline Plugin

Pipeline de desarrollo end-to-end para proyectos con requerimientos en `/features/`. Lleva una feature desde el spec hasta el PR, con documentación, tests y code review incluidos.

Diseñado para equipos pequeños (2-5 devs) que trabajan con Next.js, TypeScript y Prisma, pero adaptable a cualquier stack definido en `CLAUDE.md`.

## Prerequisitos

- `CLAUDE.md` en la raíz del proyecto con el stack y las convenciones definidas
- Carpeta `/features/` con archivos `.md` por requerimiento
- Carpeta `/featuresDone/` (puede estar vacía al inicio)
- Git inicializado con branch `develop` configurado

## Skills

### `/feature-pipeline:feature-start [nombre]` — Fase 1

Lee el requerimiento de `/features/`, genera spec técnica, pide aprobación y crea el branch.

```
/feature start login
/feature start dashboard-admin
```

### `/feature-pipeline:feature-develop` — Fase 2

Implementa la feature, genera documentación técnica + HTML de usuario, escribe tests y hace commit.

```
/feature develop
```

### `/feature-pipeline:feature-review` — Fase 3

Code review con Stack Specialist, pide aprobación, mueve a `/featuresDone/` y crea el PR.

```
/feature review
```

### `/feature-pipeline:improve [path]` — Mejora puntual

Activa el Stack Specialist sobre un archivo o carpeta específica.

```
/improve components/socios/SocioCard.tsx
/improve app/api/socios/
```

### `/feature-pipeline:scan` — Health check

Escanea el proyecto completo buscando deuda técnica, coverage gaps y dependencias desactualizadas.

```
/scan
```

### `/feature-pipeline:context-sync` — Sincronizar CLAUDE.md

Detecta cambios de stack o convenciones y propone actualizaciones al CLAUDE.md.

```
/context sync
```

## Agentes

- **stack-specialist** — Lee CLAUDE.md y actúa como senior engineer del stack del proyecto. Usado por `/improve` y `/feature review`. Solo lectura.
- **qa** — Analiza coverage gaps contra la spec y escribe los tests faltantes. Usado por `/feature develop`. Nunca modifica archivos de implementación.

## Flujo completo

```
/features/01_login.md
       ↓
/feature start login   →  Spec técnica  →  ⏸ Aprobación  →  git branch feature/login
       ↓
/feature develop       →  Código  →  Docs técnica  →  HTML usuario  →  Tests
       ↓
/feature review        →  Code review  →  ⏸ Aprobación  →  /featuresDone/  →  PR
```

## Compatibilidad

El plugin lee `CLAUDE.md` para adaptar sus recomendaciones al stack del proyecto. Funciona con cualquier stack que esté documentado en ese archivo.

Probado con: Next.js 14 (App Router) + TypeScript + Prisma + NextAuth.js + Jest.
