# SmartFactory v17.2 — Cierre seguro con MQTT antes de BD

Esta versión corrige un riesgo operativo detectado en v17/v17.1:

- En cierres FINAL y MD, primero se publica MQTT de paro al ESP.
- Si MQTT no está conectado o falla la publicación, NO se ejecutan INSERT/DELETE en BD.
- En cierre MT no se publica MQTT, por lo tanto puede cerrar BD sin requerir MQTT.

## Validación esperada

### FINAL / MD con MQTT desconectado

Debe responder:

```text
ok: false
modo: MQTT_NO_PUBLICADO
queries_ejecutados: []
```

Y no debe modificar:

```text
smartfactory.resumenmarcajes
smartfactory.datossensados
smartfactory.marcajeactivo
```

### FINAL / MD con MQTT conectado

Debe:

```text
1. publicar MQTT fin al ESP
2. insertar resumenmarcajes
3. borrar datossensados
4. borrar marcajeactivo
```

### MT

Debe:

```text
1. NO publicar MQTT
2. insertar resumenmarcajes estado MT
3. borrar datossensados
4. borrar marcajeactivo
```
