# 04 — Flujos de marcaje (actual, esperado, problemas, pendientes)

Conceptos:
- **Marcaje**: usuario + OP + recurso + actividad + topic (`{mac}-OP`).
- **Productivo**: OP real de Optimus.
- **Improductivo**: OP centinela **`12345`** (README_V20_23; único criterio [C], `app.js:589`).
- La cantidad (`cantidadreal`) se explica en `05-cantidadreal.md`. La identificación en `07-identificacion-biometria.md`.

---

## 0. Orden de efectos por ruta (fuente de verdad)

> **Corrección de la Fase 1**: el resumen de la Fase 1 decía que la apertura publicaba MQTT antes del INSERT. **Es falso.** El orden real es el de esta tabla [C].

| Ruta (función) | Usada por | 1 | 2 | 3 | 4 | Si falla MQTT |
|---|---|---|---|---|---|---|
| Apertura productiva `persistencia_marcajes_service::iniciar_marcaje_real_bd` (211-388) | `iniciar-real-bd`, `iniciar-improductivo-bd`, relevo MT, retorno tras improductivo | (2026-11-24) **Resolución de OT** en Optimus, solo lectura (233-254; el relevo la hereda sin consultar Optimus). Un rechazo termina aquí, sin consultas a SmartFactory. Después, validaciones V1-V7 | **INSERT `marcajeactivo`** (305) | **Publicar inicio** `{mac}-OP` (330-352) | Log `APERTURA_REAL_OK` | El marcaje **queda abierto**; respuesta `ok:true` con un mensaje de aviso |
| Apertura improductiva `::iniciar_marcaje_improductivo_bd` (392-538) | `iniciar-improductivo` | `SIN_TAREA` sin consultar Optimus (411); V1-V7 | INSERT (461) | Publicar inicio (486-508) | Log | Igual |
| Cierre FINAL / MD `cierres_service::ejecutar_cierre_marcaje_real` (724-968) | `ejecutar-cierre-real` | Cálculo y validaciones, incluida (2026-11-24) la lectura de la OT fijada en `marcajeactivo` (`_obtener_ot_fijada`; si falla → 409 `ERROR_BD_OT` sin efectos); SELECT de existencia (787-805) | **Publicar paro** (823-841) | INSERT resumen (846); **si falla → aborta (409) sin DELETE** (v20.24) [+ agregado `F` y suma de pliegos incorrectos (869-915) si FINAL] | DELETE `datossensados` (918) → DELETE `marcajeactivo` (922) | Si `publicar` devuelve `ok:false` → **aborta sin tocar la BD**. ⚠️ Puede devolver `ok:true` con el broker caído (R-04) |
| Cierre MT (misma función) | `ejecutar-cierre-real` | Igual | — (no publica) | INSERT resumen `MT` (si falla → aborta sin DELETE, v20.24) | DELETEs | No aplica |
| Cierre heredado `persistencia_marcajes_service::cerrar_marcaje_real_bd` (541-623) | `cerrar-real-bd` (sin botón) | SELECT | DELETE `marcajeactivo` | — | — | Sin MQTT, sin resumen, sin borrar `datossensados` |

### Comportamiento según los flags [C]

| Flags | Apertura | Cierre |
|---|---|---|
| `ENABLE_REAL_DB_WRITES=0` | `PROTEGIDO`: sin INSERT **ni** publicación | `PROTEGIDO_BD`: nada |
| `ENABLE_REAL_DB_WRITES=1`, `ENABLE_REAL_MQTT_PUBLISH=0` | INSERT sin publicar | MT se ejecuta; FINAL/MD → `PROTEGIDO_MQTT`, nada |

---

## 1. Identificación (resumen; detalle en `07-identificacion-biometria.md`)

1. La UI pide la huella al servicio `:9001`.
2. Llama a `POST /api/usuario/identificar-prueba`.
3. Decide el siguiente paso (`app.js::identificarUsuario` 131-237):
   - **Marcaje activo** → panel de cierre (no puede abrir otro).
   - **`relevoMtPendiente` en esta pestaña** → relevo automático (§6).
   - **Ninguno de los dos** → ingreso de OP.

El marcaje activo se busca **primero en memoria y después en BD** (`usuarios_service::consultar_marcaje_activo` 55-85) [C].

