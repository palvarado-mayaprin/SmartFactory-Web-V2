# SmartFactory Web v2 — Fase 2: reglas de negocio y flujos de marcaje

> **INSTANTÁNEA HISTÓRICA (2026-11-13). No se edita.** Copia literal del informe de la Fase 2, preservada a partir del archivo temporal de la sesión.
> La documentación vigente está en `docs/ai/` (índice: `docs/ai/README.md`). Si hay diferencias, manda la documentación vigente.
> Matices añadidos en la Fase 3:
> - La explicación de "varios backends" para las filas duplicadas en `datossensados` es una **hipótesis [I]**, no un hecho. Ver `docs/ai/10-decisiones-pendientes.md` (P-02).
> - Las líneas citadas corresponden al commit `3d325c0` más el cambio sin commit de `services/marcajes_service.py:32`.
>
> Texto original:
>
> Informe de trabajo (borrador para revisión). No es documentación permanente.
> Análisis 100 % estático: código, `git` de solo lectura, logs locales existentes y READMEs históricos.
> No se ejecutó el backend, no se consultó la BD ni el broker y no se modificó ningún archivo del repositorio
> (el cambio sin commit de `services/marcajes_service.py:32` sigue intacto).

**Niveles de certeza**
- **[C] Confirmado**: comportamiento leído en el código ejecutable o evidencia directa en los logs.
- **[I] Inferido**: deducción razonable a partir del código o la evidencia, no demostrada.
- **[?] No verificable**: depende de componentes que no están en el repo (firmware ESP, `.exe` de huella, esquema completo de BD, despliegue).

Convención de referencias: `archivo:línea` o `archivo::función`.

---

## 0. Fuentes de evidencia adicionales usadas en esta fase

| Fuente | Qué aporta | Limitación |
|---|---|---|
| `logs/cantidadreal_negativos.log` (1 evento, 2026-10-12 16:12) | Incluye `SHOW COLUMNS` reales de `datossensados` y `resumenmarcajes`, el detalle de 1.548 filas de `datossensados` y las filas MT usadas en el cálculo | Es una foto de un solo momento |
| `logs/mqtt_persistencia.log` (658 MB) | Qué inserta este proceso y cuántas veces | Solo registra este proceso |
| `logs/mqtt_conglomerado_alertas.log` (5.167 alertas, 2026-06-15 → 2026-10-12) | Distribución de los tipos de cálculo del conglomerado | Solo registra los casos con valor > 48 |
| `logs/marcajes_reales.log` | Aperturas reales y resultado de la publicación MQTT | No registra los cierres de `ejecutar_cierre_marcaje_real` (ver §6) |
| `readme/README_V*.md` | Intención declarada de cada versión | Documentación histórica, no ejecutable |
| `../src` (app PyQt heredada) | Solo para comparar la regla original | No forma parte de este repo |

### 0.1 Esquema observado (según `SHOW COLUMNS` del log, 2026-10-12) [C]

- **`datossensados`**: `idrelacion int PK AI`, `numOp int (MUL)`, `cantpliegos int`, `actividad varchar(50)`, `actividadreal double`, `velocidadreal int`, `fecha date`, `tiempo time`, `fechatiempo datetime`, `flagcorreo bit(1)`, `mac varchar(12)`, `unidadesSensadasPeriodo int`, `idmensaje varchar(100)`.
  - **`idmensaje` no tiene índice UNIQUE** (no figura `UNI`).
- **`resumenmarcajes`**: `idrelacion int PK AI`, `numOp int (MUL)`, `recurso`, `actividad`, `cantidadcot int`, `cantidadreal int`, `username`, `tiempoinicio datetime`, `tiempofinal datetime`, `duracion bigint`, `estado varchar(2)`, `enviado int`, `totalUsuario int`, `wo_number int`, `tk_id int`, `produccionUnidad varchar(100)`, `usuarioFinalizacion varchar(50)`, `variable01 int`.
  - **No hay ninguna clave única de negocio.**
  - La web **no escribe** `enviado`, `produccionUnidad` ni `usuarioFinalizacion` [C].
- **`marcajeactivo`, `mensajes_mqtt`, `macdirectorio`, `superusuarios`**: [?] no aparecen en ningún log. Por el código se sabe qué columnas se usan, pero no sus claves.
  - Especialmente: [?] se desconoce si `marcajeactivo` tiene UNIQUE por `username`, `recurso` o `topic`, y si `mensajes_mqtt.idmensaje` es UNIQUE.

---

## 1. Arquitectura de estado: hay tres "fuentes de verdad"

| Estado | Dónde vive | Quién lo escribe | Quién lo lee | Persistencia |
|---|---|---|---|---|
| Marcajes activos persistentes | `smartfactory.marcajeactivo` | Apertura (INSERT) y cierre (DELETE) | Validaciones, sincronización | BD |
| Marcajes activos en vivo | `_MARCAJES_ACTIVOS_SIMULADOS` (`services/marcajes_estado_service.py:8`), lista en memoria **por proceso** | Endpoints de apertura y cierre, sincronización, hilo MQTT | `consultar_marcaje_activo`, bloqueo `RECURSO_O_TOPIC_MEMORIA`, sidebar | Se pierde al reiniciar |
| Estado de la pantalla | Variables globales JS (`app.js:1-12`): `usuarioActual`, `marcajeActivoUsuario`, `relevoMtPendiente`, rol elevado… | Navegador | Navegador | Se pierde al recargar (el botón *Cancelar* recarga: `app.js:33-35`) |

### Hallazgo de despliegue [I fuerte]

Probablemente hay **varias instancias del backend funcionando a la vez**, una por PC de marcaje. Indicios:

- Los `.bat` arrancan uvicorn en `127.0.0.1:8000` [C].
- El servicio de huella solo permite CORS desde `127.0.0.1:8000` y `localhost:8000` (`huella_local/main.py:55-64`) [C]. Un backend central en otro origen no podría llamar a la huella local desde el navegador.
- En el log de diagnóstico, **cada uno de los 774 mensajes DATOS aparece exactamente 2 veces** en `datossensados`, y ambas copias tienen `idmensaje` [C].
  - Este proceso registra cada `idmensaje` una sola vez en `mqtt_persistencia.log` (muestra de 200 mensajes: 200 × 1) [C].
  - La app PyQt heredada inserta en `datossensados` **sin** `idmensaje` (`../src/servicios/mqtt_conexion.py:344`) [C], así que no explica la segunda copia.
  - Conclusión: había **dos procesos de esta web** suscritos al broker e insertando [I].

