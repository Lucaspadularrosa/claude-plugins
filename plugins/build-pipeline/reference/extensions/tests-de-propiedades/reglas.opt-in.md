# tests-de-propiedades

Que es: ademas de los tests por ejemplo, cada invariante del dominio se prueba con generadores de datos (property-based testing): ida y vuelta de serializadores, idempotencia, reglas de negocio que valen para cualquier entrada.
Que cuesta: una dependencia de test nueva si el stack no la tiene (el profiler la detecta o la propone); el implementer escribe un test de propiedad por invariante del brief; el gate verifica que existan.
Pregunta: ¿Activamos la extension de tests de propiedades? Conviene si el dominio tiene reglas con muchas combinaciones de entrada o serializacion de datos.
Default: off
