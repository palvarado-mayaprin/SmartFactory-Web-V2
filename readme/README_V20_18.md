# SmartFactory Web v20.18

## Cambio aplicado

Se agregó regla operativa para mensajes MQTT con `numOp = 100`:

- Se siguen insertando en `smartfactory.mensajes_mqtt`.
- Ya no se insertan en `smartfactory.datossensados`.

## Motivo

`datossensados` es tabla temporal operacional y no debe contaminarse con mensajes técnicos/heartbeat.
`mensajes_mqtt` sigue conservando trazabilidad histórica completa.

## Base

Basada en v20.17 con log diagnóstico de conglomerado.