---

## 2. Apertura de marcaje productivo

### Actual [C]

**UI** (`app.js`):
1. `buscarOp` (1235-1277).
2. Selección de recurso (`cargarActividadesPorRecurso` 1309-1327).
3. Opcionalmente, `abrirSelectorActividadNoCotizada` (1349-1445). Solo añade la actividad a la lista local.
4. `seleccionarActividad` (1447-1550): (2026-11-24, iteración 5 de `14-resolucion-ot.md`) `elegirOtParaInicio` consulta `POST /api/op/ots`; si `requiereEleccion`, el operario elige la parte de la orden en un Swal de radio («Continuar» / «Volver»; «Volver» cancela sin efectos). Confirmación Swal (con «Parte:» si hubo elección) → `POST /api/marcajes/iniciar-real-bd` con `num_op, descripcion, cantidad, recurso, actividad, actividad_nombre, codigo_usuario` y `numero_ot` **solo** si hubo elección. Ante 409 `SELECCION_OT_REQUERIDA`/`OT_NO_CANDIDATA`: nueva elección con el aviso «Las partes de la orden cambiaron; vuelva a elegir» y **un** reintento. El diálogo de éxito muestra «Parte» con `AUTOMATICA`/`ELEGIDA`.

**Búsqueda de la OP** (`ordenes_service::buscar_orden_produccion`; desde el 2026-11-24, `14-resolucion-ot.md` iteración 2):
- La OP debe ser solo dígitos, existir en `job200` y ser elegible (`resolucion_ot_service::leer_op`); sin rango (P-20).
- Devuelve `orden = {num_op, descripcion, cantidad}`; `num_op` es `job200.j_number`. Ya no existe `orden.num_ot` (v20.25).
- `j_quantity` pasa a ser la cantidad cotizada.
- Recursos: `obtener_recursos_de_orden` (14-57), **sin filtro por OP ni OT** (R-10, fuera de alcance de v20.25).
- Actividades (v20.25): vigentes (`act_discont = '0'`) del centro de costo con tarea en **cualquier** OT de la OP (cotizadas) o sin tarea en ninguna (no cotizadas), por `num_op`.
- Recurso sugerido: el primero cuyo código sea **subcadena** de `staf_resource` (110-114).

**Resolución de OT (2026-11-24, `14-resolucion-ot.md` iteración 4)** [C]: antes de V1, `iniciar_marcaje_real_bd` llama a `resolucion_ot_service::resolver_desde_optimus(num_op, actividad, numero_ot)` (solo lectura en `job200`, `wo` y `wo_task200`).
- Rechazo (`OP_*`, `SELECCION_OT_REQUERIDA`, `OT_NO_CANDIDATA`, `RESPUESTA_INVALIDA`) → 409 `modo=RESOLUCION_OT` con `codigo`, `mensaje` y, si las hay, `ots_candidatas`. `OPTIMUS_NO_DISPONIBLE` → **503**. Log `APERTURA_BLOQUEADA` con el código. No consulta `macdirectorio` ni `marcajeactivo`, no escribe ni publica.
- Correcto → `wo_number`, `tk_id`, `estadoResolucion` (`AUTOMATICA`/`ELEGIDA`/`SIN_TAREA`) y `tituloOt` se añaden al payload y van al INSERT. Con `SIN_TAREA`, OT y tarea `NULL`. La respuesta incluye `resolucion`.
- Sin actividad (en blanco) → `VALIDACION_BLOQUEADA` antes de consultar Optimus.

**Validaciones de la apertura**, en orden:

| ID | Regla | Función (línea) | Fuente | Ante error de BD |
|---|---|---|---|---|
| V1 | El usuario no tiene marcaje activo | `marcajes_service::preparar_inicio_marcaje` → `consultar_marcaje_activo` (224) | Memoria, luego BD | Pasa (R-03) |
| V2 | El recurso tiene MAC: `macdirectorio WHERE recurso=R OR recursoalternativo=R LIMIT 1` | `obtener_mac_por_recurso` (22-41) | BD | Bloquea ("sin MAC") |
| V3 | Máquina libre: `marcajeactivo WHERE recurso=R OR topic=T` | `consultar_marcaje_activo_por_recurso_o_topic` (46-85) | BD | Pasa |
| V4 | Máquina libre en memoria (mismo recurso o topic) | `consultar_marcaje_temporal_por_recurso_o_topic` (88-119) | Memoria | — |
| V5 | Campos críticos no vacíos | `persistencia_marcajes_service::validar_apertura_marcaje_real` (125-140) | — | — |
| V6 | El usuario no está en `marcajeactivo` (repite V1, solo BD) | idem (142-163) | BD | Pasa |
| V7 | Topic o recurso libre (repite V3) | idem (165-187) | BD | Pasa |

