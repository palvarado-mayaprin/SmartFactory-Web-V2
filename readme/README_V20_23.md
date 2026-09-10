# SmartFactory Web v20.23

## Retorno automático después de tiempo improductivo

Esta versión parte de v20.22 y agrega un flujo posterior al cierre exitoso de un marcaje improductivo (`numOp = 12345`).

### Regla de identificación

Un marcaje se considera improductivo únicamente cuando su OP es `12345`.

### Consulta del contexto anterior

Antes de ejecutar el cierre del improductivo se consulta exactamente el último registro de `smartfactory.resumenmarcajes` para el mismo recurso y usuario, ordenado por `tiempofinal DESC` y limitado a un registro. La consulta se hace antes del cierre para evitar que el improductivo recién cerrado pase a ser el registro más reciente. Ninguna acción posterior se ejecuta hasta que el cierre improductivo termina correctamente.

Si el último registro encontrado no tiene `variable01 = 1`, el cierre termina normalmente sin sugerir reapertura. No se continúa buscando registros históricos anteriores.

### Reanudación

Cuando el último registro previo tiene `variable01 = 1`, después del cierre exitoso se muestra una confirmación para continuar la actividad anterior, indicando actividad, recurso y orden.

- **No:** el cierre termina normalmente y no se crea otro marcaje.
- **Sí:** se reconstruye la OP mediante los endpoints existentes, se valida que el recurso siga disponible y se valida la actividad (cotizada o no cotizada). Luego se reutiliza `/api/marcajes/iniciar-real-bd` para abrir automáticamente el marcaje.

No se heredan MAC, topic, contadores MQTT, tiempos ni datos operativos del marcaje anterior. Las validaciones y la publicación MQTT siguen siendo las existentes en el flujo normal de apertura.

Si la reapertura falla, el tiempo improductivo ya cerrado no se revierte.

### Compatibilidad

No se modifica la lógica de FINAL, MD, MT, `cantidadreal`, diagnóstico de valores negativos, flujo ARR de v20.21 ni PAUSA POR ACTIVIDAD IMPRODUCTIVA de v20.22.
