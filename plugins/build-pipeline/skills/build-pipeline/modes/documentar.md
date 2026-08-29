# Modo DOCUMENTAR (`/documentar [feature]`)

Genera retroactivamente las guias de usuario que faltan: features construidas antes
de que el pipeline documentara, o cuyo docs best-effort fallo. No toca codigo. Las
convenciones y los scripts son los de `SKILL.md`.

1. **Universo**: `render_manual_index.py {raiz} --solo-cobertura` imprime las features
   `done` sin guia (y cuales ya estan declaradas `SIN GUIA` en progress: esas se
   documentan igual si el usuario quiere, pero avisale que en su momento se marco
   sin superficie). No leas `progress.json` ni las guias: el script ya cruzo todo. Si
   el usuario indico una feature puntual, limitate a esa (aunque no este `done`:
   confirmalo). Si no falta ninguna, decilo y termina.
2. **Confirmar** la lista con el usuario antes de arrancar.
3. **Rama unica** `docs/manual-retroactivo` desde la rama de integracion. Por cada
   feature, una Task de `user-docs-writer` en **modo retroactivo** (reconstruye desde
   los commits `[T-xxx]` del brief y documenta el codigo actual de la integracion);
   lanzalas todas **en una sola tanda** — cada una escribe solo su
   `.dev/manual/{slug}.md`. Commit por guia (`docs: guia de usuario {slug}
   (retroactiva)`).
4. Best-effort: la que falla o no tiene superficie se anota con
   `progress_update.py --note "SIN GUIA: <motivo>"` y no frena a las demas.
5. **Cierre**: `render_manual_index.py {raiz}` en la misma rama, `render_index.py
   .dev`, y UN PR con todas las guias. Resumen: guias generadas, las que quedaron sin
   (y por que), y el proximo paso (mergear y, si quieren el manual navegable,
   `/publicar-manual`).