> V2 incluye `OR recursoalternativo` (`services/marcajes_service.py:32`; sin commit hasta 2026-11-15, versionado en un commit propio). Sin él, solo se busca por `recurso`.
> - Alcance [C]: todas las aperturas (productiva, improductiva, pausa, retorno tras improductivo y los endpoints `preparar`/`simular`) pasan por `obtener_mac_por_recurso`; el relevo MT reutiliza el topic del marcaje cerrado y no consulta `macdirectorio`. `obtener_recursos_existentes_improductivo` y la carga de MAC de `mqtt_service` no cambian.
> - [C] Si la columna no existe, la consulta devuelve `None` (error de MySQL) y **toda apertura** se bloquea con "No existe sensor/MAC". Su existencia es [?] (P-09).
> - [C] `LIMIT 1` sin `ORDER BY`: si un valor coincide con el `recurso` de una fila y el `recursoalternativo` de otra, la MAC elegida no es determinista.
> - **No lo modifiques ni lo reviertas sin autorización** (P-09).

**Efectos**:
- INSERT en `marcajeactivo (numOp, descrip, cantidad, recurso, actividad, username, topic, produccionUnidad='UNIDAD', wo_number, tk_id, estadoResolucion, tituloOt)` (las 4 últimas desde el 2026-11-24; `NULL` si la ruta no las trae). No se guarda la hora de inicio.
- Publicación del inicio (formato en `06-mqtt-sensores.md` §3).
- Memoria: `agregar_o_actualizar_marcaje_estado`, con `fecha_inicio` = hora del servidor.
- WS `MARCAGES_ACTIVOS_ACTUALIZADOS`.

**Efecto sobre otros**:
- La máquina queda bloqueada para cualquier operario mientras exista la fila.
- El ESP empieza a enviar DATOS [I/? según el firmware].

### Esperado (reglas conocidas)

- Un operario solo puede tener un marcaje abierto; una máquina solo uno a la vez (docstring de `validar_apertura_marcaje_real`, 110-118) [C, regla declarada en el código].
- Los recursos ofrecidos deberían ser los de la OT, como en PyQt (`../src/widgets/acciones_botones.py:2284-2289`) [I: es la regla original; no consta que se cambiara a propósito].

### Problemas

- R-03: las validaciones pasan ante un error de BD.
- R-06: carrera entre la validación y el INSERT.
- R-04: la publicación devuelve éxito aunque falle.
- R-10: recursos sin filtrar.
- R-16: fechas fijas en el payload.
- R-17: subcadena en el recurso sugerido.

### Pendiente

- P-03: ¿hay UNIQUE en `marcajeactivo`?
- P-08: ¿el recurso sin filtrar es intencional?
- P-09: estado del cambio `recursoalternativo`.

---

## 3. Apertura de marcaje improductivo

### Actual [C]

