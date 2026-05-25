# improve — Análisis de Mejoras con Stack Specialist

> Se invoca con `/feature-pipeline:improve [archivo o carpeta]`.
>
> Activa el agente `stack-specialist` sobre el código indicado y produce sugerencias específicas al stack del proyecto.

---

## Cuándo usar esta skill

Cuando el usuario quiere mejorar código existente sin estar en medio de una feature.

Ejemplos de trigger:
- `/improve components/socios/SocioCard.tsx`
- `/improve app/api/socios/`
- "mejorá este componente"
- "revisá si hay algo que mejorar en este archivo"
- "el stack specialist que revise esto"

---

## Proceso

### Paso 1: Identificar el target

Si el usuario especificó un path, usarlo directamente.
Si no especificó nada, preguntar: "¿Qué archivo o carpeta querés que analice?"

### Paso 2: Invocar Stack Specialist

Pasar el target al agente `stack-specialist` para análisis completo.

### Paso 3: Presentar resultados priorizados

Mostrar el reporte del Stack Specialist con énfasis en **Quick Wins** — las mejoras de mayor impacto con menor esfuerzo.

### Paso 4: Preguntar qué aplicar

> "¿Querés que aplique alguna de estas mejoras? Podés decirme 'aplicá todo', 'solo las críticas', o elegir ítems específicos."

Si el usuario aprueba cambios → aplicarlos, hacer commit con `refactor: [descripción]`.
Si es solo consulta → no modificar archivos.

---

## Constraints

- **No modificar nada sin confirmación del usuario.**
- **Citar paths y líneas específicas** en cada recomendación.
- **No aplicar sugerencias 🟢 sin que el usuario las pida explícitamente** — solo aplicar 🔴 y 🟡 si el usuario dice "aplicá todo".