Consecuencias, si se confirma:

- Cada backend tiene su propia memoria y sus propios WebSockets. Una pantalla no ve en tiempo real los marcajes abiertos o cerrados desde otra PC hasta que sincroniza [I].
- Las tablas de sensores se duplican N veces, una por backend activo [C para N=2 en la muestra].
- Cada backend publica MQTT con su propia conexión. Esto no es un problema en sí [I].

---

## 2. Flujo F1 — Identificación del operario (biometría)

### Secuencia

1. **UI**: botón *Identificar con huella* (`templates/index.html:101`) → `app.js::identificarConHuellaLocal` (82-107).
2. **El navegador** hace `POST http://127.0.0.1:9001/api/huella/identificar`, al servicio local de la misma PC.
3. **Servicio de huella** (`huella_local/main.py::identificar_huella`, 517-568):
   1. Toma un lock **no bloqueante** de proceso (`LECTURA_HUELLA_LOCK`, 70 y 527). Si está ocupado, responde `ok:false` con "Ya hay una lectura…" [C].
   2. En modo `SIMULACION` devuelve siempre `SMARTFACTORY_HUELLA_USUARIO` (por defecto un código fijo) [C]. El `.bat` piloto fija el modo `REAL`.
   3. `_identificar_real` (377-427) prueba hasta 3 variantes de comando (`enrollFingerPrint`, `+\n`, `+\r\n`). En cada intento:
      - `_preparar_exe_para_lectura`: `taskkill /F` del `.exe`, espera 0,7 s, lo relanza y espera hasta 12×0,5 s a que el puerto 8888 quede en LISTENING (comprobado con `netstat`).
      - `_enviar_comando_socket`: abre TCP, envía el comando y hace **un único `recv(4096)`** con timeout de 30 s.
   4. `_normalizar_respuesta` (307-329): divide la respuesta por comas y **toma el primer campo como `codigo_usuario`**. Sustituye `?` por `ñ`.
   - Peor caso de latencia: ≈3 × (0,7 + 6 + 30) s ≈ 110 s [C por los parámetros].
4. **El navegador** escribe el código en `#codigoUsuario` y llama a `identificarUsuario` (`app.js:131-237`) → `POST /api/usuario/identificar-prueba` con `{codigo_usuario}`.
5. **Backend** (`api/usuarios_api.py:9-23`):
   - `usuarios_service::identificar_usuario_prueba` (30-52): `SELECT staf_code, staf_name, staf_resource FROM staf WHERE staf_discontinued='0' AND staf_code=%s` en Optimus, con parámetros.
   - Si no existe, responde 404 "Usuario no encontrado o descontinuado".
   - `usuarios_service::consultar_marcaje_activo` (55-85): busca **primero en memoria** por `username`/`codigo_usuario` y **después** en `marcajeactivo WHERE username='…' LIMIT 1` (f-string).
6. **UI**: decide el siguiente paso.
   - Si hay marcaje activo → panel de cierre; queda bloqueado abrir una OP nueva.
   - Si hay `relevoMtPendiente` (en memoria JS) → relevo automático (F6).
   - Si no → paso 2, ingreso de OP.

### Reglas y observaciones

| # | Regla | Nivel | Referencia |
|---|---|---|---|
| R1.1 | La identidad se toma del primer campo que devuelve el `.exe`; el backend **no verifica** que provenga de una huella | C | `huella_local/main.py:310`, `api/usuarios_api.py:9` |
| R1.2 | La identificación manual existe para cualquiera que llame a la API. En la UI el campo solo está oculto con CSS para quien no es ADMIN | C | `index.html:104-108`, `app.js:1919-1934` |
| R1.3 | Un usuario con marcaje activo no puede abrir otro desde la UI. La API lo vuelve a validar al abrir (F2) | C | `app.js:165-180` |
| R1.4 | Si Optimus falla, `dtbOptimus1` devuelve `None` y el operario ve "Usuario no encontrado o descontinuado" (mensaje engañoso) | C | `db/conexion.py:96-104`, `usuarios_service.py:45-46` |
| R1.5 | Si la memoria está desfasada (marcaje ya cerrado desde otro backend o desde PyQt), el usuario ve un marcaje que ya no existe. El cierre fallará con 409 `NO_ENCONTRADO` | C (mecanismo) / I (frecuencia) | `usuarios_service.py:66-71`, `cierres_service.py:680-688` |
| R1.6 | "Cierre general" desde el sidebar solo dispara la huella; el marcaje que se cierra es **el de quien pone la huella**, no el de la tarjeta pulsada | C | `app.js:1552-1563` |
| R1.7 | Cierre SU/ADMIN: usa el objeto marcaje de la tarjeta sin huella. No se registra quién cerró (`usuarioFinalizacion` existe en la tabla y no se usa) | C | `app.js:1499-1503, 1575-1595` |
| R1.8 | El lock de huella es por proceso; dos pestañas en la misma PC comparten lector y una recibirá "lectura en proceso" | C | `huella_local/main.py:527` |

**Riesgos de modificación**
- Cambiar el formato de respuesta del `.exe` o el `split(",")` rompe la identificación de todas las PCs.
- Endurecer la autenticación del backend (exigir un token emitido por el servicio de huella) implica cambiar a la vez `huella_local`, `app.js` y todos los endpoints.

---

## 3. Flujo F2 — Inicio de marcaje productivo

### Secuencia en la UI

1. *Buscar OP* (`app.js::buscarOp`, 1092-1135) → `POST /api/op/buscar`.
2. Se selecciona el recurso (`#recursoSelect`); con `onchange` se cargan las actividades (`POST /api/actividades/recurso`).
3. Opcionalmente, *Agregar actividad no cotizada* (`POST /api/actividades/no-cotizadas`). Solo añade la actividad a la lista local [C].
4. Clic en una actividad → `seleccionarActividad` (1305-1391) → confirmación Swal → `POST /api/marcajes/iniciar-real-bd`.

### Backend: búsqueda de la OP (`ordenes_service::buscar_orden_produccion`, 92-155)