**Entrada directa**:
1. El operario elige un motivo en `#ImproductivoSelect` (`COMIDA`, `MANTO`, `FALLA`, `CAMBIO`; `templates/index.html:168-172`).
2. `SeleccionarRecurso` (`app.js:1085-1115`) carga **todos** los recursos de `macdirectorio`.
3. **El `onchange` del select de recursos** lanza `marcajeTiempoImproductivo` (`index.html:180`; `app.js:1143-1230`) → confirmación → `POST /api/marcajes/iniciar-improductivo`, con `num_op="12345"`, `cantidad="12345"`, `descripcion="Tiempo Improductivo"`.
   - Para elegir el recurso que ya aparece seleccionado al principio, hay que cambiar antes a otro (no hay botón de confirmación).
   - **Diálogo de éxito con `OP null`** [C por lectura estática; no reproducido en navegador] (E6, Fase 4): el texto es `` `OP ${ordenActual} · …` `` (`app.js:1202`). `ordenActual` solo vale `"12345"` si antes se pulsó *Marcar Tiempo Improductivo* (`SeleccionarRecurso`, `app.js:1107`); tras un éxito se pone a `null` (`app.js:1207`). El contenedor `#selectorRecursoTiempoImproductivo` **nunca se oculta ni se vacía** después del éxito (solo lo toca `prepararRecursosImproductivo`, `app.js:1118-1141`). Si el siguiente operario cambia directamente ese select, la apertura se ejecuta y el diálogo muestra `OP null` (u `OP [object Object]` si había buscado una OP productiva). El backend recibe siempre `num_op="12345"` fijo, así que **los datos guardados no se ven afectados**; es un defecto de presentación (R-31).

**Entrada tras pausa** (§5.2).

**Backend**: `iniciar_marcaje_improductivo_bd` → `simular_inicio_marcaje_improductivo` → `preparar_inicio_marcaje_improductivo`. Aplica **las mismas V1-V7**, INSERT y **publica el inicio MQTT con OP 12345**. (2026-11-24) Se guarda con `estadoResolucion='SIN_TAREA'` y OT y tarea `NULL`, sin consultar Optimus.

**Efectos sobre otros**:
- **La máquina queda ocupada** durante el tiempo improductivo.
- El ESP envía DATOS `12345,…`, que se guardan en `datossensados` (evidencia en el log del 2026-10-12).

**Inconsistencia** [C]: `simular_inicio_marcaje_improductivo` (`marcajes_service.py:422-431`) **no incluye `descrip` ni `cantidad`** en `valores`, así que el marcaje en memoria tiene `cantidad=None`. El INSERT en BD sí guarda 12345. Al cerrar, `cantidadcot` será 0 o 12345 según de dónde salga el objeto (R-18).

En Optimus no existen las actividades COMIDA/MANTO/… → `wo_number=0, tk_id=0` en el resumen [C]. Desde el 2026-11-24 sale de `SIN_TAREA` (P-19) y ya no se consulta `wo_task200`.

### Esperado

- Regla declarada: "un marcaje se considera improductivo únicamente cuando su OP es 12345" (README_V20_23) [C en el código].
- [?] Si debe ocupar la máquina y activar el ESP (P-07).

### Problemas

- R-12: las cantidades de los improductivos se contaminan entre sí.
- R-13: agregado `F` acumulativo.
- R-18: `cantidadcot` incoherente.
- R-19: el `onchange` lanza el inicio.

---

## 4. Cierre FINAL (finalización de la actividad)

### Actual [C]

**UI** `app.js::ejecutarCierreRealMarcajeActivoDelUsuario` (670-682) → `procesarCierreRealMarcajeActivoDelUsuario` (684-854):
0. (v20.24) `cierreEnCurso` impide un segundo envío mientras el primero no termina (doble clic).
1. Toma `tipoCierreMarcaje` (por defecto **FINAL**, `index.html:122`) y `totalUsuarioCierre` (vacío → 0).
   - (v20.24) Toma `pliegosIncorrectosCierre` (empieza en 0 cada vez que se muestra el panel) y lo valida con `validarPliegosIncorrectos` (`static/js/cierre_validacion.js`): entero ≥ 0, sin decimales; vacío → 0. Si no es válido, avisa y no continúa. En OP 12345 el campo está oculto y se envía `null`.
2. Si el marcaje es 12345, consulta antes el contexto de retorno (§5.3).
3. Confirmación. (v20.24) Si no es improductivo, muestra **Pliegos buenos (total reportado)** y **Pliegos incorrectos**.
4. `POST /api/marcajes/ejecutar-cierre-real` con **el objeto marcaje completo que tiene el navegador** y `pliegos_incorrectos`.

**Backend** (orden en §0):
1. `simular_cierre_marcaje` (474-720) valida:
   - el tipo de cierre;
   - que `pausa_improductiva` solo vaya con MD;
   - los campos críticos `numOp, recurso, actividad, username, topic`;
   - (v20.24) `pliegos_incorrectos`: `None` o entero ≥ 0 (también lo valida Pydantic con 422). En OP 12345 se fuerza `NULL`.
