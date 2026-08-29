---
description: Genera retroactivamente las guias de usuario (.dev/manual/) de features ya construidas que quedaron sin documentar, reconstruyendo desde sus commits [T-xxx] y el codigo actual. Un PR con todas las guias.
argument-hint: "[opcional: slug de una feature puntual; por defecto, todas las done sin guia]"
---

Documenta retroactivamente: `$ARGUMENTS`

Segui el modo DOCUMENTAR de la skill `build-pipeline` (lee
`${CLAUDE_PLUGIN_ROOT}/skills/build-pipeline/modes/documentar.md`). Resumen del
contrato: el universo lo da `render_manual_index.py --solo-cobertura` (no leas
progress ni guias); confirma la lista conmigo; una rama `docs/manual-retroactivo`
con un `user-docs-writer` por feature lanzados en una tanda; indice regenerado por
script y UN PR con todo.