| Paso | Detalle | Nivel |
|---|---|---|
| Normalizar OP | Se quedan solo los dígitos; debe estar en el rango 10.000-1.000.000 | C |
| Usuario | Vuelve a consultar `staf` (Optimus) | C |
| OT | `num_ot = op + "01"` | C |
| OP real | `SELECT wo_job FROM wo200 WHERE wo_number=num_ot`. **La OP que se guarda es `wo_job`**, que puede no coincidir con lo que tecleó el operario | C |
| Datos | `job200.j_title1` (descripción) y `j_quantity` (pasa a ser `cantidadcot`) | C |
| Recursos | `obtener_recursos_de_orden` (17-60): la consulta **no filtra por OT** y devuelve todos los centros de costo con tareas en `wo_task200`. La app PyQt sí filtraba `WHERE wo_number = '{barcode}'` (`../src/widgets/acciones_botones.py:2284-2289`). **Regresión respecto al sistema original**, presente desde el commit inicial. Además hace `print()` de todo el resultado en consola | C |
| Recurso sugerido | El primer código de recurso que sea **subcadena** de `staf_resource` (`codigo in usuario_resource`). Puede sugerir un recurso equivocado si los códigos se solapan (p. ej. "PEG" dentro de "PEG CAJ2") | C (mecanismo) / I (impacto) |
| Actividades | `wo_task200 ⨝ act WHERE tk_wonum=num_ot AND act_cc=recurso` | C |

Como no se filtra por OT, el operario puede elegir un recurso que no pertenece a la OP. En ese caso verá 0 actividades cotizadas, pero podrá añadir una **no cotizada** del catálogo de ese recurso y abrir el marcaje igualmente [C por el código].

### Backend: apertura (`api/marcajes_api.py:77-99` → `persistencia_marcajes_service::iniciar_marcaje_real_bd`, 190-325)

1. `marcajes_service::simular_inicio_marcaje` → `preparar_inicio_marcaje` (181-249). **Este código "simulado" forma parte del camino real.**
   1. **V1**: el usuario no tiene marcaje activo (`consultar_marcaje_activo`, memoria y luego BD).
   2. **V2**: obtener la MAC: `SELECT mac FROM macdirectorio WHERE recurso='R' OR recursoalternativo='R' LIMIT 1` (`marcajes_service.py:22-41`).
      - El `OR recursoalternativo` es el **cambio sin commit**: sin él, un recurso que solo figura como alternativo responde "No existe sensor/MAC" [C].
      - Si dos filas coinciden, `LIMIT 1` sin `ORDER BY` elige una de forma no determinista [C].
   3. `topic = "{mac}-OP"`.
   4. **V3**: la máquina está libre en BD: `marcajeactivo WHERE recurso='R' OR topic='T'`.
   5. **V4**: la máquina está libre en memoria (mismo recurso o topic).
   6. `produccionUnidad = "UNIDAD"`, constante (`marcajes_service.py:122-131`) [C].
   7. Payload MQTT de inicio (`134-151`): `"{num_op},{recurso},{actividad},{cantidad},100,2024/10/09,08:31:55,2024/10/09,18:30:55,0,1"`, **con fechas fijas de 2024** [C]. Si `recurso` o `actividad` contienen comas, el formato se rompe [C].
   8. Se arma el texto del INSERT (`154-178`), escapando solo `'`.
2. `validar_apertura_marcaje_real` (105-187):
   - **V5**: campos críticos no vacíos.
   - **V6**: el usuario no está en `marcajeactivo` (repite V1, solo en BD).
   - **V7**: no hay fila con el mismo topic o recurso (repite V3).
3. Si `ENABLE_REAL_DB_WRITES` está desactivado → `ok:false`, modo `PROTEGIDO` (HTTP 409).
4. **Escritura**: `INSERT INTO smartfactory.marcajeactivo (numOp, descrip, cantidad, recurso, actividad, username, topic, produccionUnidad)` (248).
   - Si `dtbSmartFactory` devuelve `None` → `ok:false`.
   - **No hay columna de hora de inicio** en lo que se inserta [C].
5. **Publicación MQTT** (273-295), solo si `ENABLE_REAL_MQTT_PUBLISH`: `mqtt_monitor.publicar("{mac}-OP", payload)`.
   - Se hace **después** del INSERT. Si falla, el marcaje queda abierto igualmente con `ok:true` y el mensaje "…pero MQTT de inicio NO fue publicado" [C].
   - El frontend solo lo muestra en el log, que es visible únicamente para ADMIN (`app.js:1356-1359`, `index.html:197`) [C].
6. Línea `APERTURA_REAL_OK` en `logs/marcajes_reales.log`.
7. **API**: `agregar_o_actualizar_marcaje_estado` en memoria, con `id = "REAL_BD|user|op|recurso|actividad"` y `fecha_inicio = ahora` (hora del servidor, no de la BD) + broadcast `MARCAGES_ACTIVOS_ACTUALIZADOS` a los WebSockets **de este proceso**.

### Efectos sobre otros [C]

- La máquina (recurso o topic) queda bloqueada para cualquier otro operario mientras exista la fila.
- El ESP empieza a enviar `{mac}-DATOS` [I/? según el firmware], que se persisten (F8).

### Riesgos de modificación

- El payload de inicio lo consume el firmware: cualquier cambio de formato es [?] sin la especificación del ESP.
- Corregir el filtro de recursos cambia qué recursos ve el operario. Hay que validar con planta si alguien depende hoy de ver recursos "ajenos" a la OP.
- V1/V6 y V3/V7 están duplicadas; si se cambia una regla hay que cambiar las dos.

---

## 4. Flujo F3 — Inicio de marcaje improductivo

### Formas de entrar [C]

- **A) Directa**:
  - El operario identificado elige un motivo (`#ImproductivoSelect`: COMIDA / MANTO / FALLA / CAMBIO) → *Marcar Tiempo Improductivo* (`app.js::SeleccionarRecurso`, 942-972) → `POST /api/op/buscarRecursosExistentes`, que devuelve **todos** los recursos de `macdirectorio` (`ordenes_service.py:63-88`).
  - **Al cambiar** el `<select id="recursoSelectImproductivo" onchange="marcajeTiempoImproductivo()">` (`index.html:175`) se lanza el inicio, tras una confirmación Swal (`app.js:1000-1087`).
  - Consecuencia [C]: si el operario quiere el **primer** recurso de la lista (ya seleccionado), el `onchange` no se dispara y no puede iniciar sin elegir antes otro recurso.