2. Calcula la cantidad, los tiempos y `wo_number/tk_id`.
   - (2026-11-24) `wo_number/tk_id` salen de la OT **fijada al abrir** (`_obtener_ot_fijada`): `SELECT wo_number, tk_id, estadoResolucion, tituloOt FROM marcajeactivo` con las mismas condiciones que el SELECT de existencia. `AUTOMATICA`/`ELEGIDA` → los de la fila; `SIN_TAREA` → `0`/`0` (P-19); estado nulo, desconocido o sin fila → respaldo `_obtener_wo_tk` (comportamiento anterior). Error de BD (`None`) → 409 `ERROR_BD_OT` **antes** de publicar o escribir. `valores` añade `estadoResolucion` y `tituloOt`. La fila `F` usa los mismos `wo_number/tk_id`.
   - `_obtener_wo_tk` (solo respaldo) usa `dtbOptimus`, que **lanza excepción**. La simulación se llama fuera del `try` (741) → HTTP 500 **antes** de escribir [C].
3. Comprueba los flags.
4. SELECT de existencia **exacto** (numOp, recurso, actividad, username, topic). Un error de BD también se trata como "no existe" (bloquea, seguro).
5. Publica el paro.
6. INSERT de la fila del usuario con `estado NULL`, `variable01` omitida y (v20.24) `pliegosIncorrectos`.
   - **(v20.24) Si el INSERT no devuelve `"Operación exitosa"`, el cierre se aborta**: respuesta 409 `INSERT_RESUMEN_FALLIDO`, sin agregado ni DELETE. El marcaje y `datossensados` quedan intactos para reintentar. En FINAL/MD el paro MQTT ya se publicó y el mensaje lo indica: el ESP queda parado con el marcaje activo y el reintento vuelve a publicar el paro (R-33, riesgo operativo abierto).
7. **Agregado**:
   ```sql
   SELECT SUM(cantidadreal), MIN(tiempoinicio), MAX(tiempofinal), SUM(duracion)
   FROM resumenmarcajes
   WHERE actividad = ? AND numOp = ?
   ```
   (v20.24) Después, `SELECT SUM(pliegosIncorrectos) … WHERE actividad, numOp AND (estado IS NULL OR estado <> 'F')`: suma solo filas de operario, de todos los ciclos. Si falla o no hay valores → `NULL`. Semántica completa de la fila `F` y decisión pendiente: `10-decisiones-pendientes.md` §3.4 (P-16).
   Seguido de `INSERT (…, username='SMARTFACTORY', estado='F', …, pliegosIncorrectos)`.
   - Si ese SELECT falla (`None`), la fila `F` **se inserta igualmente** con la cantidad y los tiempos del operario actual (`cierres_service.py:884-888`) [C] (E2). Ver `05-cantidadreal.md`.
   - Antes, en el paso 2, un error de MySQL en las lecturas de `datossensados` o de la suma de MT se convierte en 0 sin aviso y el cierre continúa (E1, `05-cantidadreal.md`).
8. DELETE `datossensados WHERE numOp, actividad, mac`.
9. DELETE `marcajeactivo WHERE numOp, actividad, username` (**sin recurso ni topic**).
10. Salvo el INSERT del operario (paso 6), **ningún resultado de INSERT/DELETE se comprueba.** La respuesta es `ok:true` (R-01).
11. API: quita el marcaje de la memoria por `id` + WS.

**Flujo posterior ARR** (v20.21, `app.js:358-469`, `841-849`):
- Si `tipoCierre==="FINAL"` y el código de actividad contiene "ARR" (sin distinguir mayúsculas), se ofrece abrir el *tiraje* de la misma OP y recurso.
- Se reconstruye la OP con `/api/op/buscar`, se valida que el recurso siga en la lista y el operario elige la actividad (flujo §2).
- No hereda MAC, topic, tiempos ni cantidades.

### Esperado

- "Cierre definitivo de actividad, inserta resumen usuario + resumen SMARTFACTORY estado F" (docstring 731-740) [C, declarado].
- [?] Si el agregado debe excluir las filas `F` anteriores o filtrar por recurso (P-04).

### Problemas

