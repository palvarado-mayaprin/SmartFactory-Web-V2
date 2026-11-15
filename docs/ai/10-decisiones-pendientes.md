# 10 — Decisiones pendientes, recomendaciones y discrepancias

> Nada de este documento es una regla de negocio aprobada, salvo lo registrado en §4 (decisiones aprobadas). Cuando un humano responda una pregunta, anota aquí la **respuesta, la fecha y quién la dio**, y actualiza los documentos afectados. Cambia [?]/[I] por [C] solo con evidencia.

## 1. Preguntas abiertas (P-xx)

| ID | Pregunta | Por qué importa | Cómo verificarlo (solo lectura) | Estado |
|---|---|---|---|---|
| P-01 | **Firmware ESP**: ¿se reinicia `cantpliegos` al recibir un inicio en `{mac}-OP`? ¿También si es la misma OP y actividad (relevo MT)? ¿Qué significan `100`, `0,1`, `0,0` y las fechas del payload? | Determina si los relevos MT y los MD calculan bien (N3, N4) y si es seguro cambiar los payloads | Especificación o código del firmware; prueba controlada en una máquina de pruebas | Abierta |
| P-02 | **Despliegue**: ¿cuántas instancias del backend están activas a la vez y dónde? ¿Alguna PC sigue con PyQt? ¿Qué origina las filas duplicadas en `datossensados`? | La hipótesis multi-backend [I] explica los duplicados y el estado desincronizado, **pero no está confirmada** | Inventario de PCs; procesos activos; conexiones al broker (lista de clientes) | Abierta |
| P-03 | **Esquema**: DDL real (`SHOW CREATE TABLE`) de `marcajeactivo`, `mensajes_mqtt`, `datossensados`, `resumenmarcajes`, `macdirectorio`, `superusuarios`. ¿Hay claves UNIQUE? | Define si las carreras R-06 pueden duplicar y si `INSERT IGNORE` en `mensajes_mqtt` deduplica | Consulta de solo lectura **autorizada** por un responsable | Abierta |
| P-04 | **Regla correcta de `cantidadreal`**: ¿la resta de MT debe acotarse a la misma sesión, recurso o MAC? ¿El agregado `F` debe excluir los `F` previos? ¿Se permiten negativos? | Corrige R-02 y R-13 | Decisión de negocio, con datos históricos de comparación | Abierta |
| P-05 | ¿**Quién consume** `resumenmarcajes` (filas `F`, columna `enviado`)? ¿Se exporta a Optimus? | Impacto de cualquier cambio en el cierre | Revisar procesos y ETL del ERP | Abierta |
| P-06 | ¿Cómo deben cerrarse los **improductivos**? ¿Solo FINAL? ¿Deben generar `F` y restar MT? | R-12, N2, N8 | Decisión de negocio | Abierta |
| P-07 | ¿Es intencional que el improductivo **ocupe la máquina** y **active el ESP**? | Otros operarios quedan bloqueados en esa máquina | Decisión de negocio | Abierta |
| P-08 | ¿Es intencional poder elegir **cualquier recurso** y no solo los de la OT? | R-10 (regresión respecto a PyQt) | Preguntar a planta y a quien desarrolló la v2 | Abierta |
| P-09 | El cambio `OR recursoalternativo` (`services/marcajes_service.py:32`): ¿está desplegado? ¿Qué significa "recurso alternativo"? ¿Existe la columna `macdirectorio.recursoalternativo` en cada BD? ¿Puede un valor coincidir con `recurso` de una fila y `recursoalternativo` de otra (`LIMIT 1` sin `ORDER BY`)? | Sin la columna, toda apertura se bloquea ("No existe sensor/MAC"); con duplicados, la MAC no es determinista | Autor del cambio; `SHOW COLUMNS FROM smartfactory.macdirectorio` | Abierta. "¿Debe commitearse?" **resuelto** (2026-11-15): sí, en un commit propio. **No modificar** |
| P-10 | ¿El umbral **48** del conglomerado es un límite físico? | 5.167 alertas: ¿ruido o problema real? | Planta e ingeniería del sensor | Abierta |
| P-11 | ¿Hay un **procedimiento manual** para corregir cierres incompletos o negativos? ¿Hay registro de incidencias? | Recuperación ante R-01 | Responsables de operación | Abierta |
| P-12 | ¿El repositorio de GitHub es **privado**? ¿Se rotarán las credenciales? | R-14 | Propietario del repo | Abierta |
| P-13 | **BD de desarrollo**: ¿dónde vivirá la instancia MySQL aislada (local, Docker, servidor de pruebas)? ¿Quién autoriza obtener el DDL (P-03) y ejecutar la implementación M-15? | Hace falta para probar SQL real y escrituras sin tocar producción | Decisión de infraestructura | Abierta |
| P-14 | **Observaciones E1–E6 de la Fase 4** (validación independiente). El usuario las aportó el 2026-11-13 | Completan la documentación de errores de BD, MQTT, identificación y UI | Contraste estático con el código (§3.3) | **Cerrada (2026-11-13)**: las 6 verificadas contra el código y documentadas (§3.3) |
| P-15 | **Pliegos incorrectos (v20.24)**: (a) confirmar con `SHOW COLUMNS` que `resumenmarcajes.pliegosIncorrectos` existe en **cada** BD a la que apunte un backend; (b) ¿quién consume el dato (P-05)? | Un backend contra una BD sin la columna rechaza todos los cierres (409, sin pérdida) | (a) `SHOW COLUMNS FROM smartfactory.resumenmarcajes`; (b) responsables de reportes y ERP | Abierta |
| P-16 | **Semántica de la fila `F`** (resumen `SMARTFACTORY` de un FINAL): hoy cada columna usa un alcance distinto (§3.4). ¿Cuál es el alcance correcto de cada una? En particular, ¿`pliegosIncorrectos` debe sumar solo el ciclo actual (desde la última `F`) o todo el histórico de numOp+actividad, como hace ahora? | La fila `F` mezcla un agregado acumulativo (`cantidadreal`, R-13), el último operario (`totalUsuario`) y la suma histórica de operarios (`pliegosIncorrectos`). Un reporte que los combine compara magnitudes incoherentes | Decisión de negocio, junto con P-04 y P-05. **No se modifica hasta decidirlo** | Abierta |

