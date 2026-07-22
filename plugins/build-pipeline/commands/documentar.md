---
description: Genera retroactivamente las guias de usuario (.dev/manual/) de features ya construidas que quedaron sin documentar, reconstruyendo desde sus commits [T-xxx] y el codigo actual. Un PR con todas las guias.
argument-hint: "[opcional: slug de una feature puntual; por defecto, todas las done sin guia]"
---

Documenta retroactivamente: `$ARGUMENTS`

Segui el modo DOCUMENTAR de la skill `build-pipeline`:

1. Cruza `progress.json` contra `.dev/manual/` y decime que features `done` estan
   sin guia (o limitate a la que te indique). Si no falta ninguna, decimelo y listo.
2. Confirma conmigo la lista antes de arrancar.
3. En una rama `docs/manual-retroactivo`, corre `user-docs-writer` en modo
   retroactivo por cada feature (reconstruye desde los commits `[T-xxx]` y
   documenta el codigo actual de la integracion), commit por guia.
4. Best-effort: la que falle o no tenga superficie de usuario se anota y sigue.
5. Regenera el indice del manual y abri UN PR con todo. Mostrame el resumen y
   sugerime `/publicar-manual` si quiero el manual navegable.