- R-01: cierre no atómico.
- R-02: resta de MT ajenos.
- R-04: paro con éxito falso.
- R-13: agregado `F` acumulativo.
- R-20: DELETE de `marcajeactivo` sin recurso.
- R-21: sin log de auditoría de cierres.

---

## 5. Cierre MD (reporte parcial con la máquina detenida)

### 5.1 MD normal [C]

- Igual que FINAL, pero con `estado='MD'` y **sin** agregado `F`.
- Publica el paro y libera la máquina.
- Los MD **no** se restan en los cálculos posteriores (solo se restan los MT; `05-cantidadreal.md`).

### 5.2 Pausa por actividad improductiva (v20.22) [C]

`app.js:471-586`, `cierres_service.py:497-501, 612-617`:

1. Botón *PAUSA POR ACTIVIDAD IMPRODUCTIVA* → exige `total_usuario`.
2. Cierre **MD forzado** con `pausa_improductiva=true` → el INSERT lleva `variable01 = 1`.
3. Si el cierre va bien → el operario elige un motivo → `POST /iniciar-improductivo` con el mismo usuario y recurso.
4. Si la apertura del improductivo falla, **el MD no se revierte**. Al terminar, la página se recarga.

### 5.3 Retorno tras improductivo (v20.23) [C]

`app.js:588-751`, `cierres_service::obtener_ultimo_resumen_recurso_usuario` (58-102):

1. **Antes** de cerrar un marcaje con OP 12345: `SELECT * FROM resumenmarcajes WHERE recurso AND username ORDER BY tiempofinal DESC LIMIT 1`.
2. Si ese registro tiene `variable01 = 1` y el cierre termina bien → se ofrece reabrir la OP y actividad anteriores con el flujo normal (`/api/op/buscar` → cotizadas → no cotizadas → `/iniciar-real-bd`).
   - (2026-11-24, iteración 5) Se envía `numero_ot = registro.wo_number` si es un entero > 0 (la OT del marcaje anterior). Si ya no es candidata (409 de OT) → nueva elección con aviso y un reintento; «Volver» → error «No se pudo reanudar la actividad…», sin crear nada.
3. Si algo falla, el cierre del improductivo no se revierte.

- [I] `tiempofinal` viene del reloj del ESP, o de la hora del servidor si no hubo datos. Un desfase de relojes podría elegir un registro inesperado.

---

## 6. Cierre MT (relevo sin detener la máquina)

### Actual [C]

1. **No publica MQTT**: el ESP sigue contando.
2. INSERT `estado='MT'`.
3. **Borra `datossensados` de numOp+actividad+mac** y borra `marcajeactivo`.
4. Devuelve `relevo_pendiente` (`cierres_service.py:926-946`). (2026-11-24) Lleva `wo_number`, `tk_id`, `estadoResolucion` y `tituloOt` de `valores` y ya no `num_ot`. La UI (`construirRelevoPendienteDesdeCierre`) copia esos 4 campos de `datos.valores`.
5. La UI lo guarda **solo** en la variable JS `relevoMtPendiente` (`app.js:891-894`) y muestra el panel.
6. El siguiente operario que se identifica **en esa misma pestaña** dispara `iniciarRelevoMtAutomatico({confirmar:false})` (`app.js:263-276`, `925-975`).
7. Se llama a `POST /iniciar-relevo-mt-real` → `iniciar_relevo_mt_real_bd` (664-748).
8. Esa función construye el payload y **reutiliza `iniciar_marcaje_real_bd`**: mismas validaciones, INSERT y **nueva publicación del inicio al ESP**.
   - (2026-11-24) **Hereda** la OT sin consultar Optimus (`_validar_resolucion_relevo`, que solo valida la forma): `AUTOMATICA`/`ELEGIDA` exigen `wo_number` y `tk_id` enteros positivos; `SIN_TAREA` exige vacíos (`0` cuenta como vacío, porque el cierre envía 0/0; decisión del usuario del 2026-11-24); estado ausente o nulo (marcaje antiguo) → todo `NULL`. Datos incoherentes o un estado desconocido → 409 `DATOS_RELEVO_INCOMPLETOS` sin efectos. Se pasan como `resolucion=` a `iniciar_marcaje_real_bd`.