## 2. Recomendaciones técnicas (NO aprobadas; requieren autorización explícita)

Están ordenadas por relación entre beneficio y riesgo. **Ninguna debe implementarse sin aprobación.** Las que cambian resultados de negocio dependen además de la P-xx indicada.

| # | Recomendación | Mitiga | Depende de | Cambia resultados de negocio |
|---|---|---|---|---|
| M-01 | Pruebas de caracterización con mocks de `db.conexion` y `mqtt_monitor`. **Implementado (núcleo) el 2026-11-13**: ampliar con cada cambio | R-26 | — | No |
| M-02 | Registrar en log cada cierre real (inicio, cada sentencia, resultado) | R-21, R-01 (diagnóstico) | — | No |
| M-03 | **Implementado en parte (2026-11-14, aprobado en la Fase 6)**: el fallo del INSERT de operario aborta el cierre. Pendiente: Comprobar los resultados de INSERT/DELETE y abortar o avisar; usar una sola conexión con transacción en el cierre | R-01 | M-01 | No (solo errores) |
| M-04 | `publicar`: comprobar `is_connected()` y `rc`; valorar QoS 1 | R-04 | P-01 | No |
| M-05 | Distinguir error de "sin filas" en `dtbSmartFactory` (lanzar excepción o devolver un tipo explícito) | R-03 | M-01 | No |
| M-06 | Rotación de logs | R-24 | — | No |
| M-07 | Credenciales a variables de entorno y rotarlas | R-14 | P-12 | No |
| M-08 | Consultas parametrizadas | R-15 | M-01 | No |
| M-09 | UNIQUE en `datossensados.idmensaje` (migración) | R-08 | P-02, P-03 | Indirecto |
| M-10 | Acotar la resta de MT y corregir el agregado `F` | R-02, R-13 | **P-01, P-04, P-05** | **Sí** |
| M-11 | Filtrar recursos por OT | R-10 | **P-08** | **Sí** |
| M-12 | Autenticación y autorización en el servidor | R-05 | Diseño | Flujo de UI |
| M-13 | Persistir el relevo MT en el servidor | R-22 | P-01 | Flujo |
| M-14 | Retirar los endpoints heredados (`cerrar-real-bd`, simulaciones, `iniciar-improductivo-bd`) | R-11 | Confirmar que nadie los usa | No |
| M-15 | Aislamiento de BD por entorno (`db/entorno.py`, `db/consultas.py`, barreras B1-B5), según `13-entorno-desarrollo-bd.md` | R-25, R-03, R-15 | P-03, P-13 | No (producción idéntica por defecto) |

## 3. Discrepancias resueltas documentalmente

### 3.1 Entre las fases 1 y 2 de la auditoría

