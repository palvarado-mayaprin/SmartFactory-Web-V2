# SmartFactory Web v20.17

## Log diagnóstico de unidadesCalculadasConglomerado

Se agregó un log específico para diagnosticar valores anómalos en `unidadesCalculadasConglomerado`.

Cuando el valor calculado sea mayor a `48`, el sistema escribirá en:

```text
logs/mqtt_conglomerado_alertas.log
```

El log incluye:

- topic MQTT
- payload original
- MAC
- idmensaje
- cantpliegos actual
- cantpliegos anterior
- resta `actual - anterior`
- tipo de cálculo aplicado
- query usado para buscar cantpliegos anterior
- respuesta del query anterior
- query INSERT de `mensajes_mqtt`
- query INSERT de `datossensados`
- respuesta de los INSERT si escritura real está habilitada

Este log no bloquea la operación; solo deja trazabilidad para diagnóstico.
