# feature-develop — Fase 2: Implementación + Docs + Tests

> Skill del pipeline de features. Se invoca con `/feature-pipeline:feature-develop`.
>
> Requiere que `/feature start` haya sido ejecutado: debe existir un `.spec.md` en `/features/` y un branch `feature/*` activo.
>
> Orquesta: implementación → documentación técnica → documentación HTML de usuario → tests.

---

## Cuándo usar esta skill

Después de que `/feature start` fue aprobado y el branch está creado.

Ejemplos de trigger:
- `/feature develop`
- "arrancá con el desarrollo"
- "implementá la feature"

---

## Proceso

### Paso 1: Verificar estado

Confirmar que existe el contexto necesario:
1. Leer `CLAUDE.md` para cargar stack y convenciones
2. Verificar el branch activo con `git branch --show-current` — debe ser `feature/*`
3. Buscar el archivo `.spec.md` en `/features/` correspondiente al branch
4. Leer la spec completa

Si falta alguno de estos elementos, informar al usuario y detener.

### Paso 2: Implementar la feature

Seguir los **Pasos de Implementación** definidos en la spec, en orden.

Para cada paso:
1. Anunciar cuál paso se está ejecutando
2. Implementar el código respetando las convenciones de CLAUDE.md:
   - Server Components por defecto; `"use client"` solo si hay interactividad
   - TypeScript strict — sin `any`
   - Validación con Zod en API routes antes de tocar la DB
   - Prisma con `select` explícito
   - Nomenclatura definida en CLAUDE.md
3. Al terminar cada paso, verificar el criterio de aceptación definido en la spec

**Estructura de archivos a crear:**
- Page component: `app/(dashboard)/[ruta]/page.tsx`
- Componentes del módulo: `components/[feature]/[NombreComponente].tsx`
- API route: `app/api/[ruta]/route.ts`
- Validaciones: `lib/validations/[feature].ts`
- Types: dentro del componente o en `lib/types/[feature].ts` si se comparten

### Paso 3: Generar documentación técnica

> Generada inline por esta skill — no requiere dependencias externas.

Crear `/docs/[nombre-feature].md` con:

```markdown
# [Nombre Feature] — Documentación Técnica

## Resumen
[Qué hace esta feature]

## Arquitectura
[Decisiones tomadas durante la implementación, incluyendo desviaciones de la spec original]

## Archivos Creados / Modificados
| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `path/to/file.tsx` | Nuevo | [descripción] |

## API Routes
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/[ruta]` | Admin | [descripción] |

## Modelo de Datos
[Schema Prisma relevante, si aplica]

## Variables de Entorno Requeridas
[Nuevas env vars agregadas, si aplica]
```

### Paso 4: Generar documentación HTML de usuario

Crear `docs/html/[nombre-feature].html` — una página HTML standalone que documenta la feature para el usuario final.

**Estilo visual obligatorio** (consistente con el proyecto SIGEC):
- Fondo: `#0A1628`
- Sidebar: `#0D1B36`
- Acento: `#FFCC00` / `#E6B800`
- Tipografía: Plus Jakarta Sans (Google Fonts)
- Cards con bordes suaves, badges de estado con color

**Contenido del HTML:**
- Header con nombre del módulo y descripción breve
- Sección "¿Qué hace esta pantalla?" — explicación para el usuario no técnico
- Screenshots o mockups referenciados (usar los de `.dev/docu_requerimientos/filesFotos/` si existen)
- Sección "Paso a paso" — cómo usar la feature
- Sección "Roles" — qué puede hacer cada rol
- Sección "Preguntas frecuentes" si aplica

### Paso 5: Generar tests

Invocar el agente `qa` (incluido en este plugin) para:
1. Analizar los criterios de aceptación de la spec
2. Identificar gaps de cobertura en el código implementado
3. Escribir tests siguiendo las convenciones del proyecto
4. Ejecutar el test runner definido en CLAUDE.md y verificar que pasan

### Paso 6: Commit

Hacer commit de todo el trabajo:
```bash
git add .
git commit -m "feat: [descripción breve de la feature]"
```

### Paso 7: Actualizar la spec

Marcar los criterios de aceptación como completados en el `.spec.md`:
- Cambiar `status: todo` a `status: in-progress`
- Marcar los checkboxes completados

### Paso 8: Confirmar estado

Mostrar resumen:

```
✅ Feature implementada
✅ Documentación técnica: /docs/[nombre].md
✅ Documentación HTML: /docs/html/[nombre].html
✅ Tests: N tests pasando
✅ Commit realizado
⏭  Siguiente paso: /feature review
```

---

## Constraints

- **Seguir el orden de la spec** — no saltear pasos de implementación.
- **No modificar archivos de test existentes** — solo agregar nuevos.
- **El HTML de usuario debe ser standalone** — sin dependencias externas excepto Google Fonts.
- **No avanzar si los tests fallan** — reportar el error y esperar instrucciones.
- **Respetar convenciones de CLAUDE.md** — el Stack Specialist revisará en la siguiente fase.
