# 06 — MQTT y sensores industriales (ESP)

> El firmware de los ESP **no está en el repo**. Todo lo que se diga sobre su comportamiento es [?] o [I].

## 0. Alcance actual (desde 2026-11-13)

**Postergado para una fase futura**:
- simulador MQTT;
- broker de pruebas;
- emulación de ESP;
- infraestructura para reproducir lecturas industriales;
- cambios en el procesamiento de DATOS;
- refactorización de las comunicaciones MQTT.

Mientras tanto:
- Las pruebas sustituyen `mqtt_monitor.publicar` por un doble (`tests/conftest.py`) y el entorno `.venv-test` no tiene `paho-mqtt`.
- Si una funcionalidad nueva afecta a sensores, cálculos de producción o mensajes publicados, **identifica el impacto y pide aprobación** antes de tocar este módulo (`12-procedimiento-desarrollo.md` §2).
- Los hallazgos y decisiones pendientes de este documento siguen vigentes.

## 1. Conexión [C]

- Cliente paho-mqtt 2.1.0 con `CallbackAPIVersion.VERSION1` (`services/mqtt_service.py:49-70`).
- Broker, puerto, usuario y contraseña salen de `SMARTFACTORY_MQTT_*`, **con valores por defecto escritos en el código** (64-65, 112-113). No los copies.
- **Arranque automático** en el evento `startup` (`main.py:37-54`). Si falla:
  - Se registra el error.
  - **No hay reintento** (`iniciar` lanza excepción, `ejecutando=False`).
  - Solo un ADMIN puede pulsar *Conectar MQTT*, o hay que reiniciar uvicorn.
- Tras una conexión correcta, `loop_start` gestiona las reconexiones [I, comportamiento de paho] y `_on_connect` vuelve a suscribir (169-190) [C].
- Las **suscripciones se calculan una sola vez** al iniciar (87-100): `conexion`, `MAC` y, por cada MAC de `macdirectorio`, `-CONFIG`, `-OP`, `-DATOS`, `-BANDERAS`, `-ALERT`. Una MAC nueva exige reiniciar el servicio MQTT [C].
- **Si MySQL falla al iniciar** [C] (E3, Fase 4): `dtbSmartFactory` devuelve `None`, iterar sobre él lanza `TypeError`, que `_obtener_macs_desde_bd` (72-85) captura y convierte en **lista vacía**. MQTT conecta igualmente **solo con `conexion` y `MAC`, sin ningún `-DATOS`**:
  - No se persisten lecturas de ninguna máquina hasta reiniciar el servicio MQTT.
  - El error se anota en `ultimo_error` (84), pero `iniciar` lo **sobrescribe con `None`** justo después (124), y `_on_connect` también lo limpia al conectar (171). El panel no muestra la causa.

## 2. Topics y formatos

| Topic | Dirección | Procesamiento | Nivel |
|---|---|---|---|
| `{mac}-DATOS` | ESP → backend | Se persiste (§4) y se asocia en memoria | C |
| `{mac}-OP` | backend → ESP (y el backend también lo recibe, porque está suscrito) | Inicio y paro de la actividad. Al recibirlo solo se muestra | C |
| `{mac}-CONFIG`, `-BANDERAS`, `-ALERT`, `conexion`, `MAC` | ESP → backend [I] | **Solo se muestran** (buffer de 80); no se persisten | C |

**Payload DATOS** (`mqtt_persistencia_simulada_service.py::_parsear_payload_datos` 75-108) [C]: 8 campos separados por comas.
`numOp, cantpliegos, actividad, actividadreal, velocidadreal, fecha(YYYY-MM-DD), tiempo(HH:MM:SS), unidadesSensadasPeriodo`
- Ejemplo real: `12345,0,COMIDA,0.00,0.00,2026-10-12,16:12:27,0`.
- `numOp == "N/A"` se convierte en `"100"`.
- Con menos de 8 campos el mensaje se descarta (no se persiste).

Existe un **segundo parser**, más laxo, solo para la vista en memoria: `marcajes_estado_service.py::_parsear_payload_datos` (27-68). Toma el campo 1 como cantidad o, si falla, el último número del texto. **No mantener ambos sin necesidad.**

## 3. Publicación (backend → ESP) [C]

| Mensaje | Formato | Origen |
|---|---|---|
| Inicio | `{num_op},{recurso},{actividad},{cantidad},100,2024/10/09,08:31:55,2024/10/09,18:30:55,0,1` (**fechas fijas**) | `marcajes_service::construir_mensaje_mqtt_inicio` (134-151) |
| Paro (FINAL/MD) | `[{num_op},{recurso},{actividad},{cantidadcot},0,{fIni},{hIni},{fFin},{hFin},0,0]` (con corchetes; fechas = MIN/MAX de `datossensados` con `/`) | `cierres_service::_construir_mqtt_fin` (413-430) |
| MT | No se publica nada | `cierres_service.py:608` |

- [?] Significado de los campos `100`, `0,1`, `0,0` y si el ESP usa las fechas.
- Si `recurso` o `actividad` contienen comas, el formato se rompe [C].

`MqttMonitorService.publicar` (257-294) [C]:
- QoS 0, sin `retain`.
- Solo comprueba `client` y `ejecutando`; **no** comprueba `conectado` ni el `rc` que devuelve `publish`.
- Puede devolver **`ok:true` sin que el mensaje haya salido** (R-04).
- A QoS 0 no hay confirmación de entrega en ningún caso.

