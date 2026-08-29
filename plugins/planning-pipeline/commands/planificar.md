---
description: Convierte la linea de base de requisitos en un plan de ejecucion para agentes IA (tareas, lotes paralelos y briefs de feature).
---

Genera el plan de ejecucion a partir de la linea de base de requisitos del proyecto,
siguiendo la skill `planning-pipeline` de punta a punta (precondicion y guard de
re-ejecucion, derivacion en dos fases con un subagente por feature en paralelo, lotes
y vistas por script, validacion mecanica hasta verde + inspeccion de juicio con tope
de 3 pasadas, briefs renderizados por script y completados en paralelo, cierre).

Si ya hay plan con build arrancado, lo correcto es `/replanificar`; regenera todo solo
si te lo confirmo. Si la inspeccion no pasa al tercer intento, mostrame los defectos
remanentes y decido yo. Al final, el resumen con features, tareas, contratos, maximo
paralelismo y critical path, tomado de la salida de los scripts.

$ARGUMENTS
