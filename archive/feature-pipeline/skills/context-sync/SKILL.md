# context-sync — Actualizar CLAUDE.md

> Se invoca con `/feature-pipeline:context-sync`.
>
> Re-escanea el proyecto y propone actualizaciones al CLAUDE.md para reflejar el estado actual del stack y las convenciones.

---

## Cuándo usar esta skill

Después de varias features desarrolladas, cuando el stack evolucionó (nuevas librerías, nuevos patrones aprendidos, cambios de convención).

Ejemplos de trigger:
- `/context sync`
- "actualizá el CLAUDE.md"
- "el stack cambió, actualizá el contexto"
- "sincronizá el contexto del proyecto"

---

## Proceso

### Paso 1: Leer el CLAUDE.md actual

Leer `CLAUDE.md` completo. Tomar nota de cada sección y su contenido actual.

### Paso 2: Escanear el estado actual del proyecto

Leer `package.json` para detectar:
- Nuevas dependencias agregadas desde la última actualización
- Cambios de versiones en dependencias clave
- Scripts nuevos

Escanear `app/`, `components/`, `lib/` para detectar:
- Patrones nuevos que se usan consistentemente pero no están en CLAUDE.md
- Convenciones de naming que difieren de lo documentado
- Nuevos módulos o rutas no reflejadas en la estructura

### Paso 3: Comparar y detectar diferencias

Para cada sección de CLAUDE.md, identificar si hay información:
- **Desactualizada**: lo que dice CLAUDE.md ya no refleja el código
- **Faltante**: hay patrones/convenciones en uso que no están documentados
- **Obsoleta**: hay documentación de cosas que ya no se usan

### Paso 4: Proponer cambios

Mostrar las diferencias detectadas en formato diff:

```markdown
## Cambios propuestos para CLAUDE.md

### Stack Técnico
❌ Actual: `Autenticación | NextAuth.js v5`
✅ Propuesto: `Autenticación | Clerk`
Motivo: Se encontró @clerk/nextjs en package.json, no nextauth

### Nuevas convenciones detectadas
✅ Agregar: Los Server Actions se definen en `lib/actions/[feature].ts`
Motivo: Se encontró este patrón en 4+ features desarrolladas

### Estructura actualizada
✅ Agregar carpeta: `/lib/actions/` — Server Actions por módulo
```

### Paso 5: Pedir aprobación ⏸

> "Estos son los cambios que propongo para CLAUDE.md. ¿Los aplico todos, o querés revisar alguno antes?"

**Esperar confirmación antes de modificar.**

### Paso 6: Aplicar cambios aprobados

Actualizar `CLAUDE.md` con los cambios aprobados.
Hacer commit: `docs: actualizar CLAUDE.md con cambios de stack`

---

## Constraints

- **No modificar CLAUDE.md sin aprobación explícita.**
- **Proponer cada cambio individualmente** si hay múltiples cambios grandes.
- **Nunca eliminar secciones** sin confirmación — solo actualizar o agregar.
- **Citar evidencia** para cada cambio propuesto (archivo donde se detectó el patrón).
