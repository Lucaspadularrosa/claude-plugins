# Extension: tests de propiedades (opt-in)

Prefijo de ids: `PBT`. Severidad de un incumplimiento: `medium`. Mismo formato que
las demas extensiones: el `stack-profiler` detecta la libreria de propiedades del
stack (o propone la nativa) y vuelca cada regla a `extensions.tests-de-propiedades.
controls` del baseline; el implementer y el gate leen eso.

## PBT-01 · Un test de propiedad por invariante del brief
- Regla: cada regla de negocio del brief que vale para cualquier entrada (un
  invariante: "el total nunca es negativo", "una cuota vencida no se puede cobrar dos
  veces") tiene un test de propiedad con generadores, ademas de los ejemplos Gherkin.
- Verificacion: por cada regla de negocio del brief marcada como invariante hay un
  test que usa la libreria de propiedades del baseline.
- Aplica si: siempre.
- Etapas: implementer, gate.
- Severidad: medium.

## PBT-02 · Ida y vuelta en todo serializador o parser
- Regla: lo que se serializa y se vuelve a leer tiene que dar el mismo valor
  (`parse(render(x)) == x`) para cualquier `x` generado.
- Verificacion: cada serializador, parser o conversion de formato del diff tiene su
  test de ida y vuelta.
- Aplica si: hay serializacion, parseo o conversion de formatos.
- Etapas: implementer, gate.
- Severidad: medium.

## PBT-03 · Idempotencia probada aplicando dos veces
- Regla: toda operacion declarada idempotente se prueba con `f(f(x)) == f(x)` sobre
  entradas generadas.
- Verificacion: por cada operacion que el brief o RES-03 declara idempotente hay un
  test de doble aplicacion.
- Aplica si: hay operaciones idempotentes.
- Etapas: implementer.
- Severidad: medium.

## PBT-04 · La libreria nativa del stack, con semilla fija en CI
- Regla: se usa la libreria de propiedades que el baseline indica (la del ecosistema:
  Hypothesis, fast-check, jqwik, QuickCheck, FsCheck...), con semilla fija en CI para
  que un fallo sea reproducible.
- Verificacion: los tests de propiedad del diff usan esa libreria y la config de test
  fija la semilla en CI.
- Aplica si: siempre.
- Etapas: implementer, gate.
- Severidad: medium.

## PBT-05 · Generadores que cubren los bordes del dominio
- Regla: los generadores incluyen los bordes: vacio, maximo, negativos, unicode,
  fechas limite; no solo el caso feliz.
- Verificacion: los generadores del diff no restringen el dominio a valores comodos
  sin justificacion en el test.
- Aplica si: siempre.
- Etapas: gate.
- Severidad: medium.
