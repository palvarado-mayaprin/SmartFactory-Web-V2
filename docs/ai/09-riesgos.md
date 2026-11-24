# 09 — Registro de riesgos técnicos y de integridad

Estados: **Abierto** (identificado, sin acción) · **Mitigado** · **Cerrado**. Todos están **Abiertos** al 2026-11-13, salvo:

- **R-26** → *Mitigado parcialmente* (2026-11-13): 36 pruebas en `tests/` que fijan apertura, cierre, contrato API y consistencia de la documentación. Faltan frontend y los flujos posteriores al cierre (ARR, retorno, relevo en la UI).
- **R-01** → *Mitigado parcialmente* (2026-11-14, Fase 6, decisión del usuario): si falla el INSERT del resumen del operario, el cierre se aborta antes del agregado y de los DELETE (409 `INSERT_RESUMEN_FALLIDO`). Siguen sin comprobarse el INSERT `F` y los DELETE, y no hay transacción. El aborto deja un riesgo operativo nuevo, **R-33** (*Abierto*, 2026-11-15).
- **R-26** → ampliado (2026-11-14): 57 pruebas pytest y 3 de Node (`tests/js`).
- **R-25** → *Mitigado para pruebas* (2026-11-13): `.venv-test` sin drivers, con red bloqueada y BD sustituida. Para el desarrollo con BD sigue abierto hasta implementar `13-entorno-desarrollo-bd.md`.

Los defectos de negocio (R-01, R-02, R-03, R-04, R-13…) siguen **Abiertos**. Las pruebas los *fijan*, no los corrigen.

**Nivel** indica la certeza del mecanismo (C/I/?).
**Severidad** (Alta/Media/Baja) es una valoración técnica, no una decisión de negocio.

