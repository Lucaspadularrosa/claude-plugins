# Extension: resiliencia (opt-in)

Prefijo de ids: `RES`. Severidad de un incumplimiento: `medium`, salvo que la regla
diga `high`. Cada regla trae lo que el gate busca en el diff (*Verificacion*), cuando
aplica (*Aplica si*, segun la superficie del `security-baseline.json`) y que etapa la
cumple (*Etapas*). El `stack-profiler` traduce cada regla al mecanismo nativo del
stack y la vuelca a `extensions.resiliencia.controls` del baseline; el implementer y
el gate leen eso, no este archivo.

## RES-01 · Timeout explicito en toda llamada saliente
- Regla: toda llamada HTTP, a base de datos, a cola o a socket lleva un timeout
  explicito; nunca el default infinito del cliente.
- Verificacion: cada cliente o llamada nueva en el diff pasa un timeout o usa un
  cliente configurado con uno (el profiler indica cual).
- Aplica si: hay llamadas salientes.
- Etapas: implementer, gate.
- Severidad: high.

## RES-02 · Reintentos solo sobre operaciones idempotentes, con backoff y tope
- Regla: se reintenta solo lo que se puede repetir sin efecto doble; con espera
  creciente y un numero maximo de intentos.
- Verificacion: todo reintento del diff envuelve una operacion idempotente (lectura,
  o escritura con clave de idempotencia) y tiene backoff y tope.
- Aplica si: hay reintentos.
- Etapas: implementer, gate.
- Severidad: medium.

## RES-03 · Clave de idempotencia en escrituras que viajan por red
- Regla: una escritura que llega por red (API, cola, webhook) acepta una clave de
  idempotencia y la segunda entrega con la misma clave no produce efecto doble.
- Verificacion: los endpoints o consumidores nuevos que escriben aceptan la clave y
  la persisten; hay un test que entrega dos veces.
- Aplica si: superficie api o service.
- Etapas: implementer, gate.
- Severidad: high.

## RES-04 · Una dependencia caida degrada, no tumba
- Regla: el error de una integracion externa se captura, se registra y produce una
  respuesta degradada o un error claro al usuario; nunca una excepcion sin manejar.
- Verificacion: cada llamada externa nueva tiene manejo de error con registro y un
  camino de degradacion definido.
- Aplica si: hay integraciones externas.
- Etapas: implementer, gate.
- Severidad: medium.

## RES-05 · Endpoint de salud que refleja las dependencias criticas
- Regla: el sistema expone un chequeo de salud que falla si una dependencia critica
  (base de datos, cola) no responde.
- Verificacion: existe el endpoint o comando de salud con el mecanismo del stack y
  consulta las dependencias que el baseline lista como criticas.
- Aplica si: superficie web, api o service.
- Etapas: implementer.
- Severidad: medium.

## RES-06 · Nada crece sin limite en memoria
- Regla: colas, caches y buffers en memoria tienen tamaño maximo o expiracion.
- Verificacion: toda estructura en memoria que acumula entre peticiones en el diff
  declara un limite.
- Aplica si: superficie service.
- Etapas: gate.
- Severidad: medium.

## RES-07 · Migraciones compatibles hacia atras
- Regla: una migracion de datos no rompe la version anterior del codigo mientras el
  despliegue esta en curso (agregar antes de quitar, columnas nuevas con default).
- Verificacion: las migraciones del diff no eliminan ni renombran lo que la version
  anterior todavia usa en el mismo despliegue.
- Aplica si: hay migraciones.
- Etapas: implementer, gate.
- Severidad: medium.

## RES-08 · Logs estructurados con id de correlacion
- Regla: toda peticion genera o propaga un id de correlacion y los logs lo incluyen.
- Verificacion: el codigo nuevo usa el logger del stack con el id de correlacion del
  baseline; no hay `print` ni logs sueltos en caminos de peticion.
- Aplica si: superficie web, api o service.
- Etapas: implementer.
- Severidad: medium.
