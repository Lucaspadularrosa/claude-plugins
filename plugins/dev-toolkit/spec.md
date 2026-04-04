# Dev Toolkit Plugin

## Descripcion General

Plugin reutilizable y adaptable a cualquier proyecto de software,
independientemente del lenguaje o framework utilizado.

## Principios de Diseno

Usar Context7 para leer la documentacion de Claude Code y construir
los componentes necesarios bajo los siguientes principios:

- Crear skills, agents y commands segun los requerimientos del proyecto.
- El chat principal actua solo como orquestador, salvo cuando se invoca
  un skill o command directamente.
- Optimizar siempre el uso de tokens y contexto.
- Cada sub-agent debe tener una unica responsabilidad.

## Funcionalidades

### 1. Spec Driven Development (SDD)

Implementar instrucciones especificas para SDD siguiendo las referencias:
- https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- https://heeki.medium.com/using-spec-driven-development-with-claude-code-4a1ebe5d9f29

Skill propuesta: `sdd` con los siguientes subcomandos:
- `add` — crea una nueva tarea/spec. Si existe documentacion del proyecto,
   debe leerla y usarla para generar el plan.
- `plan` — planifica e itera sobre una tarea existente.
- `implement` — implementa una unica tarea.
- `go` — ejecuta todos los pasos en secuencia.

### 2. Agente de Buenas Practicas

Agente especializado que comprende la tecnologia del proyecto y propone
mejores practicas de forma consistente.

### 3. Agente de Testing

Agente dedicado a la generacion y mantenimiento de tests.

### 4. Documentacion Tecnica

Skill o sub-agent encargado de generar:
- Documentacion tecnica interna para el equipo.
- Documentacion en formato HTML orientada al usuario final,
  describiendo las funcionalidades del proyecto.

### 5. Coleccion Postman

Generacion de colecciones Postman bajo demanda para probar
endpoints o funcionalidades especificas.
