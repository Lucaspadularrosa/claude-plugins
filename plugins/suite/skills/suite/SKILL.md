---
name: suite
description: Ayuda a elegir que hacer con esta suite de plugins cuando la persona no sabe que comando necesita, no conoce la suite, o describe su situacion en vez de pedir un comando. Se dispara con cosas como no se por donde empezar, que puedo hacer con esto, tengo un proyecto y no se que me conviene, que comandos hay, para que sirve esto, ayudame a arrancar, heredé un codigo, me pasaron un documento, hay que agregar algo, esto esta lleno de bugs. Tambien cuando la persona pide algo que abarca varias etapas (de la nada al sistema andando) y hay que armarle el recorrido. Usar antes de cargar cualquier pipeline, no en vez de ellos.
---

# Por donde empezar

Esta suite hace el ciclo completo de software con agentes, en siete pipelines. Cada
uno tiene su skill y sus comandos; este no hace trabajo, **decide cual corresponde**.

La regla que ordena todo: **primero mira en que estado esta el proyecto, despues
escucha que quiere la persona, y recien ahi elegi.** Los dos, no uno.

## Paso 1 - El estado, que es gratis

```bash
suite-status .dev
```

Cero tokens de modelo, solo lectura. Te dice que pipelines corrieron, en que etapa
esta cada feature, que bloquea y que sugiere. Si el comando no existe, el plugin
`requerimientos` no esta instalado: segui con la tabla y decilo.

Si no existe `.dev/`, la suite nunca corrio en este proyecto: es un arranque.

## Paso 2 - Que esta pidiendo

| Lo que dice la persona | Camino | Plugin |
|---|---|---|
| "tengo el documento que me pasaron", "esta es la idea del sistema" | `/requerimientos:descubrir <rutas>` | requerimientos |
| "quiero arrancar pero no tengo nada escrito" | `/requerimientos:descubrir` sin argumentos (te entrevista) | requerimientos |
| "de estas features, elaboremos estas" | `/requerimientos:incremento <FG-xx>` | requerimientos |
| "cambio esto que ya habiamos definido" | `/requerimientos:cambio <texto>` | requerimientos |
| "es un proyecto chico y el documento esta cerrado" | `/requerimientos <rutas>` (todo en una corrida) | requerimientos |
| "ya estan los requisitos, armemos el plan" | `/planificar` | planning |
| "cambiaron los requisitos, actualiza el plan" | `/replanificar` | planning |
| **"hay que sacarlo ya"**, una feature chica y urgente | `/tarjeta <doc o pedido>` | planning |
| "construi esta feature" | `/construir FG-xx` | build |
| "construi todo lo que se pueda en paralelo" | `/construir-lote` | build |
| "quedaron features sin guia de usuario" | `/documentar` | build |
| "quiero publicar el manual" | `/publicar-manual` | manual-usuario |
| "hereda este repo", "no entiendo que hace esta app" | `/comprender [ruta]` | recovery |
| "busca bugs", "revisa la seguridad", "que se puede mejorar" | `/auditar [alcance]` | audit |
| "construimos algo rapido y quedo sin documentar" | `/requerimientos:promover FG-xx` | requerimientos |
| "como venimos", "que falta", "en que estamos" | `/requerimientos:estado` | requerimientos |
| "como funcionaron los pipelines", "cuanto costo" | `/metricas` | metrics |

## Paso 3 - Deci por donde vas, y ofrece la alternativa

Una linea, siempre: **que elegiste, por que, y cual es la otra opcion**. Equivocarse
tiene que salir barato.

> Voy por `/comprender`, porque el repo tiene codigo y no tiene `.dev/`. Si lo que
> queres es que te busque bugs y no entender el sistema entero, es `/auditar`.

**Sugeri, no lances.** El comando lo confirma la persona, salvo que ya te lo haya
pedido explicito.

## Los pares que se confunden

- **`/comprender` vs `/auditar`**: los dos miran codigo que ya existe. `comprender`
  responde *que hace y en que estado esta*; `auditar` responde *que esta mal*. Si no
  sabe que hace la app, primero comprender.
- **`/requerimientos:descubrir` vs `/incremento`**: descubrir es amplitud barata (el
  mapa de features); incremento es profundidad sobre las features elegidas. Siempre
  descubrir primero.
- **`/tarjeta` vs el ciclo formal**: la tarjeta es para UNA feature acotada y urgente,
  y se paga despues con `/promover`. Con **cualquiera** de estas, recomenda el ciclo
  formal aunque haya apuro: mas de una feature en el pedido, cambios en el modelo de
  datos central, requisitos que hay que acordar con un tercero, dominio sin
  vocabulario comun todavia.
- **`/construir` vs `/construir-lote`**: una feature con pausa de aprobacion del plan,
  contra un lote entero en paralelo sin pausas. Con un lote en curso, una feature
  nueva se construye con `/construir`, no relanzando el lote.
- **`/planificar` vs `/replanificar`**: si ya hay `tasks.json`, es replanificar.
  Planificar de nuevo pisa los ids.

## Recorridos completos

Cuando el pedido abarca varias etapas, no enrutes a un comando: mostra el recorrido y
arranca por el primero.

- **De la nada al sistema andando**: `descubrir` -> `incremento` -> `planificar` ->
  `construir-lote` -> `publicar-manual`.
- **Heredaste una app**: `comprender` -> (opcional) reconstruir la linea de base ->
  `planificar` -> `construir`.
- **Urgencia**: `tarjeta` -> `construir` -> mas tarde `promover`.

## Lo que esta suite no hace

No es un framework ni una libreria: no se importa en el codigo del proyecto. No
reemplaza al equipo — todas las pausas de aprobacion son de la persona. Y no corre
nada en produccion: construye en ramas y abre PRs.

Si lo que la persona necesita no esta en la tabla, decilo derecho en vez de forzar el
comando mas parecido.
