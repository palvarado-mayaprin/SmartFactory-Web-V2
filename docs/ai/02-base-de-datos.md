# 02 — Base de datos y persistencia

> ⚠️ Las credenciales y hosts están en claro en `db/conexion.py` (y los valores por defecto de MQTT en `services/mqtt_service.py:64-65`). **No los copies en documentación, logs ni mensajes.** Ver `09-riesgos.md` R-14.

## 1. Orígenes de datos [C]

| Clase (`db/conexion.py`) | Destino | Uso | Parámetros SQL | Ante error |
|---|---|---|---|---|
| `dtbSmartFactory` (9-50) | MySQL `smartfactory` | Lectura **y escritura** | **No**: query como string | Ante `mysql.connector.Error`: `print` y devuelve **`None`**. Cualquier otra excepción **se propaga** (ver abajo) |
| `dtbOptimus` (53-73) | MySQL Optimus `mayaprin` (ERP) | Lectura (`_obtener_wo_tk`) | No | **Lanza excepción** (sin `try`) |
| `dtbOptimus1` (76-109) | Igual | Lectura (usuarios, OP, actividades) | **Sí** (`%s`) | Devuelve `None` |
| `dtbEntregasDiarias` (112-140) | SQL Server `entregasDiarias` | Sin uso activo (consulta comentada) | No | `None`. El `finally` fallaría si `connect` falla, porque `cursor` queda sin definir [C] |

### Semántica de `dtbSmartFactory.consultaSmartFactory` [C]

- Abre una **conexión nueva por consulta**. No hay pool. **No hay transacciones entre sentencias.**
- Si la query (tras `strip().lower()`) empieza por `insert`, `update` o `delete` → `commit` y devuelve la cadena `"Operación exitosa"`, **aunque haya afectado 0 filas**.
- Si no → `fetchall()`: una lista, **vacía** si no hay filas.
- Ante un error de MySQL → `None`.
  - Solo se captura **`mysql.connector.Error`** (`db/conexion.py:41-44`). Cualquier otra excepción (por ejemplo, un error de Python en el propio método) **se propaga** al llamador; el `finally` cierra cursor y conexión igualmente [C] (E5, Fase 4).
  - ⚠️ Casi todos los llamadores usan `if not resultado`, que **no distingue "sin filas" de "error"**. Ver R-03.
- Al escribir código nuevo contra esta clase, trata `None` como error, `[]` como "sin filas" y **no supongas** que nunca lanza.

### Construcción de SQL [C]

- Se usan f-strings escapando solo `'` → `''`:
  - `limpiar_sql` (`services/marcajes_service.py:8-19`)
  - `_limpiar_sql` (`services/auth_service.py:6-13`)
  - `_escape_sql` (`services/mqtt_persistencia_simulada_service.py:59-65`)