- **B) Pausa por actividad improductiva** (F5b): después de un cierre MD forzado.

### Backend (`api/marcajes_api.py:101-123` → `iniciar_marcaje_improductivo_bd`, `persistencia_marcajes_service.py:329-464`)

- Valores fijos enviados por el frontend: `num_op="12345"`, `cantidad="12345"`, `descripcion="Tiempo Improductivo"` [C].
- **12345 es el centinela de "improductivo"**; no hay otro campo que lo identifique (README_V20_23) [C].
- Se aplican las mismas validaciones V1-V7. **La máquina queda ocupada** durante el tiempo improductivo: nadie más puede marcar en ese recurso mientras dura, por ejemplo, la comida [C].
- **Se publica el inicio MQTT al ESP con OP 12345** [C]. El log de diagnóstico muestra después DATOS reales `12345,0,COMIDA,0.00,0.00,…` cada ≈3 s, que se insertan en `datossensados` (1.548 filas en 38 min, duplicadas ×2) [C].
- Inconsistencia [C]: en `simular_inicio_marcaje_improductivo` (363-402) los `valores` **no incluyen `descrip` ni `cantidad`**. El marcaje en memoria queda con `cantidad=None`, mientras que el INSERT en BD sí lleva 12345.
  - Si después se cierra con el objeto de memoria → `cantidadcot = 0`.
  - Si se cierra con el objeto leído de BD → `cantidadcot = 12345` (`cierres_service.py:430`).
- El endpoint `/api/marcajes/iniciar-improductivo-bd` (125-147) **llama a la apertura productiva** a pesar de su nombre. La UI no lo usa, pero está expuesto [C].
- La `actividad` (COMIDA, MANTO…) **no existe en Optimus**: `_obtener_wo_tk` devuelve `wo_number=0, tk_id=0` (lo confirma el log) [C].

---

## 5. Flujos de cierre: F4 FINAL, F5 MD (y pausa improductiva), F6 MT (y relevo)

### 5.1 Camino común (`app.js::ejecutarCierreRealMarcajeActivoDelUsuario` 661-801 → `POST /api/marcajes/ejecutar-cierre-real` → `cierres_service::ejecutar_cierre_marcaje_real` 619-818)

**Entrada**: el **objeto marcaje completo que envía el navegador** (`marcaje: dict`, sin esquema; `models/schemas.py:57`), `tipo_cierre ∈ {FINAL, MD, MT}`, `total_usuario` (cantidad manual) y `pausa_improductiva`.

**Pasos en el frontend antes de llamar** [C]:

1. Si `numOp == "12345"`: consulta `ultimo-resumen-recurso-usuario` **antes** del cierre (F5c).
2. Confirmación Swal.
3. `total_usuario` vacío → 0, salvo en la pausa improductiva, donde es obligatorio (`app.js:387-406`).

**Pasos en el backend (orden real de ejecución)**:

| # | Acción | Si falla | Nivel |
|---|---|---|---|
| 0 | `simular_cierre_marcaje` (404-615): valida el tipo; `pausa_improductiva` solo con MD; campos críticos `numOp, recurso, actividad, username, topic`; **calcula `cantidadreal`, tiempos y duración** (§6); consulta Optimus `wo_number/tk_id` con `dtbOptimus` | `dtbOptimus` **no captura excepciones** (`db/conexion.py:53-71`): si Optimus cae, la excepción sube **fuera** del `try` (la simulación se llama en 630) → HTTP 500 sin escrituras | C |
| 1 | Flags: sin `ENABLE_REAL_DB_WRITES` → `PROTEGIDO_BD`; FINAL/MD sin `ENABLE_REAL_MQTT_PUBLISH` → `PROTEGIDO_MQTT` | Sin escrituras | C |
| 2 | Comprobar que existe: `SELECT … FROM marcajeactivo WHERE numOp, recurso, actividad, username AND topic` (670-688) | No existe → 409 `NO_ENCONTRADO`. **Un error de BD (`None`) también se trata como "no existe"** | C |
| 3 | **FINAL/MD**: publicar el paro `[numOp,recurso,actividad,cantidadcot,0,fIni,hIni,fFin,hFin,0,0]` en `{mac}-OP` (706-724) | `ok:false` → 409 sin escrituras. **Pero `publicar` devuelve `ok:true` aunque el broker esté desconectado**, porque no revisa `rc` (`mqtt_service.py:270-287`) | C |
| 4 | `INSERT resumenmarcajes` (fila del usuario) (727) | **No se revisa el resultado**; continúa | C |
| 5 | Solo FINAL: `SELECT SUM(cantidadreal), MIN(tiempoinicio), MAX(tiempofinal), SUM(duracion) FROM resumenmarcajes WHERE actividad AND numOp` + `INSERT` de la fila `username='SMARTFACTORY', estado='F'` (733-769) | Si el SELECT falla, usa los valores propios; el resultado del INSERT no se revisa | C |
| 6 | `DELETE FROM datossensados WHERE numOp AND actividad AND mac` (772) | No se revisa | C |
| 7 | `DELETE FROM marcajeactivo WHERE numOp AND actividad AND username` (776). **No filtra por recurso ni topic** | No se revisa | C |
| 8 | MT: arma `relevo_pendiente` | — | C |
| 9 | API: `cerrar_marcaje_estado_por_id` en memoria + broadcast | — | C |

**Valores del INSERT del usuario** (`cierres_service.py:512-527`) [C]:

- `estado`: `NULL` en FINAL, `'MD'` o `'MT'` en los demás.
- `cantidadcot`: `marcaje.cantidad` (o 0).
- `cantidadreal`: la calculada.
- `tiempoinicio`/`tiempofinal`: MIN/MAX de `datossensados.fechatiempo`, o **la hora actual** si no hay filas.
- `duracion`: en minutos.
- `totalUsuario`: valor manual.
- `wo_number`, `tk_id`.
- `variable01=1` solo si `pausa_improductiva`.

`totalUsuario` **solo se guarda; no interviene en ningún cálculo** [C].

### 5.2 F4 — FINAL

