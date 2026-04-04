# Dev Toolkit Marketplace

Marketplace de plugins de Claude Code para equipos de desarrollo.

## Plugins Disponibles

| Plugin | Descripción |
|--------|-------------|
| `dev-toolkit` | Toolkit reutilizable: SDD, buenas prácticas, testing, documentación técnica y Postman |

## Instalación

### 1. Agregar el marketplace (una vez por usuario)

```bash
/plugin marketplace add <github-owner>/claude-plugins
```

### 2. Instalar el plugin

```bash
/plugin install dev-toolkit@dev-toolkit-marketplace
```

## Uso

```bash
# Spec-Driven Development
/dev-toolkit:sdd add "Implement JWT authentication"
/dev-toolkit:sdd plan
/dev-toolkit:sdd implement
/dev-toolkit:sdd go "Add rate limiting"

# Documentación técnica
/dev-toolkit:tech-docs internal
/dev-toolkit:tech-docs html

# Generar colección Postman
/dev-toolkit:postman --base-url http://localhost:8080
```

## Actualizar

```bash
/plugin update dev-toolkit@dev-toolkit-marketplace
```
