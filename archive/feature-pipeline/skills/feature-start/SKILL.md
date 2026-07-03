# feature-start — Fase 1: Spec + Arquitectura + Branch

> Skill del pipeline de features. Se invoca con `/feature-pipeline:feature-start [nombre]`.
>
> Orquesta: lectura del requerimiento → spec técnica → aprobación → creación del branch.

---

## Cuándo usar esta skill

Cuando el usuario quiere comenzar a desarrollar una feature que tiene un archivo `.md` en `/features/`.

Ejemplos de trigger:
- `/feature start login`
- `/feature start dashboard-admin`
- "quiero arrancar con el login"
- "empecemos la feature 01"

---

## Proceso

### Paso 1: Leer el requerimiento

Buscar en `/features/` el archivo que corresponde al nombre indicado.
- Si el usuario dijo "login", buscar `*login*.md`
- Si hay ambigüedad (múltiples matches), listar opciones y pedir que elija

Leer el archivo completo. Extraer:
- Descripción de la feature
- Módulo afectado
- Roles con acceso
- Criterios de aceptación
- Referencias a mockups

### Paso 2: Leer contexto del proyecto

Leer `CLAUDE.md` para internalizar:
- Stack técnico (framework, ORM, auth, testing)
- Estructura de carpetas del proyecto
- Convenciones de código

Si existe `package.json`, leerlo también para confirmar versiones.

Invocar el agente `stack-specialist` para que cargue el contexto del stack antes de generar la spec.

### Paso 3: Generar la Spec Técnica

Producir un documento de spec con este formato exacto:

```markdown
---
feature: [nombre]
status: todo
created: [fecha actual]
branch: feature/[nombre-kebab-case]
---

## Descripción
[Qué hace esta feature para el usuario final — 2-3 oraciones]

## Módulo y Rutas Afectadas
- Ruta: `/app/(dashboard)/[ruta]/page.tsx`
- API: `/app/api/[ruta]/route.ts`
- Componentes nuevos: `[lista]`
- Componentes modificados: `[lista]`

## Schema de Base de Datos
[Si aplica: modelos Prisma nuevos o modificados, con campos y relaciones]

## Arquitectura
[Decisiones de diseño: Server vs Client Components, estrategia de fetch, state management]

## Criterios de Aceptación Técnicos
- [ ] [Criterio verificable 1]
- [ ] [Criterio verificable 2]
...

## Pasos de Implementación
### Paso 1: [nombre]
**Goal**: [qué logra]
**Files**: `path/to/file`
**Verificación**: [cómo saber que está completo]

### Paso 2: ...

## Tests Requeridos
- [ ] [Test 1 — happy path]
- [ ] [Test 2 — error/edge case]
- [ ] [Test de autorización por rol]

## Checklist de Cierre
- [ ] Todos los criterios de aceptación verificados
- [ ] Tests pasando
- [ ] Documentación técnica generada
- [ ] HTML de usuario generado
- [ ] Sin `any` types
- [ ] Code review aprobado
```

### Paso 4: Pedir aprobación ⏸

Mostrar la spec al usuario y preguntar:

> "¿La spec está bien? Podés pedir cambios antes de que cree el branch y arranquemos con el desarrollo."

**Esperar respuesta explícita del usuario antes de continuar.**

Si el usuario pide cambios: actualizar la spec y volver a mostrarla.
Si el usuario aprueba: continuar con el Paso 5.

### Paso 5: Crear el branch

Una vez aprobada la spec:

1. Determinar el nombre del branch: `feature/[nombre-en-kebab-case]`
   - Ejemplo: `feature/login-autenticacion`, `feature/dashboard-admin`
2. Ejecutar: `git checkout -b feature/[nombre]`
3. Guardar la spec como archivo en `/features/[nombre].spec.md`
4. Confirmar al usuario que el branch fue creado y la spec guardada

### Paso 6: Confirmar estado

Mostrar resumen:

```
✅ Spec aprobada y guardada en /features/[nombre].spec.md
✅ Branch creado: feature/[nombre]
⏭  Siguiente paso: /feature develop
```

---

## Constraints

- **No crear el branch sin aprobación explícita del usuario.**
- **No inventar criterios de aceptación** — derivarlos del archivo `.md` del requerimiento.
- **Si no existe el archivo en /features/**, informar al usuario y listar los archivos disponibles.
- La spec debe ser específica al stack detectado en CLAUDE.md — no genérica.