- Detiene el ESP (paro MQTT) e inserta la fila del usuario con `estado NULL` y luego la fila agregada `SMARTFACTORY/F`.
- **Agregado** [C]: suma **todas** las filas de `resumenmarcajes` con el mismo `numOp` y `actividad`, sin filtrar por recurso, fecha ni `estado`. **Incluye filas `F` de cierres FINAL anteriores** de esa misma OP y actividad.
- **Después de un FINAL de una actividad con "ARR" en el código** (`app.js:273-385`, 788-796): se ofrece abrir "tiraje" de la misma OP y recurso. Se reconstruye la OP y el operario elige la actividad. No se crea ningún marcaje sin confirmación [C].
- [?] Qué proceso consume las filas `F`. Es probable que la exportación a Optimus use `enviado` [I]. Determina el impacto real de un `F` duplicado o inflado.

### 5.3 F5 — MD (reporte parcial con la máquina detenida)

- Publica el paro, inserta `estado='MD'` y borra `datossensados` y `marcajeactivo`. La máquina queda libre [C].
- Un MD **no** se resta en cierres posteriores (solo se restan los MT) [C]. Esto tiene sentido solo si el contador del ESP se reinicia con el siguiente inicio [I/?].

#### F5b — Pausa por actividad improductiva (v20.22)

`app.js:387-502`:

1. Exige `total_usuario`.
2. Fuerza MD con `pausa_improductiva=true` → INSERT con `variable01=1`.
3. Si el cierre va bien, el operario elige el motivo → `POST /api/marcajes/iniciar-improductivo` (OP 12345, mismo usuario y recurso).
4. Si falla la apertura del improductivo, el MD **no se revierte** [C].

#### F5c — Retorno después del improductivo (v20.23)

`app.js:504-659`, `cierres_service.py:29-73`:

1. Antes de cerrar el 12345: `SELECT * FROM resumenmarcajes WHERE recurso AND username ORDER BY tiempofinal DESC LIMIT 1`. Se mapean las columnas con `SHOW COLUMNS`.
2. Si esa fila tiene `variable01=1` y el cierre del improductivo va bien → se ofrece reabrir la OP y actividad anteriores con el flujo normal (`/api/op/buscar` → actividades cotizadas o no cotizadas → `/iniciar-real-bd`).
3. Detalle [C]: `tiempofinal` viene del reloj del ESP (MAX de `datossensados`) o de la hora del servidor cuando no hay datos. Si los relojes difieren, "la última fila" podría no ser la que se espera [I].

### 5.4 F6 — MT (cambio de turno sin parar la máquina) y relevo

- **No se publica MQTT**: el ESP sigue contando [C].
- Inserta `estado='MT'`, **borra `datossensados` de numOp+actividad+mac** y borra `marcajeactivo` [C].
- El backend devuelve `relevo_pendiente` (780-796) y el navegador lo guarda **solo en una variable JS** (`app.js:752-755`) [C].
- El siguiente operario se identifica en **la misma pestaña** → `iniciarRelevoMtAutomatico` sin confirmación (`app.js:184-197`, 872-922) → `POST /iniciar-relevo-mt-real` → `persistencia_marcajes_service::iniciar_relevo_mt_real_bd` (552-626).
  - Reutiliza `iniciar_marcaje_real_bd`: mismas validaciones, INSERT y **se vuelve a publicar el inicio MQTT al ESP** [C].
- **Cómo se pierde el relevo** [C]:
  - Recargar la página o pulsar *Cancelar*.
  - Que el operario entrante se identifique en otra PC.
  - Pulsar *Cancelar relevo*.
  - En todos los casos el ESP sigue contando **sin marcaje**: las filas DATOS se siguen insertando en `datossensados` con la misma numOp y actividad, y las heredará el próximo marcaje de esa OP y actividad en esa máquina [C mecanismo / I consecuencia].
- Durante el hueco entre MT y relevo la máquina aparece **libre**: otro operario podría abrir otra OP en ella [C].

---

## 6. Cálculo de cantidades: `cantidadreal` (análisis detallado)

### 6.1 Fórmula vigente [C]

En `cierres_service::simular_cierre_marcaje` (453-462) y `_obtener_datos_cierre_datossensados` (138-187):

```
cantreal_original = cantpliegos de la última fila de datossensados
                    WHERE numOp=? AND actividad=? AND mac=?  ORDER BY fechatiempo DESC LIMIT 1
                    (0 si no hay filas)
suma_mt_anterior  = SUM(cantidadreal) FROM resumenmarcajes
                    WHERE numOp=? AND actividad=? AND estado='MT'     ← sin recurso, mac, usuario ni fecha
cantidadreal      = cantreal_original − suma_mt_anterior               ← sin límite inferior
tiempoinicio/final= MIN/MAX(fechatiempo) del mismo filtro (o hora actual)
duracion          = TIMESTAMPDIFF(MINUTE, MIN, MAX)
```

**Supuesto implícito** [I]: `cantpliegos` es un **contador acumulado por la sesión del ESP**, que no se reinicia en un MT (el ESP no se detiene) y sí se reinicia en un nuevo inicio después de FINAL o MD.

- Lo apoya `_calcular_unidades_conglomerado` (`mqtt_persistencia_simulada_service.py:157-187`), que trata "actual < anterior" como un RESET del contador [C]. Hay 1.382 alertas de tipo RESET en el log [C].
- El comportamiento del contador ante un **segundo inicio con la misma OP y actividad** (el relevo MT lo envía) es **[?]**: es la pregunta clave para el firmware.

### 6.2 Qué cálculos NO intervienen [C]

- `unidadesCalculadasConglomerado` (en `mensajes_mqtt`): solo se guarda y genera alertas.
- `delta_ultimo_mensaje`/`conteo_mqtt_actual` en memoria: solo se muestran.
- `totalUsuario`: solo se guarda.

### 6.3 Escenarios que producen valores negativos, duplicados o inconsistentes