**Cómo se pierde el relevo**: recargar la página o pulsar *Cancelar*, identificarse en otra PC, o pulsar *Cancelar relevo* (`app.js:1007-1013`). En todos los casos:
- La máquina sigue produciendo **sin marcaje**.
- La máquina aparece **libre** y otro operario podría abrir otra OP en ella.
- Los DATOS se siguen acumulando en `datossensados` bajo la misma numOp y actividad, y los heredará el siguiente marcaje que coincida [C mecanismo / I consecuencia].

### Esperado

- "Reporte parcial sin detener máquina… Solicitar identificación inmediata del siguiente operario. No se publica MQTT de paro" (`cierres_service.py:661-662`; README_V18) [C, declarado].

### Problemas

- R-02: resta de MT acumulada entre sesiones.
- R-22: relevo frágil y volátil.
- **[?] Efecto de volver a publicar el inicio sobre el contador del ESP** (P-01).

---

## 7. Cierres desde las tarjetas del sidebar [C]

- **"Cierre general"** (`app.js:1652-1656`, `1605-1616`): solo lanza la lectura de huella. Se cierra **el marcaje de quien pone la huella**, no el de la tarjeta.
- **"Cierre SU/ADMIN"** (`app.js:1658-1662`, `1623-1648`): carga el objeto de la tarjeta como `marcajeActivoUsuario` sin huella. El INSERT usa el `username` del dueño del marcaje.
  - **No queda registro de quién cerró**: `usuarioFinalizacion` no se usa.

---

## 8. Endpoints heredados con efecto real

`cerrar-real-bd` borra `marcajeactivo` **sin resumen** y sin borrar `datossensados` (R-11). `iniciar-improductivo-bd` abre un marcaje **productivo**. Ver `03-endpoints-websockets.md`.

---

## 9. Sincronización frontend ↔ backend ↔ BD [C]

| Evento | Efecto |
|---|---|
| Carga o recarga de **cualquier** pestaña | `POST sincronizar-desde-bd` → `reemplazar_estado_marcajes(listar_marcajes_activos_bd())`. **Reemplaza toda la memoria** del proceso y la envía a sus pestañas. Se pierden los contadores MQTT en vivo |
| …si falla la lectura | `listar_marcajes_activos_bd` devuelve `[]` → **memoria vacía** y "Sin marcajes activos" en pantalla. Los bloqueos por BD siguen funcionando (R-07) |
| Apertura o cierre en este proceso | Actualiza la memoria y envía el broadcast |
| Apertura o cierre en **otro** proceso (otra PC [I] o PyQt [?]) | Este proceso no se entera hasta que sincroniza: tarjetas obsoletas y falsos `RECURSO_O_TOPIC_MEMORIA` |
| `consultar_marcaje_activo` | **Prioriza la memoria**: un marcaje obsoleto hace que el operario "tenga" un marcaje inexistente; el cierre fallará con 409 `NO_ENCONTRADO` |
| DATOS MQTT | `asociar_mensaje_mqtt_a_marcaje` actualiza los contadores del **primer** marcaje en memoria con esa MAC (solo visual) |
| Reconexión WS | El cliente reintenta cada 3 s y recibe la memoria (sin sincronizar con BD) |

---

## 10. Concurrencia y operaciones parciales (resumen)

| Situación | Resultado | Nivel |
|---|---|---|
| Dos aperturas simultáneas en la misma máquina o del mismo usuario | Ambas pueden pasar V1-V7 → dos filas, salvo que haya UNIQUE | C / ? (P-03) |
| Dos cierres del mismo marcaje | Dos filas de resumen; el segundo puede calcular 0 | C (sin guarda) |
| INSERT del resumen falla | Producción perdida; `ok:true` | C |
| DELETE de `marcajeactivo` falla | El marcaje reaparece al sincronizar; el reintento genera un resumen 0/negativo duplicado | C |
| DELETE de `datossensados` falla | Filas huérfanas que contaminan la siguiente sesión | C |
| Paro "publicado" con el broker caído | BD cerrada, ESP sigue contando | C |
| Lista en memoria modificada desde el hilo de paho y el event loop sin lock | Lecturas inconsistentes y efectos visuales | I |

Matriz completa con causas y recuperación: `09-riesgos.md`.