## 4. Procesamiento de un mensaje entrante [C]

`_on_message` (200-254) corre en el **hilo de red de paho**:

1. `mac, tipo = topic.split("-", 1)` si `len(topic) >= 17`.
2. `registrar_mensaje_mqtt`: buffer en memoria de 80 mensajes y contador.
3. `procesar_persistencia_mqtt` (240-422). El nombre dice "simulada", pero **escribe en producción** si `ENABLE_REAL_MQTT_DB_WRITES`:
   1. `idmensaje = "{mac} {fecha} {tiempo}"`, con resolución de 1 s.
   2. `anterior` = último `cantpliegos` de `mensajes_mqtt` para esa MAC, ordenado por `fechatiempo`.
   3. `unidadesCalculadasConglomerado` = `actual − anterior` (DIFERENCIA); `actual` si no hay anterior (SIN_ANTERIOR) o si `actual < anterior` (RESET).
   4. `INSERT IGNORE mensajes_mqtt`.
   5. `INSERT IGNORE datossensados`, **salvo `numOp == 100`** (v20.18).
   6. **Se inserta aunque no exista un marcaje activo para esa MAC**: no se valida contra `marcajeactivo`.
   7. Si el conglomerado > **48** → `logs/mqtt_conglomerado_alertas.log` (5.167 alertas entre 2026-06-15 y 2026-10-12: 3.784 DIFERENCIA, 1.382 RESET, 1 SIN_ANTERIOR [C]). [?] Si 48 es un límite físico (P-10).
4. `asociar_mensaje_mqtt_a_marcaje` (`marcajes_estado_service.py:115-203`): busca el **primer** marcaje en memoria con esa MAC y actualiza sus contadores. Si la OP o la actividad no coinciden, solo lo anota como advertencia en memoria.
5. Broadcast `MQTT_MENSAJE_RECIBIDO` (y `MARCAGES_ACTIVOS_ACTUALIZADOS` si hubo asociación).

**Sin `try/except` propio** [C] (E3, Fase 4): `_on_message` solo protege la decodificación del payload (201-204). Ni el cuerpo del callback ni `registrar_mensaje_mqtt`, `procesar_persistencia_mqtt` o `asociar_mensaje_mqtt_a_marcaje` capturan excepciones de forma general. paho 2.1.0, con `suppress_exceptions=False` por defecto (no se cambia en el proyecto), registra la excepción y **la relanza** (`venv/Lib/site-packages/paho/mqtt/client.py`, `_handle_on_message`). [I] Lo más probable es que eso termine el hilo de `loop_start` y la lectura MQTT se detenga sin que `ejecutando` cambie. No verificado en ejecución (R-30).

**Coste** [C]: 3 conexiones MySQL síncronas por mensaje DATOS dentro del hilo de paho. [I] Si la BD va lenta, los mensajes se acumulan y puede verse afectado el keepalive.

**Logs**: `mqtt_persistencia.log` crece sin rotación (≈658 MB al 2026-10-12) [C].

## 5. Filas duplicadas en `datossensados`

- **Hecho [C]**: en la muestra del log del 2026-10-12 (1.548 filas de `12345/COMIDA`, MAC D4E9F4ABFD6C), cada uno de los 774 `idmensaje` aparece exactamente **2 veces**, con `idmensaje` relleno en ambas.
- **Hecho [C]**: `datossensados.idmensaje` no tiene UNIQUE, así que `INSERT IGNORE` no deduplica (README_V14 lo advertía).
- **Hecho [C]**: en una muestra de 200 mensajes de esa MAC, este proceso los registró como insertados una sola vez cada uno en `mqtt_persistencia.log`.
- **Hecho [C]**: la app PyQt heredada inserta en `datossensados` **sin** la columna `idmensaje` (`../src/servicios/mqtt_conexion.py:344`).
- **Hipótesis [I], NO confirmada**: había otro proceso con este mismo código insertando, por ejemplo un segundo backend en otra PC. Otras explicaciones no descartadas:
  - Otra instancia en la misma PC.
  - Otra herramienta que también rellene `idmensaje`.
  - Reentregas del broker a otro suscriptor.
  - Verificación pendiente en P-02.
- Impacto: **no** altera `cantidadreal` (N9 en `05-cantidadreal.md`); sí el volumen, el diagnóstico y, posiblemente, `mensajes_mqtt` [?].

## 6. Problemas, recomendaciones y pendientes

- **Problemas**: R-04 (éxito falso), R-08 (sin UNIQUE / duplicados), R-09 (suscripciones fijas, sin reintento inicial y sin `-DATOS` si MySQL falla al iniciar), R-30 (`_on_message` sin `try/except`), R-16 (fechas fijas), R-23 (DB síncrona en el hilo de paho), R-24 (log sin rotación).
- **Recomendaciones (no aprobadas)**:
  - Comprobar `rc` y `is_connected()` antes de declarar éxito.
  - Usar QoS 1 para el inicio y el paro.
  - Mover la persistencia a una cola o worker.
  - Rotar los logs.
  - Recalcular suscripciones al cambiar `macdirectorio`.
- **Pendiente**: P-01 (firmware), P-02 (origen de los duplicados), P-10 (umbral 48).
