# SmartFactory Web v11 - Bloqueo temprano por máquina/recurso

Esta versión corrige la validación de duplicados por máquina/recurso.

## Cambio principal

Antes, el bloqueo fuerte por máquina/recurso se ejecutaba principalmente en el endpoint de escritura real:

POST /api/marcajes/iniciar-real-bd

Eso permitía que, al seleccionar una actividad, se armara la simulación aunque la máquina ya tuviera marcaje activo.

Ahora el bloqueo se ejecuta desde la preparación/simulación:

POST /api/marcajes/simular-inicio

## Qué bloquea

1. Usuario con marcaje activo en BD.
2. Máquina/recurso con marcaje activo en BD.
3. Topic con marcaje activo en BD.
4. Máquina/recurso con marcaje activo temporal en memoria.
5. Topic con marcaje activo temporal en memoria.

## Qué validar

1. Crear o tener un marcaje activo para una máquina.
2. Intentar seleccionar una actividad para la misma máquina.
3. El sistema debe bloquear desde la selección de actividad y ya no debe armar el mensaje MQTT ni el INSERT preview.

## Modo seguro

Se conserva el modo protegido por defecto. La escritura real solo se activa con:

SMARTFACTORY_ENABLE_REAL_DB_WRITES=1