- No se escapa `\`. Con la configuración por defecto de MySQL (barra invertida como escape), un valor que termine en `\` puede romper la consulta [I]. Las entradas son internas, pero `username`/`password` del login elevado las escribe el usuario. Ver R-15.

## 2. Tablas `smartfactory` (MySQL)

### Esquema observado [C, foto del 2026-10-12 tomada del `SHOW COLUMNS` de `logs/cantidadreal_negativos.log`]

- **`datossensados`**:
  - Columnas: `idrelacion int PK AI`, `numOp int (MUL)`, `cantpliegos int`, `actividad varchar(50)`, `actividadreal double`, `velocidadreal int`, `fecha date`, `tiempo time`, `fechatiempo datetime`, `flagcorreo bit(1)`, `mac varchar(12)`, `unidadesSensadasPeriodo int`, `idmensaje varchar(100)`.
  - **`idmensaje` no tiene índice UNIQUE.**
- **`resumenmarcajes`**:
  - Columnas: `idrelacion int PK AI`, `numOp int (MUL)`, `recurso varchar(50)`, `actividad varchar(50)`, `cantidadcot int`, `cantidadreal int`, `username varchar(50)`, `tiempoinicio datetime`, `tiempofinal datetime`, `duracion bigint`, `estado varchar(2)`, `enviado int`, `totalUsuario int`, `wo_number int`, `tk_id int`, `produccionUnidad varchar(100)`, `usuarioFinalizacion varchar(50)`, `variable01 int`.
  - **`pliegosIncorrectos int DEFAULT NULL`** (v20.24). La creó el usuario en `smartfactory.resumenmarcajes` el 2026-11-14 **[declarado por el usuario; no verificado con `SHOW COLUMNS`]**. Es INT con signo, así que **la BD no impide negativos**: los rechazan la API (422) y el servicio. Significado: pliegos incorrectos o rechazados que declara el operario. Es **independiente** de `totalUsuario` (pliegos buenos declarados) y de `cantidadreal` (sensor). `NULL` = no registrado (filas históricas, clientes antiguos y tiempos improductivos). En la fila `F` = suma de las filas de operario de numOp+actividad (excluye `F`, incluye ciclos anteriores; pendiente P-16).
  - **Sin claves únicas de negocio.**
- **`marcajeactivo`, `mensajes_mqtt`, `macdirectorio`, `superusuarios`**: esquema **[?]**. Solo se conocen las columnas que usa el código. Se desconoce si `marcajeactivo` tiene UNIQUE (P-03).

> `numOp` es `int` en BD. El código lo trata como texto (`'12345'`). MySQL lo convierte implícitamente [C]. El valor MQTT `"N/A"` se transforma en `"100"` antes de insertar (`services/mqtt_persistencia_simulada_service.py:88-90`).

### Quién lee y escribe cada tabla [C]

| Tabla | Operación | Archivo::función (línea) | Disparador |
|---|---|---|---|
| `marcajeactivo` | INSERT | `persistencia_marcajes_service::iniciar_marcaje_real_bd` (248), `::iniciar_marcaje_improductivo_bd` (387) | Apertura productiva, improductiva o relevo |
| `marcajeactivo` | DELETE (`numOp+actividad+username`) | `cierres_service::ejecutar_cierre_marcaje_real` (868) | Cierre FINAL/MD/MT |
| `marcajeactivo` | DELETE (`username+numOp+recurso+actividad[+topic]` LIMIT 1) | `persistencia_marcajes_service::cerrar_marcaje_real_bd` (531) | Endpoint heredado `cerrar-real-bd`, **sin uso en la UI** |
| `marcajeactivo` | SELECT | `usuarios_service::consultar_marcaje_activo`, `marcajes_service::consultar_marcaje_activo_por_recurso_o_topic`, `persistencia_marcajes_service::validar_apertura_marcaje_real`, `::listar_marcajes_activos_bd`, `cierres_service::ejecutar_cierre_marcaje_real` (733) | Validaciones y sincronización |
| `resumenmarcajes` | INSERT fila de usuario | `cierres_service::ejecutar_cierre_marcaje_real` (792). Texto armado en `simular_cierre_marcaje` (558-573) | Todo cierre |
| `resumenmarcajes` | INSERT fila `SMARTFACTORY`/`F` | `cierres_service::ejecutar_cierre_marcaje_real` (853-860) | Solo FINAL |
| `resumenmarcajes` | SELECT SUM MT, agregado FINAL, último registro | `_obtener_suma_mt_anterior` (320), `ejecutar_cierre_marcaje_real` (816-822), `obtener_ultimo_resumen_recurso_usuario` (58-102) | Cálculo y flujos posteriores |
| `resumenmarcajes` | SELECT `SUM(pliegosIncorrectos)` de filas de operario (v20.24) | `_construir_query_suma_pliegos_incorrectos` (49-55), ejecutada en `ejecutar_cierre_marcaje_real` (836-843) | Solo FINAL, para la fila `F` |
| `datossensados` | INSERT IGNORE | `mqtt_persistencia_simulada_service::procesar_persistencia_mqtt` (333) | Cada mensaje `-DATOS` con `numOp≠100` |
| `datossensados` | DELETE (`numOp+actividad+mac`) | `cierres_service::ejecutar_cierre_marcaje_real` (864) | Todo cierre (también MT) |
| `datossensados` | SELECT (cantidad, tiempos) | `cierres_service::_obtener_datos_cierre_datossensados` (167-216) | Cierre |
| `mensajes_mqtt` | INSERT IGNORE | `procesar_persistencia_mqtt` (324) | Cada mensaje `-DATOS` |
| `mensajes_mqtt` | SELECT último `cantpliegos` por MAC | `_buscar_cantpliegos_anterior` (111-154) | Cada mensaje `-DATOS` |
| `macdirectorio` | SELECT | `marcajes_service::obtener_mac_por_recurso` (22-41), `ordenes_service::obtener_recursos_existentes_improductivo` (63-88), `mqtt_service::_obtener_macs_desde_bd` (72-85) | Apertura, improductivo, arranque MQTT |
| `superusuarios` | SELECT `*` | `auth_service::validar_usuario_elevado` (16-58). El rol se lee por **posición** `fila[8]` | Login elevado |

Columnas de `resumenmarcajes` que la web **no escribe** [C]: `enviado`, `produccionUnidad`, `usuarioFinalizacion`. Quién las usa: **[?]** (P-05).

### Funciones de cada tabla según la documentación histórica [I]

- `marcajeactivo`: marcajes abiertos en este momento. Una fila por operario activo.
- `datossensados`: tabla **temporal operativa**. Se limpia al cerrar (README_V20 "Notas importantes").
- `mensajes_mqtt`: **histórico permanente** (README_V20).
- `resumenmarcajes`: resultado contable de cada marcaje. La fila `F` es el agregado de la actividad.

### Valores de `resumenmarcajes.estado` [C] (`cierres_service.py:558`, `857`)

| Valor | Significado |
|---|---|
| `NULL` | Fila del operario en un FINAL |
| `'MD'` | Reporte parcial con la máquina detenida (MD) |
| `'MT'` | Reporte parcial sin detener la máquina (MT) |
| `'F'` | Agregado `SMARTFACTORY` de un FINAL |

`variable01 = 1` marca un MD originado por la *pausa por actividad improductiva* (v20.22) [C].

## 3. Tablas Optimus (`mayaprin`, solo lectura) [C]

| Tabla | Uso | Archivo |
|---|---|---|
| `staf` | Operarios (`staf_code`, `staf_name`, `staf_resource`, `staf_discontinued`) | `services/usuarios_service.py:34-43` |
| `wo200` | OT → OP real (`wo_job`) | `services/ordenes_service.py:110` |
| `job200` | Descripción y cantidad de la OP | `services/ordenes_service.py:118` |
| `wo_task200`, `act`, `cc` | Recursos y actividades | `services/ordenes_service.py:24-31, 176-228` |
| `wo` | `wo_number`/`tk_id` para el resumen | `services/cierres_service.py:275-307` |

### ⚠️ `username` no significa lo mismo en todas partes [C] (E4, Fase 4)

| Dónde | Contenido de `username` | Evidencia |
|---|---|---|
| Respuesta de identificación (`usuario.username` en la UI) | **`staf_name`** (nombre del operario) | `services/usuarios_service.py:46-52` |
| `smartfactory.marcajeactivo.username` y `resumenmarcajes.username` (filas de usuario) | **`staf_code`** (el `codigo_usuario` que envía la UI) | `services/marcajes_service.py:353, 395`; `services/persistencia_marcajes_service.py:114` |
| `resumenmarcajes.username` en filas `F` | Literal `'SMARTFACTORY'` | `services/cierres_service.py:853-859` |
| `smartfactory.superusuarios.username` | Login del usuario elevado | `services/auth_service.py:16-58` |

En la UI, el código del operario está en `usuarioActual.code`. Para buscar, filtrar o comparar marcajes usa el **código** (`staf_code`), nunca `usuarioActual.username`.

## 4. Problemas, recomendaciones y pendientes

- **Problemas**: R-01 (cierre no atómico), R-03 (error tratado como "sin filas"), R-08 (sin UNIQUE en `idmensaje`), R-14 (credenciales), R-15 (SQL por concatenación). Detalle en `09-riesgos.md`.
- **Recomendaciones (no aprobadas)**:
  - Capa de repositorio con parámetros.
  - Transacción única para el cierre.
  - Distinguir error de vacío lanzando excepción.
  - Credenciales en variables de entorno.
  - Ver `10-decisiones-pendientes.md`.
- **Pendiente**:
  - Obtener el DDL real (`SHOW CREATE TABLE`) de las 6 tablas `smartfactory` en modo lectura (P-03).
  - Identificar a los consumidores de `resumenmarcajes` (P-05).