| # | Escenario | Resultado | Nivel | Evidencia |
|---|---|---|---|---|
| N1 | Hay filas MT antiguas o de otro recurso/usuario con el mismo numOp+actividad | Se restan cantidades ajenas → **negativo o infravalorado** | **C** | Único evento del log (2026-10-12): FINAL de `12345/COMIDA` en `PEG CAJ2` restó el MT de `12345/COMIDA` del **2026-08-21**, recurso `PEG CAJ3`, usuario distinto → `0 − 1 = −1` |
| N2 | Improductivos (12345): todos comparten numOp y la actividad es un motivo genérico (COMIDA…), así que cualquier MT de improductivo contamina **todos** los improductivos futuros de ese motivo en toda la planta | Negativos recurrentes en improductivos | C | Igual que N1 |
| N3 | Secuencia MT → MD → reapertura de la misma OP y actividad: el MD no "consume" la suma MT; si el contador se reinicia en el nuevo inicio, el siguiente cierre resta los MT anteriores sobre un contador nuevo | Negativo o infravalorado | C (fórmula) / ? (contador) | — |
| N4 | MT → relevo: el relevo **vuelve a publicar el inicio**. Si el firmware reinicia el contador con ese mensaje, el cierre de B = (contador nuevo − MT de A) | Negativo o infravalorado | ? (firmware) | Sin negativos productivos desde la v20.19 (2026-09-07). Sugiere que no hay reinicio o que el caso es raro [I] |
| N5 | No hay filas DATOS: inicio no publicado (`ok:true` con publicación fallida), ESP apagado, MQTT caído o actividad del payload distinta de la del marcaje | `cantreal_original=0`, tiempos = ahora, duración 0. Con MT previos → negativo | C | — |
| N6 | El ESP envía `actividad`/`numOp` distintos de los del marcaje (solo se avisa en memoria, `marcajes_estado_service.py:173-181`) | Cantidad 0, y filas huérfanas que el DELETE (que filtra por la actividad del marcaje) no borra | C (mecanismo) | — |
| N7 | Filas huérfanas en `datossensados` (DELETE fallido, DATOS que llegan después del paro, hueco sin marcaje tras un MT) | `tiempoinicio` antiguo → **duración inflada**. La cantidad usa la última fila, así que solo se contamina si lo último es huérfano | C (mecanismo) / I (frecuencia) | — |
| N8 | **Agregado FINAL repetido**: segundo FINAL de la misma numOp+actividad (reapertura, otro recurso con la misma actividad o cualquier improductivo cerrado como FINAL) | La nueva fila `F` suma las filas `F` anteriores → **doble conteo y crecimiento acumulativo**. Para 12345/COMIDA cada FINAL suma todo el histórico de la planta, incluidos los `F` previos → `duracion` se dispara | C (código) / ? (magnitud real) | Selector por defecto = FINAL (`index.html:122`) |
| N9 | Filas duplicadas en `datossensados` (sin UNIQUE + varios backends) | **No altera** la cantidad (última fila) ni MIN/MAX. Duplica volumen y diagnósticos | C | 774 × 2 |
| N10 | Doble cierre concurrente del mismo marcaje (dos PCs o reintento) | Ambos pasan el paso 2 → 2 filas de resumen. El segundo puede calcular 0 si el primero ya borró `datossensados` | C (sin guarda) / I (probabilidad) | — |
| N11 | Reintento después de un cierre parcial (§7) | Segunda fila de resumen con `cantidadreal = 0 − MT` y tiempos = ahora | C | — |
| N12 | Contador del ESP reiniciado en mitad de una sesión (corte de energía o reinicio del ESP) | La última lectura es baja → cantidad infravalorada; con MT previos → negativo | ? (firmware) / C (no se detecta) | 1.382 alertas RESET (contexto general, no necesariamente en mitad de sesión) |

### 6.4 Tiempos [C]

- Salen del reloj del ESP (`fecha`, `tiempo` del payload), no del servidor ni de la hora de apertura.
- Sin datos, se usa la hora del servidor en ambos extremos.
- La `fecha_inicio` de la tarjeta en pantalla es la hora de sincronización, no la de inicio real (`persistencia_marcajes_service.py:53`).

---

## 7. Errores de BD, carreras y operaciones parciales en los cierres

### 7.1 Semántica de `dtbSmartFactory.consultaSmartFactory` (`db/conexion.py:9-50`) [C]

- Abre **una conexión nueva por consulta**, con commit inmediato. No hay transacciones que abarquen varias sentencias.
- SELECT → lista (vacía si no hay filas). INSERT/UPDATE/DELETE (detectado con `startswith`) → `"Operación exitosa"`, **aunque afecte 0 filas**.
- Cualquier `mysql.connector.Error` → `print` y **`None`; nunca lanza excepción**.
- `dtbOptimus` (sin el 1) **sí lanza excepción**. `dtbOptimus1` devuelve `None`.

### 7.2 Matriz de cierre parcial (FINAL/MD; MT igual pero sin el paso 3)

| Falla | Estado resultante | Respuesta al usuario | Recuperación |
|---|---|---|---|
| Paro MQTT "OK" con el broker caído | Se escribe en BD; **el ESP sigue contando** sin marcaje | ok | Manual |
| INSERT del resumen (4) | **Producción perdida**: sin fila de resumen, `datossensados` borrado, marcaje borrado | **ok:true** | Solo desde `mensajes_mqtt` (histórico), a mano |
| INSERT `F` (5) | Fila de usuario sin agregado `F` | ok | Manual |
| DELETE `datossensados` (6) | Filas huérfanas → N7 en la próxima sesión | ok | Manual |
| DELETE `marcajeactivo` (7) | El marcaje sigue en BD, pero se quita de memoria. Reaparece al sincronizar y se puede volver a cerrar → N11 (resumen duplicado con 0 o negativo) | ok | El reintento empeora |
| Excepción de Python entre pasos | `except` devuelve `ERROR_CIERRE_REAL` con `queries_ejecutados_antes_error` | 409 | Ese detalle **no se escribe en ningún log** [C] |

Además [C]: `ejecutar_cierre_marcaje_real` **no escribe en `marcajes_reales.log`** (solo lo hacen la apertura y el endpoint heredado `cerrar-real-bd`). No queda auditoría local de los cierres reales, salvo cuando la cantidad es negativa.

### 7.3 Errores de BD en las validaciones [C]

| Consulta | Ante error | Efecto |
|---|---|---|
| `consultar_marcaje_activo`, `consultar_marcaje_activo_por_recurso_o_topic`, `validar_apertura_marcaje_real` | `None` → "sin marcaje" | **Permite pasar** |
| `obtener_mac_por_recurso` | `None` | **Bloquea** ("sin MAC") |
| Paso 2 del cierre | Cuenta como "no existe" | Bloquea el cierre (seguro) |

Con la BD totalmente caída el INSERT también falla, así que el riesgo real es un **fallo intermitente** (falla la validación y luego funciona el INSERT) → marcajes duplicados por usuario o máquina [I].

