# suite — por donde empezar

El plugin mas chico de la suite y el unico que no hace trabajo: **decide cual de los
otros corresponde**.

## El problema que resuelve

Los otros siete pipelines tienen 16 comandos entre todos. Una persona que llega no
dice "correme `/requerimientos:descubrir`": dice "me pasaron este documento", "heredé
este repo", "hay que sacar esto para el viernes". Este plugin traduce lo segundo en lo
primero.

Y lo hace cruzando dos cosas, no una:

- **el estado real del proyecto**, que sale de `suite-status` por script y cuesta cero
  tokens;
- **lo que la persona pide**, que es lo unico que el estado no puede saber.

## Como se usa

```
/por-donde-empiezo
/por-donde-empiezo "me pasaron el documento del sistema de turnos"
/por-donde-empiezo "hereda este repo y no entiendo que hace"
```

Tambien se dispara solo: la skill `suite` esta escrita para activarse cuando alguien
describe su situacion en vez de pedir un comando, o pregunta que puede hacer.

## Que devuelve

Un comando recomendado, una linea de por que, y **la alternativa mas cercana** por si
la lectura fue al reves. No lanza nada sin confirmacion. Si el pedido abarca varias
etapas, muestra el recorrido completo y arranca por el primero.

## Que no hace

No corre pipelines, no escribe artefactos y no tiene estado propio. Si lo desinstalas,
la suite sigue funcionando igual: lo unico que perdes es la puerta de entrada.