| Tema | Fase 1 dijo | Realidad [C] | Resolución |
|---|---|---|---|
| Orden INSERT ↔ MQTT en la apertura | "valida → publica MQTT → INSERT" | **INSERT y después publicar** (`persistencia_marcajes_service.py:248` y luego `273`) | Corregido. Tabla por ruta en `04-flujos-marcajes.md` §0 |
| Orden en el cierre | "publica paro antes de tocar BD" | Correcto para FINAL/MD; MT no publica; el cierre heredado no publica | Documentado por ruta |
| Varios backends | No se mencionaba | Fase 2: "[I fuerte] dos procesos" | **Se mantiene como hipótesis [I]** (P-02). Los duplicados son un hecho [C]; su causa no |
| Número de endpoints | Sin número | 27 HTTP + 2 WS (backend) + 5 HTTP (huella) | `03-endpoints-websockets.md` |

### 3.2 Entre comentarios o READMEs y el código (manda el código)

| # | Documento o comentario | Código real | Nivel |
|---|---|---|---|
| D1 | README_V14: añadir `UNIQUE uq_idmensaje` | No existe en el esquema (2026-10-12) | C |
| D2 | Docstring de `MqttMonitorService` (`mqtt_service.py:28-40`): "NO publica… NO modifica marcajes reales" | Publica inicio y paro | C |
| D3 | `publicar`: "Requiere que el servicio MQTT esté iniciado/conectado" | Solo comprueba "iniciado" | C |
| D4 | `procesar_persistencia_mqtt`: "Por defecto solo simula" | El valor por defecto es "1" → escribe | C |
| D5 | `marcajes_estado_service.py:6-7`: "Esta fase es de simulación" | Contiene los marcajes reales | C |
| D6 | `obtener_recursos_de_orden`: "Replica la lógica actual de PyQt" | PyQt filtra por OT; la web no | C |
| D7 | Mensaje de cierre: "Presione Conectar MQTT" | El botón solo es visible para ADMIN | C |
| D8 | README_V20: "el backend principal puede correr en el servidor central" | El CORS y los `.bat` solo permiten un backend local | C (configuración) / I (despliegue) |
| D9 | UI: "Solo el dueño del marcaje podrá cerrarlo con huella" | Solo en la UI | C |
| D10 | `construir_mensaje_mqtt_inicio`: fechas fijas "por ahora" | Siguen en producción | C |
| D11 | `seleccionar_produccion_unidad`: "revisar contra PyQt" | Constante `"UNIDAD"` | C |
| D12 | Nombre `mqtt_persistencia_simulada_service` / funciones `simular_*` | Forman parte del camino real | C |
| D13 | Ruta `/iniciar-improductivo-bd` | Abre un marcaje productivo | C |

### 3.3 Observaciones E1–E6 de la validación de la Fase 4 (P-14)

Contrastadas el 2026-11-13 con lectura estática del código; no se ejecutó nada contra BD ni MQTT. Ninguna cambia el comportamiento: **solo corrigen o precisan la documentación**.

| ID | Observación | Resultado | Evidencia | Documentado en |
|---|---|---|---|---|
| E1 | Errores de MySQL en el cálculo del cierre → `cantidadreal` o la suma de MT valen 0 sin aviso y el cierre continúa | **Confirmada [C]** | `cierres_service.py:157-164, 197, 320-321` | `05-cantidadreal.md` §1 y N5/N5b; `04` §4; `09` R-03 y matriz |
| E2 | Si falla el SELECT del agregado FINAL, se inserta igualmente una fila `F` con los datos del operario actual | **Confirmada [C]** | `cierres_service.py:825-834, 853-859` | `05` §1; `04` §4; `09` matriz |
| E3 | Si MySQL falla al iniciar, la lista de MAC queda vacía y MQTT sigue sin `-DATOS`; `_on_message` no tiene `try/except` propio | **Confirmada [C]**. Precisión añadida: el error también se borra del estado (124, 171). El efecto en paho se conserva como [I] | `mqtt_service.py:72-85, 87-100, 124, 200-254` | `06` §1 y §4; `09` R-09 y R-30 (nuevo) |
| E4 | `usuario.username` = `staf_name`; en `marcajeactivo`/`resumenmarcajes`, `username` = `staf_code` | **Confirmada [C]** | `usuarios_service.py:46-52`; `marcajes_service.py:353, 395` | `02` §3; `07` §2 |
| E5 | `None` solo ante `mysql.connector.Error`; otras excepciones se propagan | **Confirmada [C]**. Corrige la frase anterior "no lanza excepción" | `db/conexion.py:41-44` | `02` §1; `09` R-03 |
| E6 | El diálogo de éxito del improductivo puede mostrar `OP null` | **Confirmada [C, lectura estática]**; no reproducida en navegador | `app.js:1017, 1112, 1117, 1028-1051` | `04` §3; `09` R-31 (nuevo) |