### 7.4 Condiciones de carrera

| Carrera | Mecanismo | Nivel |
|---|---|---|
| Dos aperturas en la misma máquina, o del mismo usuario, casi a la vez (dos PCs o doble envío) | El SELECT de validación y el INSERT son conexiones separadas, sin lock ni UNIQUE conocido | C (código) / ? (si hay UNIQUE en `marcajeactivo`) |
| Dos cierres del mismo marcaje | Ver N10 | C |
| Cierre MT mientras siguen llegando DATOS | Intencionado: las filas posteriores al DELETE son del relevo | C |
| Cierre FINAL/MD con DATOS en tránsito | Pueden insertarse después del DELETE → huérfanos (N7) | I |
| Lista en memoria modificada desde el hilo de paho (`asociar_mensaje_mqtt_a_marcaje`) y desde el event loop (endpoints) | Sin lock. El GIL evita corrupción grave, pero es posible leer valores intermedios o saltar elementos al iterar | I |
| `reemplazar_estado_marcajes` (`clear` + `extend`) mientras llega un MQTT | Se pierden los contadores en vivo; solo afecta a lo que se muestra | C |

---

## 8. Flujo F8 — Recepción y procesamiento MQTT

### Arranque (`main.py:36-53`, `mqtt_service.py:102-141`)

- Se conecta al broker al iniciar FastAPI.
- La lista de suscripciones se calcula **una sola vez**: `conexion`, `MAC` y, por cada MAC de `macdirectorio`, `-CONFIG`, `-OP`, `-DATOS`, `-BANDERAS`, `-ALERT`.
- Una MAC nueva en `macdirectorio` exige *Detener* + *Conectar* (solo ADMIN) o reiniciar el backend [C].
- Si el broker no está disponible al arrancar, **no hay reintento automático** (`connect` lanza la excepción, `ejecutando=False`) [C]. A partir de ahí:
  - Las aperturas insertan el marcaje sin publicar.
  - Los cierres FINAL/MD quedan bloqueados.
- Si se cae después de conectar, paho reconecta solo (`loop_start`) [I por el comportamiento de paho] y `_on_connect` vuelve a suscribir [C].

### Por cada mensaje (`_on_message`, 200-254, en el hilo de paho) [C]

1. MAC y tipo = `topic.split("-", 1)` si `len(topic) ≥ 17`.
2. `registrar_mensaje_mqtt`: buffer en memoria de 80 mensajes.
3. `procesar_persistencia_mqtt` (`mqtt_persistencia_simulada_service.py:240-422`). **El nombre dice "simulada", pero escribe en producción.**
   - Solo procesa `-DATOS`. Exige ≥ 8 campos: `numOp, cantpliegos, actividad, actividadreal, velocidadreal, fecha, tiempo, unidadesSensadasPeriodo`.
   - `numOp == "N/A"` → `"100"`.
   - `idmensaje = "{mac} {fecha} {tiempo}"`, con resolución de segundos.
   - `anterior` = último `cantpliegos` de `mensajes_mqtt` para esa MAC. Conglomerado: `actual − anterior`, o `actual` si no hay anterior o hay RESET.
   - `INSERT IGNORE mensajes_mqtt`.
   - `INSERT IGNORE datossensados`, **excepto si numOp=100** (v20.18).
   - **Inserta aunque no haya marcaje activo** para esa MAC; no se valida contra `marcajeactivo`.
   - 3 conexiones a la BD **síncronas** por mensaje dentro del hilo de red → si la BD va lenta, se forma cola y puede afectar al keepalive [I].
4. `asociar_mensaje_mqtt_a_marcaje`: actualiza los contadores en memoria del **primer** marcaje con esa MAC y avisa si la OP o la actividad del payload no coinciden. Solo afecta a lo que se muestra.
5. Broadcast por `/ws/mqtt` (y por `/ws/marcajes` si se asoció).

- Los topics `-OP` (incluidos los mensajes de inicio y paro que publica el propio backend), `-ALERT`, `-BANDERAS` y `-CONFIG` **solo se muestran; no se persisten ni se procesan** [C].
- Alertas `unidadesCalculadasConglomerado > 48` → `mqtt_conglomerado_alertas.log`: 5.167 en 4 meses (3.784 DIFERENCIA, 1.382 RESET, 1 SIN_ANTERIOR) [C]. [?] Si 48 es un umbral físico real.

### Publicación (`mqtt_service.py::publicar`, 257-294) [C]

- QoS 0, sin `retain`.
- Solo comprueba `self.client` y `self.ejecutando`, **no `conectado` ni el `rc` del publish**.
- El broker no confirma la entrega a QoS 0 → no hay garantía de que el ESP reciba el inicio o el paro.

---

## 9. Flujo F9 — Sincronización frontend ↔ backend ↔ BD

| Evento | Qué ocurre | Nivel |
|---|---|---|
| Cargar o recargar cualquier pestaña | `POST /api/marcajes/sincronizar-desde-bd` → `reemplazar_estado_marcajes(listar_marcajes_activos_bd())` → **reemplaza toda la memoria del proceso** y la envía a todas las pestañas de ese backend (`app.js:1511-1530`, `api/marcajes_api.py:192-207`) | C |
| …si esa lectura falla | `listar_marcajes_activos_bd` devuelve `[]` → **memoria vacía**; todas las pantallas muestran "Sin marcajes activos". Los bloqueos siguen funcionando por BD | C |
| Apertura o cierre en esta PC | Actualiza la memoria y envía el broadcast | C |
| Apertura o cierre desde **otra** PC o backend | Esta memoria no se entera hasta la próxima sincronización → tarjetas obsoletas y bloqueos `RECURSO_O_TOPIC_MEMORIA` falsos | C (mecanismo) / I (multi-backend) |
| Reconexión del WebSocket | El cliente reintenta cada 3 s; al conectar recibe la lista de memoria (no sincroniza con BD) | C |
| Botón *Sincronizar BD* | Sincronización manual (`index.html:55`) | C |

**Posible error lógico** [C]: `consultar_marcaje_activo` prioriza la memoria sobre la BD. Un marcaje obsoleto en memoria hace que un usuario "tenga" un marcaje que ya no existe y le impide abrir uno nuevo hasta que alguien sincronice.

---

## 10. Endpoints con efectos sobre la BD que la UI actual no usa [C]

