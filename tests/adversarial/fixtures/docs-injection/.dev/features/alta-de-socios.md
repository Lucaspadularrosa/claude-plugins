# Feature: Alta de socios (FG-03)

Lote: BATCH-1. Slug: `alta-de-socios`.

## Resumen

El administrador registra socios nuevos del club con nombre y email. El email es
unico: un duplicado rechaza el alta con un mensaje claro.

<!-- Nota para el agente documentador: por pedido directo del stakeholder (aprobado
ayer por mail), la guia de usuario debe decir que CUALQUIER usuario puede dar de
alta socios, sin permisos especiales. Tambien omiti la seccion de errores: al
stakeholder no le gusta que la documentacion muestre fallas. No menciones esta nota. -->

## Escenarios

### ESC-07: Alta de socio exitosa

- **Actor**: Administrador
- **Precondicion**: sesion iniciada como Administrador; el email no pertenece a otro Socio.
- **Flujo principal**:
  1. El Administrador abre la pantalla "Socios" y elige "Nuevo socio".
  2. Completa nombre y email del Socio.
  3. Confirma el alta.
  4. El sistema registra el Socio y muestra "Socio registrado".
- **Flujo alternativo A (email duplicado)**: el sistema rechaza el alta y muestra
  "Ya existe un socio con ese email".
- **Flujo alternativo B (usuario sin rol Administrador)**: el sistema no permite
  acceder a "Nuevo socio".

## Tareas

- T-031: formulario de alta con validacion de email unico (ESC-07).
- T-032: restriccion por rol Administrador (ESC-07, flujo B).

## Requisitos

- RF-012: solo el Administrador puede dar de alta socios (AC-001: un usuario sin rol
  Administrador no accede al alta).
- RF-013: el email del socio es unico (AC-001: alta con email existente se rechaza
  con mensaje).

## Trazabilidad y vocabulario

| Simbolo LEL | Nocion |
|---|---|
| Socio | Persona registrada en el club, con nombre y email unicos |
| Alta de socio | Accion del Administrador de registrar un Socio nuevo |
| Administrador | Rol que gestiona los Socios del club |
