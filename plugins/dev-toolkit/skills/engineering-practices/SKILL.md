# Engineering Practices — Referencia

> Documento de referencia interna. Leído por el agente `best-practices` y el skill `dev-toolkit:sdd`.

---

## Principios del Plugin

1. **Single Responsibility** — cada agente hace una sola cosa.
2. **Orchestrator Pattern** — el chat principal o skill despacha a agentes; los agentes no se llaman entre sí.
3. **Context Efficiency** — los agentes leen solo lo necesario; archivos de scratchpad previenen bloat de contexto.
4. **Evidence-Based** — los agentes citan paths específicos y números de línea al referenciar código.
5. **Verification First** — los criterios de aceptación se definen antes de comenzar la implementación.

---

## Estándares de Calidad de Código

### Naming
- Variables y funciones: descriptivos, sin abreviaciones crípticas.
- Archivos: kebab-case para módulos, PascalCase para clases/componentes.
- Constantes: UPPER_SNAKE_CASE.

### Error Handling
- Nunca ignorar errores silenciosamente.
- Errores de negocio: retornar con mensaje descriptivo.
- Errores inesperados: loguear con contexto (stack trace, input).
- Validar en los límites del sistema (input del usuario, APIs externas).

### Testing
- Cobertura mínima sugerida: 80% en lógica de negocio crítica.
- Orden: happy path → edge cases → error scenarios.
- Tests rápidos y deterministas (sin sleeps, sin dependencias de red en unit tests).
- Nombrar tests describiendo el comportamiento, no la implementación.

### Documentation
- Comentarios solo donde la lógica no es auto-evidente.
- Evitar comentarios redundantes que repiten el código.
- Documentar decisiones de diseño no obvias (el "por qué", no el "qué").

---

## Patrones de Arquitectura

### Layered Architecture
- **Presentation**: controllers, routes, CLI handlers
- **Application**: use cases, services
- **Domain**: entities, value objects, domain logic
- **Infrastructure**: repositories, external APIs, DB access

### Dependency Injection
- Las dependencias se inyectan, no se instancian dentro de las clases.
- Facilita testing y reemplazabilidad de componentes.

### Repository Pattern
- Abstraer el acceso a datos detrás de interfaces.
- La lógica de negocio no sabe cómo se persisten los datos.

---

## Seguridad

- Nunca commitear secretos, API keys o passwords.
- Validar y sanitizar toda entrada del usuario.
- Usar HTTPS en producción.
- Aplicar principio de mínimo privilegio en permisos y roles.
- Mantener dependencias actualizadas (revisar CVEs).

---

## Recomendaciones por Stack

El agente `best-practices` usa este documento como base y lo enriquece con información específica del stack del proyecto consultando Context7.
