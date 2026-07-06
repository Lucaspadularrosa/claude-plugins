# Turnera Lupe — vision del producto

Lupe tiene una peluqueria con tres peluqueros y hoy maneja los turnos por
WhatsApp y una libreta. Pierde turnos por superposicion, los clientes se
olvidan de venir y nadie sabe cuanto facturo cada peluquero. Quiere un sistema
web simple para que los clientes reserven solos y ella deje de ser el cuello
de botella.

## Como trabaja hoy

- Cada **peluquero** atiende de martes a sabado, de 9 a 19, con una hora de
  almuerzo que cada uno elige. Un **turno** dura 30 o 60 minutos segun el
  **servicio** (corte 30, color 60, corte+barba 60).
- El **cliente** pide turno por WhatsApp; Lupe mira la libreta y le ofrece
  horarios. Si el cliente no viene (**ausencia**), el hueco se pierde.
- Los precios cambian cada dos o tres meses; la lista la decide Lupe.

## Que quiere del sistema

- Que el cliente vea los horarios libres de cada peluquero y **reserve** solo,
  eligiendo servicio y peluquero. Un horario ocupado no puede reservarse dos
  veces: eso es lo que mas le duele hoy.
- Reservar exige una **seña** del 20% del servicio (pago online). Si el
  cliente **cancela** con mas de 24 horas de anticipacion, la seña se
  devuelve; con menos, se pierde.
- El dia anterior al turno, el sistema manda un **recordatorio** al cliente
  (email o WhatsApp, lo que sea mas simple).
- Lupe (la **dueña**) puede: bloquear horarios (feriados, vacaciones de un
  peluquero), cargar y cambiar la lista de servicios y precios, y marcar una
  ausencia cuando un cliente no vino.
- Un cliente con **tres ausencias** en los ultimos seis meses no puede
  reservar mas online: tiene que llamar (Lupe decide si lo perdona).
- Reporte mensual por peluquero: turnos atendidos, ausencias y total señado.

## Restricciones

- Los peluqueros no tocan el sistema al principio: solo Lupe y los clientes.
- Tiene que andar bien en el celular (los clientes reservan desde el telefono).
- Lupe no quiere perder el historial: los turnos pasados no se borran nunca.
