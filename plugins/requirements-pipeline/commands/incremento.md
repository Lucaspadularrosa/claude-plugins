---
description: "Elabora y baselinea las features elegidas del mapa del producto: escenarios completos, requisitos con su inspeccion y diseno tecnico delta. La unidad del incremento es la feature."
argument-hint: <FG-01 FG-02 ... o nombres de features del mapa>
---

Ejecuta el modo INCREMENTO de la skill `requirements-pipeline` para: `$ARGUMENTS`

1. Resolve las features contra `product-map.json` (acepto ids `FG-xx` o nombres). Si
   alguna no existe o esta deprecada, frena y aclaramelo. Registra el incremento
   (`INC-xxx`) en `changelog.json`.
2. Corre `scenario-modeling` en modo profundizacion: elabora solo los escenarios de
   esas features, conservando los ids `SCN-xx` del mapa.
3. Corre `requirements-specification` en modo incremento: requisitos solo de esas
   features, conservando los `FG-xx`; lo de incrementos anteriores queda intacto.
4. Si la elaboracion propone modificar o deprecar algo ya baselineado, hace la PAUSA
   DE CONFIRMACION: mostrame el antes/despues de cada cambio y espera mi OK uno por
   uno. Sin mi confirmacion no se toca nada baselineado.
5. Corre `requirements-inspection` y su lazo de correccion hasta que pase.
6. Si las features tienen pantallas, preguntame si hay mockups de UI. Corre
   `technical-design` en modo incremental y `design-inspection` con su lazo, hasta que
   pase.
7. Marca las features como `baselined` en el mapa, cierra la entrada del changelog con
   los veredictos y versiones, y mostrame el resumen. Sugerime el paso siguiente:
   `/planificar` si todavia no hay plan, o re-planificar si ya existe.