| ID | Riesgo | Nivel | Sev. | Evidencia (archivo:línea / función) | Impacto | Rel. |
|---|---|---|---|---|---|---|
| R-01 | **Cierre no atómico**: cada sentencia usa su propia conexión y no se comprueba el resultado del INSERT `F` ni de los DELETE. Desde v20.24 el fallo del INSERT de operario **sí** aborta el cierre (antes se ejecutaban los DELETE y se respondía `ok:true`) | C | Alta | `cierres_service.py:844-923`; `db/conexion.py:9-50` | Producción perdida sin aviso; solo queda `mensajes_mqtt` | P-11 |
| R-02 | **La resta de MT no está acotada**: `SUM(cantidadreal)` de MT por numOp+actividad sin recurso, MAC, fecha ni sesión | C (+ evidencia de log) | Alta | `cierres_service.py:351-362`, `499-508`; `logs/cantidadreal_negativos.log` (2026-10-12) | Cantidades negativas o infravaloradas | P-04 |
| R-03 | **Error de BD tratado como "sin filas"**: las validaciones de apertura dejan pasar; la identificación dice "usuario no encontrado"; en el cierre, las lecturas de `datossensados`, la suma de MT y el agregado `F` toman 0 o los valores del operario y **el cierre continúa** (E1, E2). Solo `mysql.connector.Error` devuelve `None`; otras excepciones se propagan (E5) | C | Media | `db/conexion.py:40-43`; `usuarios_service.py:80-83`; `marcajes_service.py:71-74`; `persistencia_marcajes_service.py:148-150, 172-174` | Duplicados de marcaje ante fallos intermitentes; mensajes engañosos | — |
| R-04 | **`publicar` devuelve éxito falso**: QoS 0, no revisa `rc` ni `conectado` | C | Alta | `mqtt_service.py:257-294` | Paro "publicado" con el ESP aún contando; inicio no recibido → cantidad 0 | P-01 |
| R-05 | **Sin autenticación ni autorización en el servidor**; los roles son solo CSS; la identidad llega del navegador | C | Alta | `api/*`; `app.js:2078-2093`; `huella_local/main.py:310` | Suplantación de operario; cierres o borrados sin control | — |
| R-06 | **Carrera en la apertura**: SELECT de validación e INSERT en conexiones separadas, sin lock | C / ? (UNIQUE) | Media | `persistencia_marcajes_service.py:266-305` | Dos marcajes en la misma máquina o del mismo usuario | P-03 |
| R-07 | **Sincronización frágil**: cada carga reemplaza la memoria (la vacía si falla la lectura); la memoria tiene prioridad sobre la BD al consultar el marcaje del usuario | C | Media | `api/marcajes_api.py:194-209`; `app.js:1670-1689`; `usuarios_service.py:66-71` | Pantallas sin marcajes; marcajes "fantasma" que bloquean al usuario | P-02 |
| R-08 | **`datossensados.idmensaje` sin UNIQUE**; `INSERT IGNORE` no deduplica; filas duplicadas ×2 observadas | C | Media | `SHOW COLUMNS` en el log; README_V14; `mqtt_persistencia_simulada_service.py:199-205` | Volumen ×N; diagnóstico confuso (no afecta a la cantidad, N9) | P-02 |
| R-09 | **MQTT**: suscripciones fijadas al arrancar; sin reintento si el broker falla al iniciar; si MySQL falla al iniciar, se conecta **sin ningún topic `-DATOS`** y el error queda borrado del estado (E3) | C | Media | `mqtt_service.py:87-141`; `main.py:37-54` | MAC nuevas sin datos; cierres FINAL/MD bloqueados hasta que intervenga un ADMIN | — |
| R-10 | **Recursos de la OP sin filtrar por OT** (regresión respecto a PyQt). Sin cambios en v20.25: `obtener_recursos_de_orden` sigue leyendo `wo200` sin filtro; quedó fuera del alcance de `14-resolucion-ot.md` | C | Media | `ordenes_service.py:21-28` vs `../src/widgets/acciones_botones.py:2284-2289` | Marcajes en recursos ajenos a la OP | P-08 |
| R-11 | **Endpoint heredado `cerrar-real-bd`** borra el marcaje sin resumen | C | Media | `api/marcajes_api.py:309-334`; `persistencia_marcajes_service.py:541-623` | Pérdida de producción si se invoca | — |
| R-12 | **Improductivos con clave compartida** (OP 12345 + motivo) en cálculos y agregados globales | C | Alta | `app.js:551-559, 1181-1189`; R-02, R-13 | Negativos y agregados absurdos en tiempos improductivos | P-06, P-07 |
| R-13 | **Agregado `F` acumulativo**: suma también las filas `F` anteriores de numOp+actividad | C (magnitud ?) | Alta | `cierres_service.py:869-915` | Doble conteo en reportes y exportaciones | P-04, P-05 |
| R-14 | **Credenciales en el código versionado** (3 BD + valores por defecto de MQTT) | C | Alta | `db/conexion.py`; `mqtt_service.py:64-65` | Exposición si el repo o una copia se filtra | P-12 |
| R-15 | **SQL por concatenación**, escapando solo `'` (login incluido). Parcial en v20.25: las consultas nuevas a Optimus (`resolucion_ot_service`, actividades de `ordenes_service`) son parametrizadas; las de SmartFactory nuevas (`construir_insert_marcajeactivo`, `cierres_service::_obtener_ot_fijada`) siguen con `limpiar_sql`, porque `dtbSmartFactory` no admite parámetros. El respaldo `_obtener_wo_tk` del cierre sigue concatenado | C | Media | `marcajes_service.py:8-19`; `auth_service.py:6-36` | Inyección o errores con entradas anómalas | — |
| R-16 | **Payload de inicio con fechas fijas de 2024** y separado por comas sin escapar | C | Baja / ? | `marcajes_service.py:134-151` | [?] según el firmware | P-01 |
| R-17 | **Recurso sugerido por subcadena** de `staf_resource`. Sin cambios en v20.25 | C | Baja | `ordenes_service.py:110-114` | Sugerencia equivocada | — |
| R-18 | **`cantidadcot` incoherente en el improductivo** (memoria `None` frente a BD 12345) | C | Baja | `marcajes_service.py:422-431`; `cierres_service.py:506` | Datos inconsistentes en el resumen | — |
| R-19 | **El `onchange` del recurso improductivo lanza la apertura**; el primer recurso no se puede elegir directamente | C | Baja | `templates/index.html:180` | Usabilidad; aperturas accidentales (mitigado por la confirmación) | — |
| R-20 | **DELETE de `marcajeactivo` en el cierre sin recurso ni topic** | C | Baja | `cierres_service.py:632-635` | Si hubiera duplicados por usuario, borraría más de uno | R-06 |
| R-21 | **Sin auditoría de cierres**: no se escribe en el log y no se registra quién cerró (`usuarioFinalizacion`) | C | Media | `cierres_service.py:724-968`; `app.js:1734-1754` | Sin trazabilidad de los cierres SU/ADMIN ni de los fallos | — |
| R-22 | **Relevo MT volátil** (solo una variable JS); al perderse, la máquina cuenta sin marcaje y aparece libre | C | Media | `app.js:891-894, 1007-1013` | Producción huérfana o asignada al siguiente marcaje | P-01 |
| R-23 | **BD síncrona en el hilo de paho** (3 conexiones por mensaje) | C (efecto I) | Media | `mqtt_service.py:200-254` | Cola de mensajes y posibles desconexiones con la BD lenta | — |
| R-24 | **`mqtt_persistencia.log` sin rotación** (≈658 MB) | C | Media | `mqtt_persistencia_simulada_service.py:47-52` | Disco lleno | — |
| R-25 | **Escritura en producción por defecto**: flags en "1"; arrancar o importar conecta a BD y MQTT reales | C | Alta | `config.py:50-52`; `main.py:37-54` | Escrituras o publicaciones accidentales durante el desarrollo | — |
| R-26 | **Cobertura de pruebas parcial**: hasta el 2026-11-13 no había ninguna; hoy cubren apertura, cierre (incluidos los pliegos incorrectos), contrato API y la validación pura del formulario de cierre, pero no el frontend ni los flujos posteriores al cierre | C | Media | `tests/` (57 pytest + 3 Node) | Regresiones no detectadas fuera de lo cubierto | — |
| R-27 | **`innerHTML` con datos sin escapar** | C (impacto ?) | Baja | `app.js:1343, 1639-1663, 1931-1937` | XSS si llegan datos maliciosos por BD o MQTT | — |
| R-28 | **`dtbOptimus` lanza excepción** en el cierre → HTTP 500 | C | Baja | `db/conexion.py:53-73`; `cierres_service.py:289, 302, 741` | El cierre falla sin escrituras (seguro), con un error poco claro | — |
| R-29 | **Lista en memoria sin lock**, compartida por el hilo de paho y el event loop | C (efecto I) | Baja | `marcajes_estado_service.py:8, 115-231` | Inconsistencias visuales | — |
| R-30 | **`_on_message` sin `try/except` propio** (solo protege la decodificación); paho relanza las excepciones del callback (E3) | C (efecto I) | Media | `mqtt_service.py:200-254` | [I] Fin del hilo de red y lectura MQTT detenida sin aviso | — |
| R-31 | **Diálogo de éxito del improductivo con `OP null`**: el selector de recursos sigue visible con las opciones anteriores y `ordenActual` ya es `null` (E6) | C (estático) | Baja | `app.js:1107, 1202, 1207, 1118-1141` | Solo presentación; el backend recibe `12345` fijo | R-19 |
| R-32 | **`total_usuario` (pliegos buenos) sin validar en el servidor**: acepta `str/int/float/None` (`models/schemas.py`), solo se aplica `limpiar_sql`. Un valor no numérico o con decimales hace fallar o redondea el INSERT en la columna INT. Desde v20.24 un fallo aborta el cierre en vez de perder la producción | C | Baja | `models/schemas.py:67`; `cierres_service.py:510` | Cierre rechazado (409) ante entradas anómalas; el navegador limita con `type=number` | — |
| R-34 | **Resta de MT y agregado `F` sin distinguir OT** (2026-11-24): desde la iteración 4 de `14-resolucion-ot.md` la misma actividad puede trabajarse en varias OT de una OP (`ELEGIDA`), pero `cantidadreal = última cantpliegos − SUM(MT de numOp+actividad)` y el agregado `F` (`SUM(cantidadreal) … WHERE actividad AND numOp`) agrupan por OP + actividad, **no por OT** (`wo_number`). Los MT y resúmenes de una OT se mezclan con los de la otra. **No corregido** (fuera de alcance; requiere decisión) | C (mecanismo) / I (frecuencia) | Media | `cierres_service.py:351-362, 869-915` | MT de la OT A restados del cierre de la OT B (negativos o infravalorados) y fila `F` que suma ambas OT | P-04, R-02, R-13 |
| R-33 | **Paro MQTT publicado y resumen sin guardar** (FINAL/MD, v20.24): el paro se publica **antes** del INSERT del operario. Si el INSERT falla, el cierre se aborta (409 `INSERT_RESUMEN_FALLIDO`) y el marcaje sigue activo en BD y en memoria, pero el ESP ya está parado. El reintento vuelve a publicar el paro (comprobado con dobles: 2 publicaciones). Si el operario no reintenta, el marcaje queda abierto con la máquina detenida. Una excepción que no sea de MySQL en ese INSERT responde `ERROR_CIERRE_REAL` sin el aviso de MQTT (comportamiento previo) | C (efecto en el ESP: I) | Media | `cierres_service.py:824-841, 846-862` | [I] El ESP deja de contar mientras el marcaje figura activo; la producción del intervalo hasta el reintento no se registra. Sin procedimiento de recuperación definido (P-11) | R-01, R-04 |

