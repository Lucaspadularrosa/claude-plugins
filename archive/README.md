# Archive

Plugins retirados del marketplace. Se conservan por historia, pero **no se instalan**
ni se mantienen.

## `feature-pipeline`

Pipeline de build de la primera generacion (spec -> branch -> codigo -> tests ->
review -> PR), atado a Next.js/TypeScript, a requerimientos en `/features/` y a
convenciones de un proyecto cliente concreto. Fue reemplazado por la suite actual:

- Su rol de ejecutor de features hoy lo cubre **`build-pipeline`** (agnostico de
  stack, briefs de `.dev/features/`, piso de seguridad OWASP, lotes en paralelo).
- Sus pasadas de mejora (`/improve`, `/scan`) hoy las cubre **`audit-pipeline`**
  con verificacion adversarial.

Ademas, sus skills no tienen frontmatter YAML, por lo que las versiones actuales de
Claude Code no las registran. Si alguien lo necesitara, requiere de-personalizarlo
(referencias al proyecto SIGEC) y modernizar el formato.
