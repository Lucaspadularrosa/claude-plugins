# resiliencia

Que es: reglas para que una falla de red, de una dependencia o de un despliegue degrade el sistema en vez de tumbarlo (timeouts, reintentos solo idempotentes, claves de idempotencia, salud, limites de memoria, migraciones compatibles, logs correlacionados).
Que cuesta: el profiler lee un archivo mas una vez por proyecto; el implementer aplica ocho reglas cuando la feature toca red, datos o despliegue; el gate reporta cumplimiento por regla.
Pregunta: ¿Activamos la extension de resiliencia? Conviene si el sistema habla con servicios externos, corre como servicio o tiene despliegues con datos en produccion.
Default: off