### 3.4 Semántica actual de la fila `F` (v20.24) [C] — pendiente de decisión (P-16)

Una fila `F` se inserta en cada cierre FINAL, después de la fila del operario (`cierres_service::ejecutar_cierre_marcaje_real`). Filtro común: `numOp` + `actividad`. **No filtra** por recurso, MAC, fecha ni ciclo.

| Columna de la fila `F` | Valor actual | Incluye filas `F` anteriores | Si falla la consulta |
|---|---|---|---|
| `cantidadreal` | `SUM(cantidadreal)` de **todas** las filas | **Sí** (R-13: doble conteo en un segundo FINAL) | Valor del operario actual (E2) |
| `tiempoinicio` / `tiempofinal` | `MIN` / `MAX` de todas las filas | Sí (no altera MIN/MAX) | Tiempos del operario actual |
| `duracion` | `SUM(duracion)` de todas las filas | **Sí** (crece en cada FINAL) | Duración del operario actual |
| `totalUsuario` (pliegos buenos) | **Solo el valor del operario que cierra**, no una suma | No aplica | — |
| `pliegosIncorrectos` (v20.24) | `SUM(pliegosIncorrectos)` de las filas de operario (`estado` NULL, `MD` o `MT`), **de todos los ciclos** | **No** | `NULL` |
| `cantidadcot`, `wo_number`, `tk_id` | Los del cierre actual | — | — |

Consecuencias que hay que conocer antes de usar la fila `F` en reportes:
- Ante un segundo FINAL de la misma numOp+actividad, `pliegosIncorrectos` incluye las filas de operario del primer ciclo (acumula, pero **no duplica**). `cantidadreal` y `duracion` sí duplican, porque suman la `F` anterior.
- `totalUsuario` y `pliegosIncorrectos` de la misma fila `F` **no son comparables**: el primero es de un operario y el segundo es una suma.
- Los `NULL` (filas históricas o clientes antiguos) no cuentan en la suma: una `F` con 0 o un número bajo puede reflejar falta de registro, no ausencia de rechazos.
- En un improductivo (OP 12345), las filas de operario guardan `NULL`, así que la `F` también queda en `NULL`.

**No se ha modificado**. Cualquier cambio de alcance requiere la decisión P-16 (con P-04/P-05), y afecta a las pruebas `tests/test_pliegos_incorrectos.py::test_fila_f_suma_solo_filas_de_operario` y `tests/test_cierre_marcaje.py::test_agregado_final_no_excluye_filas_f`.

## 4. Decisiones aprobadas

| Fecha | Quién | Decisión | Implementación |
|---|---|---|---|
| 2026-11-14 | Usuario (Fase 6) | Registrar **pliegos incorrectos** al cerrar, como dato independiente de los pliegos buenos (`totalUsuario`) y de `cantidadreal`. No se restan | v20.24: `pliegosIncorrectos` en `resumenmarcajes` |
| 2026-11-14 | Usuario | Columna `pliegosIncorrectos INT DEFAULT NULL` creada por el usuario en `smartfactory.resumenmarcajes`. `NULL` = no registrado | Declarado; no verificado por el asistente (P-15 a) |
| 2026-11-14 | Usuario | Se pide y guarda en **FINAL, MD y MT** (incluida la pausa improductiva, que es un MD). En tiempos improductivos (OP 12345) no se pide y se guarda `NULL` para no cambiar su comportamiento (criterio técnico) | `docs/ai/04-flujos-marcajes.md` §4 |
| 2026-11-14 | Usuario | Fila `F` = **suma de las filas de operario** (excluye `F` anteriores). El alcance por ciclo queda pendiente (P-16, §3.4) | `_construir_query_suma_pliegos_incorrectos` |
| 2026-11-14 | Usuario | Si falla el INSERT del resumen del operario → **abortar** sin DELETE (mitigación parcial de R-01, M-03) | `ejecutar_cierre_marcaje_real`; prueba `test_insert_resumen_fallido_aborta_sin_delete` |
| 2026-11-15 | Usuario | Versionar el `OR recursoalternativo` en un commit propio, previo a v20.24, con su prueba. Sus preguntas de semántica y columna siguen abiertas (P-09) | `test_mac_por_recurso_incluye_recurso_alternativo` |
| 2026-11-15 | Usuario | Versión **20.24.0** (`main.py`, `templates/index.html`) y `readme/README_V20_24.md`. Despliegue productivo **no autorizado** | — |