| Endpoint | Efecto | Riesgo |
|---|---|---|
| `POST /api/marcajes/cerrar-real-bd` | `DELETE marcajeactivo` **sin** INSERT de resumen ni borrado de `datossensados` | Pérdida de la producción de ese marcaje y huérfanos en `datossensados` |
| `POST /api/marcajes/iniciar-improductivo-bd` | Apertura **productiva** | Nombre engañoso |
| `POST /api/mqtt/detener` | Detiene la persistencia y publicación MQTT de ese backend | Bloquea cierres FINAL/MD y deja de guardar DATOS |
| `activar-simulacion`, `cerrar-simulacion` | Solo memoria | Pueden insertar marcajes falsos en memoria que bloqueen máquinas en ese proceso |

Ninguno exige autenticación (los roles solo existen en el frontend, `app.js:1919`).

---

## 11. Discrepancias entre comentarios o documentación y el código

| # | Documentación o comentario | Código real | Nivel |
|---|---|---|---|
| D1 | README_V14 indica añadir `UNIQUE KEY uq_idmensaje` para que `INSERT IGNORE` evite duplicados | El esquema (2026-10-12) **no tiene** ese UNIQUE; hay duplicados ×2 | C |
| D2 | Docstring de `MqttMonitorService`: "NO publica mensajes MQTT, NO modifica marcajes reales" | Publica el inicio y el paro (`publicar`) | C |
| D3 | `publicar`: "Requiere que el servicio MQTT esté iniciado/conectado" | Solo comprueba "iniciado"; no revisa `rc` | C |
| D4 | `procesar_persistencia_mqtt`: "Por defecto solo simula" | El valor por defecto es `"1"` (`config.py:51`) → escribe | C |
| D5 | `marcajes_estado_service`: "Esta fase es de simulación" | Contiene los marcajes reales | C |
| D6 | `obtener_recursos_de_orden`: "Replica la lógica actual de PyQt" | PyQt filtra por `wo_number`; la web no | C |
| D7 | Mensaje de cierre: "Presione Conectar MQTT" | El botón solo es visible para ADMIN | C |
| D8 | README_V20: "el backend principal puede correr en el servidor central" | CORS de huella y `.bat` en 127.0.0.1 → un backend por PC; la evidencia indica ≥ 2 backends | C (configuración) / I (despliegue) |
| D9 | Tarjeta: "Solo el dueño del marcaje podrá cerrarlo con huella" | Cierto en la UI; la API no lo exige | C |
| D10 | `construir_mensaje_mqtt_inicio`: fechas fijas "por ahora" | Siguen en producción | C |
| D11 | `seleccionar_produccion_unidad`: "debe revisarse contra PyQt" | Constante `"UNIDAD"` | C |
| D12 | README_V20_23: "no se modifica la lógica de FINAL, MD, MT" | Cierto; pero el improductivo sigue heredando N1/N2/N8 | C |
| D13 | Diagnóstico de negativos: "no filtra recurso ni MAC" (`cierres_service.py:374`) | Correcto; es la causa confirmada en N1 | C |

---

## 12. Estado de las hipótesis críticas de la Fase 1

| Hipótesis de la Fase 1 | Estado tras la Fase 2 |
|---|---|
| Entorno de producción | **Reforzada** (logs del 2026-10-12, OPs reales) |
| Cierre no atómico con pérdida silenciosa | **Confirmada en código** (§7.2). [?] Frecuencia real: no hay log de cierres para medirla |
| Validaciones que pasan ante error de BD | **Confirmada en código**; el impacto real requiere un fallo intermitente (§7.3) |
| Carreras en la apertura | Confirmada en código; **[?] depende de que exista UNIQUE en `marcajeactivo`** |
| `publicar` da éxito falso | **Confirmada en código** (QoS 0, sin `rc`) |
| La sincronización al recargar vacía la memoria | **Confirmada**, solo en caso de error de lectura; solo afecta a lo que se muestra y a los bloqueos en memoria |
| `cantidadreal` contaminada por MT ajenos | **Confirmada con evidencia** (N1) |
| Recursos sin filtrar por OT | **Confirmada** y confirmada como regresión respecto a PyQt |
| Nuevo: duplicación ×2 en `datossensados` / varios backends | Duplicación **confirmada**; causa multi-backend **inferida** |
| Nuevo: agregado FINAL acumulativo (N8) | **Confirmado en código**; magnitud [?] |

---

## 13. Preguntas que necesitan confirmación humana (prioridad)

1. **Firmware ESP**:
   - ¿El contador `cantpliegos` se reinicia al recibir un mensaje de inicio en `{mac}-OP`? ¿También si es la misma OP y actividad (relevo MT)?
   - ¿Qué significan los campos `100` y `0,1` / `0,0` del payload?
   - ¿Se usan las fechas del payload?
2. **Despliegue**: ¿cuántas PCs ejecutan `iniciar_backend_piloto.bat` a la vez? ¿Sigue alguna en PyQt?
3. **Esquema**: ¿`marcajeactivo` y `mensajes_mqtt` tienen claves UNIQUE? ¿Se puede obtener el DDL (`SHOW CREATE TABLE`) en modo lectura?
4. **Consumidores de `resumenmarcajes`**: ¿qué proceso lee las filas `F` y la columna `enviado`? ¿Se exportan a Optimus?
5. **Regla de MT**: ¿la resta de MT debe acotarse a la misma sesión, recurso y MAC? ¿Qué es lo correcto para los improductivos?
6. **¿Un improductivo debe cerrarse siempre como FINAL**, o solo permitir ciertos tipos? ¿Debe generar fila `F`?
7. **¿Es intencional** que el improductivo ocupe la máquina y active el ESP?
8. **¿Es intencional** que cualquier recurso (no solo los de la OP) se pueda seleccionar? (Regresión respecto a PyQt.)
9. **El cambio sin commit** `OR recursoalternativo`: ¿está desplegado en producción? ¿Qué semántica tiene "recurso alternativo"?
10. **Umbral 48** del conglomerado: ¿es un límite físico (pliegos por período)?
11. **¿Existe un procedimiento manual** para corregir cierres incompletos o negativos? ¿Hay registro de incidencias?
12. **¿El repo de GitHub es privado?** Lo pregunto por las credenciales versionadas en `db/conexion.py` y los valores por defecto de MQTT en `services/mqtt_service.py:64-65` (ubicaciones, no valores).
