# Guia: entorno tecnico (una pagina)

Para cuando el stack, la infraestructura o las convenciones vienen impuestos, o cuando
el producto se construye adentro de un codebase existente. El intake lo registra como
contexto de soporte; el diseno tecnico lo toma como restriccion y el perfil de stack
del build lo usa para no deducir lo que vos ya sabes. Si todo es a eleccion, no hace
falta escribirla.

## 1. Stack impuesto

Lenguaje, framework y versiones que si o si se usan, con el motivo si lo hay
("PHP 8.2 porque es lo que opera infraestructura"). Si hay version minima y maxima,
las dos.

## 2. Donde corre

Infraestructura de produccion (nube, servidor propio, contenedores), base de datos y
servicios gestionados disponibles, y quien los opera. Si hay entorno de prueba,
donde esta.

## 3. Librerias y practicas prohibidas

Una fila por cosa que no se puede usar, con la razon y la alternativa. La razon
importa: es lo que permite decidir los casos que la tabla no cubre.

| Prohibido | Razon | Alternativa |
|---|---|---|
| ORM X | licencia incompatible | ORM Y |
| llamadas HTTP sin timeout | incidentes en produccion | cliente Z con timeout obligatorio |

## 4. Integraciones obligatorias

Sistemas externos con los que hay que hablar: que son, que protocolo, quien provee las
credenciales y si existe entorno de prueba. Sin esto, el diseno queda con una pregunta
abierta por integracion.

## 5. Seguridad y acceso

Como se autentican los usuarios hoy (inicio de sesion de la organizacion, proveedor
externo, cuenta propia), donde viven los secretos, y que datos tienen regulacion.

## 6. Convenciones del codigo

Naming, layout de carpetas, linter y formateador, politica de ramas y de commits,
cobertura minima de tests si existe. Si hay un `CLAUDE.md` o una guia de estilo en el
repo, alcanza con apuntar a ella.

## 7. Modulo de ejemplo

La ruta de un modulo existente que sirva de patron: "hace las cosas como esta hecho
`src/modules/pagos/`". Es la instruccion mas efectiva que se le puede dar al build.

## 8. CI/CD existente

Si ya hay pipeline de integracion continua, que corre y donde. Si no hay, decilo: el
build puede bootstrapear uno minimo.
