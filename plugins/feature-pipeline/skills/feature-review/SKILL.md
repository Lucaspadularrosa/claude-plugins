# feature-review — Fase 3: Code Review + Cierre

> Skill del pipeline de features. Se invoca con `/feature-pipeline:feature-review`.
>
> Requiere que `/feature develop` haya sido ejecutado.
>
> Orquesta: code review con Stack Specialist → aprobación → mover a /featuresDone → PR.

---

## Cuándo usar esta skill

Después de que `/feature develop` fue completado y los tests pasan.

Ejemplos de trigger:
- `/feature review`
- "revisá la feature"
- "hacé el code review"

---

## Proceso

### Paso 1: Verificar estado

1. Leer `CLAUDE.md` para cargar stack y convenciones
2. Verificar branch activo (`git branch --show-current`)
3. Obtener lista de archivos modificados: `git diff develop --name-only`
4. Leer el `.spec.md` de la feature activa

### Paso 2: Code Review con Stack Specialist

Invocar el agente `stack-specialist` (incluido en este plugin) sobre todos los archivos modificados.

El Stack Specialist debe revisar **en este orden de prioridad**:

**🔴 Crítico (bloquea el merge):**
- Rutas de API sin verificación de sesión o rol
- Input de usuario sin validación Zod
- Secrets o datos sensibles en el código
- Tests faltantes para lógica de negocio crítica

**🟡 Importante (debe resolverse antes del merge):**
- Client Components que podrían ser Server Components
- Queries Prisma sin `select` explícito
- N+1 queries (query dentro de loop)
- Tipos `any` sin justificación documentada
- Funciones sin tipo de retorno explícito
- Nomenclatura que no sigue CLAUDE.md

**🟢 Sugerencias (nice to have):**
- Oportunidades de Suspense / loading states
- Componentes que podrían extraerse
- Tests adicionales para edge cases

### Paso 3: Verificar criterios de aceptación

Revisar el `.spec.md` y verificar que todos los criterios de aceptación estén marcados como completados.

Si hay criterios sin completar, listarlos y preguntar al usuario cómo proceder.

### Paso 4: Mostrar reporte y pedir aprobación ⏸

Mostrar el reporte completo del Stack Specialist.

Preguntar al usuario:

> "¿Aprobás el code review y querés cerrar esta feature? Si hay issues a resolver primero, indicame cuáles."

**Esperar respuesta explícita antes de continuar.**

Opciones:
- **"Aprobado"** → continuar con el Paso 5
- **"Resolver X primero"** → esperar que el usuario resuelva y volver a ejecutar el review
- **"Cancelar"** → no hacer nada, mantener el estado actual

### Paso 5: Cerrar la feature

Una vez aprobado:

1. **Actualizar el `.spec.md`**: cambiar `status: in-progress` a `status: done`
2. **Mover el requerimiento a /featuresDone/**:
   ```bash
   mv features/[nombre].md featuresDone/[nombre].md
   mv features/[nombre].spec.md featuresDone/[nombre].spec.md
   ```
3. **Commit de cierre**:
   ```bash
   git add .
   git commit -m "feat: [nombre] — feature completa, docs y tests incluidos"
   ```

### Paso 6: Crear Pull Request

Crear un PR de `feature/[nombre]` → `develop` con este formato:

**Título:** `feat: [descripción de la feature]`

**Body:**
```markdown
## Qué hace esta feature
[Descripción del requerimiento resuelto]

## Cambios
- [Archivo nuevo/modificado]: [qué hace]

## Tests
- N tests agregados
- Suite completa: ✅ pasando

## Documentación
- Docs técnicas: `/docs/[nombre].md`
- Docs usuario: `/docs/html/[nombre].html`

## Checklist
- [x] Criterios de aceptación verificados
- [x] Tests pasando
- [x] Code review aprobado
- [x] Sin `any` types
- [x] Convenciones de CLAUDE.md respetadas
```

### Paso 7: Confirmar estado final

```
✅ Code review aprobado
✅ Feature movida a /featuresDone/
✅ Commit de cierre realizado
✅ PR creado: feature/[nombre] → develop
⏭  Próxima feature disponible en /features/
```

---

## Constraints

- **No mover a /featuresDone/ sin aprobación explícita del usuario.**
- **No crear el PR sin aprobación.**
- **Si hay issues 🔴 críticos, no proceder hasta que estén resueltos.**
- **Issues 🟡 importantes deben ser resueltos o el usuario debe aceptarlos explícitamente con justificación.**
