# SmartFactory Web v20.20

## Objetivo

Ajuste posterior a revisión QA del diagnóstico de `cantidadreal` negativa.

## Cambios

- Se mantiene **sin modificación** la fórmula productiva existente de `cantidadreal` en `services/cierres_service.py`:
  - `cantreal_calculada = cantreal_original - suma_mt_anterior`.
- Se mantiene **sin modificación** el valor utilizado en el `INSERT` a `smartfactory.resumenmarcajes`, incluso si resulta negativo.
- Se agrega `logger.error(...)` cuando se detecta `cantidadreal < 0`, con OP, MAC, valores de cálculo, tipo de cierre, recurso y actividad.
- Se conserva el diagnóstico detallado en `logs/cantidadreal_negativos.log`.
- Los fallos al escribir o construir el diagnóstico se registran con `logger.error(...)` y **no interrumpen el cierre operativo**.
- Las consultas adicionales de diagnóstico continúan ejecutándose únicamente cuando el resultado es negativo.

## Verificación sobre `api/mqtt_api.py`

No se modificó este archivo. La comparación con la base anterior confirma que únicamente contiene los endpoints de inicio, detención y estado de MQTT. El cálculo de `cantidadreal` no se realiza allí.

Tampoco existe en v20.19 ni en v20.20 un `max(0, cantidadreal...)` asociado al cierre.

## Versión

- FastAPI: `20.20.0`
- Interfaz: `v20.20`