## Matriz de cierre parcial (detalle de R-01)

| Paso que falla | Estado resultante | Respuesta | Recuperación |
|---|---|---|---|
| `dtbOptimus` en el cálculo | Nada escrito | HTTP 500 | Reintentar |
| SELECT de existencia (error) | Nada escrito | 409 `NO_ENCONTRADO` | Reintentar |
| Publicación (`ok:false`) | Nada escrito | 409 `MQTT_NO_PUBLICADO` | Conectar MQTT (solo ADMIN) |
| Publicación "ok" con el broker caído | BD cerrada; ESP contando | ok | Manual |
| INSERT del resumen del operario | **Desde v20.24**: se aborta sin agregado ni DELETE; el marcaje y `datossensados` quedan intactos (en FINAL/MD el paro ya se publicó). Antes: resumen perdido y DELETE ejecutados | 409 `INSERT_RESUMEN_FALLIDO` | Reintentar el cierre (vuelve a publicar el paro; R-33) |
| Lecturas del cálculo (`datossensados`, suma MT) con error de MySQL | Resumen escrito con 0, negativo o sobrevalorado (E1) | ok | Manual |
| SELECT del agregado `F` | Fila `F` con solo los valores del operario actual (E2) | ok | Manual |
| INSERT `F` | Fila de usuario sin `F` | ok | Manual |
| DELETE `datossensados` | Huérfanos (N7) | ok | Manual |
| DELETE `marcajeactivo` | El marcaje reaparece; el reintento duplica el resumen con 0 o negativo | ok | Manual (DELETE con cuidado) |
| Excepción de Python intermedia | Parcial; lista `queries_ejecutados_antes_error` **solo en la respuesta HTTP** | 409 | Manual |
