# scan — Escaneo de Deuda Técnica

> Se invoca con `/feature-pipeline:scan`.
>
> Analiza el proyecto completo buscando deuda técnica, inconsistencias y oportunidades de mejora priorizadas por impacto.

---

## Cuándo usar esta skill

Cuando el usuario quiere una visión general del estado técnico del proyecto.

Ejemplos de trigger:
- `/scan`
- "escaneá el proyecto"
- "buscá deuda técnica"
- "qué hay que mejorar en el proyecto"
- "hacé un health check del código"

---

## Proceso

### Paso 1: Cargar contexto

Leer `CLAUDE.md` para entender stack, convenciones y estructura esperada.

### Paso 2: Escaneo estructural

Verificar que la estructura de carpetas coincide con la definida en CLAUDE.md.
Reportar carpetas o archivos que no siguen la convención.

### Paso 3: Escaneo de código con Stack Specialist

Invocar el agente `stack-specialist` con scope amplio sobre las carpetas principales:
- `app/`
- `components/`
- `lib/`

Buscar específicamente:
- Client Components que podrían ser Server Components
- Queries Prisma sin `select`
- API routes sin validación Zod
- API routes sin verificación de auth/rol
- Uso de `any` en TypeScript
- Componentes sin tests
- Funciones duplicadas (DRY violations)
- Dependencias no usadas

### Paso 4: Escaneo de cobertura de tests

Buscar archivos en `app/` y `components/` que no tienen un correspondiente `.test.tsx`.
Listarlos como "sin cobertura".

### Paso 5: Escaneo de dependencias

Leer `package.json`. Identificar:
- Dependencias con versiones desactualizadas conocidas
- Dependencias de desarrollo en `dependencies` (deberían estar en `devDependencies`)
- Paquetes duplicados que cumplen la misma función

### Paso 6: Producir reporte priorizado

```markdown
# Health Check — SIGEC
Fecha: [fecha]

## Resumen Ejecutivo
- 🔴 X issues críticos
- 🟡 Y issues importantes  
- 🟢 Z sugerencias
- 📊 Cobertura de tests estimada: X%

## 🔴 Críticos
[Ordenados por impacto — seguridad y data integrity primero]

## 🟡 Importantes
[Ordenados por frecuencia de ocurrencia]

## 🟢 Sugerencias
[Quick wins — alta relación impacto/esfuerzo]

## Archivos Sin Tests
[Lista de archivos con lógica de negocio y sin tests]

## Dependencias
[Versiones desactualizadas relevantes]

## Próximos Pasos Recomendados
1. [Acción más impactante]
2. [Segunda acción]
3. [Tercera acción]
```

---

## Constraints

- **Solo análisis, no modificaciones.**
- **Priorizar por impacto real** — no reportar stylistic issues como críticos.
- **Citar paths específicos** para cada issue encontrado.
- **Limitar el reporte a los top 10 issues por categoría** — evitar overwhelm.
