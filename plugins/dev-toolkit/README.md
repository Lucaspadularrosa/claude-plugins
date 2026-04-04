# Dev Toolkit Plugin

Plugin reutilizable y adaptable a cualquier proyecto de software, independientemente del lenguaje o framework utilizado.

## Funcionalidades

### `/dev-toolkit:sdd` — Spec-Driven Development

Implementa el flujo SDD completo con subcomandos:

```bash
/dev-toolkit:sdd add "Implement user authentication"   # Crea una nueva tarea/spec
/dev-toolkit:sdd plan [task-file]                      # Planifica e itera sobre la tarea
/dev-toolkit:sdd implement [task-file]                 # Implementa la tarea
/dev-toolkit:sdd go "Implement user authentication"    # Ejecuta todo en secuencia
```

Las tareas se guardan en `.specs/tasks/` con ciclo de vida: `draft/ → todo/ → in-progress/ → done/`.

### `/dev-toolkit:tech-docs` — Documentación Técnica

```bash
/dev-toolkit:tech-docs internal              # Docs internas para el equipo (Markdown)
/dev-toolkit:tech-docs html                  # Docs para el usuario final (HTML)
```

### `/dev-toolkit:postman` — Colección Postman

```bash
/dev-toolkit:postman                         # Genera postman-collection.json
/dev-toolkit:postman --base-url http://...   # Con URL base personalizada
/dev-toolkit:postman --focus <module>        # Filtrar por módulo
```

## Agentes

- **best-practices**: Analiza el stack del proyecto y propone buenas prácticas. Solo lectura.
- **testing**: Genera y mantiene tests siguiendo las convenciones del proyecto.

## Principios de Diseño

- El chat principal actúa como orquestador.
- Cada sub-agent tiene una única responsabilidad.
- Optimización de tokens y contexto.
- Usa Context7 para documentación actualizada.
