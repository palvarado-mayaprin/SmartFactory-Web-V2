# 14 — Resolución de OT y tarea al abrir un marcaje (adaptación de PRODIGOS V2)

**Estado**: diseño aprobado en sus decisiones principales (2026-11-24, `10-decisiones-pendientes.md` §4). **Implementado (v20.25.0, 2026-11-24)**: iteraciones 1 a 6 (§3). Prueba en planta pendiente (`readme/README_V20_25.md`).
**Fuente**: especificación «Extracción de OT y asignación de actividades a tareas (lógica de PRODIGOS V2)», v1.0, 2026-11-24, aportada por el usuario. Aquí solo se recoge lo que se adapta a SmartFactory y en qué difiere.

## 0. Alcance

| Entra | No entra (decidido el 2026-11-24) |
|---|---|
| Elegibilidad de la OP por `job200` (`j_status`, `j_state`, `j_locked`) | Recurso real `res_code`: el «recurso» sigue siendo el **centro de costo** (`act_cc`). MAC, topic MQTT e histórico de `resumenmarcajes.recurso` no cambian |
| Todas las OT de la OP por `wo_job` (se elimina el supuesto `OT = OP + "01"`) | Caché de contingencia de 24 h (§10 de PRODIGOS): si Optimus no responde, error y no se abre |
| Tareas candidatas y función única `resolver` (`SIN_TAREA` / `AUTOMATICA` / `ELEGIDA`) | Tabla de evidencia de candidatas (`pv2_ctCandidatosMarcaje`): basta el log de auditoría |
| Elección obligatoria de OT cuando hay 2 o más candidatas, validada también en el servidor | Idempotencia por huella de contenido (SmartFactory no la tiene) |
| OT y tarea **fijadas al abrir** y guardadas en `marcajeactivo`; el cierre ya no las recalcula (salvo el respaldo para marcajes abiertos antes de v20.25, §2.4) | Cambios en payloads MQTT: la OT no viaja al ESP [C] (`services/marcajes_service.py::construir_mensaje_mqtt_inicio`) |
| Solo actividades **vigentes** (`act_discont = 0`) | Lista de recursos (R-10, P-08): sin cambios |
| Se **conserva** el botón de actividades «no cotizadas» | |

## 1. Situación anterior (hasta v20.24) [C, histórico]

> Comportamiento **reemplazado** en v20.25. Se conserva como referencia del cambio; el actual está en §2 y en `04-flujos-marcajes.md` §2-§6.

| Punto | Código | Comportamiento |
|---|---|---|
| Validar OP | `services/ordenes_service.py::buscar_orden_produccion` | Rango 10 000–1 000 000; busca `wo200.wo_number = OP+"01"` para obtener `wo_job`; no mira estado de la OP |
| Actividades cotizadas | `services/ordenes_service.py::obtener_actividades_por_recurso` | Tareas de **una sola** OT (`OP+"01"`) con `act_cc = recurso`; incluye actividades dadas de baja |
| No cotizadas | `services/ordenes_service.py::obtener_actividades_no_cotizadas_por_recurso` | Catálogo `act` del centro de costo menos las cotizadas en `OP+"01"`; incluye dadas de baja |
| Apertura | `services/persistencia_marcajes_service.py::iniciar_marcaje_real_bd` | **No** valida OT, tarea ni actividad contra Optimus. `num_ot` llega del navegador y solo se devuelve en la vista previa |
| Cierre | `services/cierres_service.py::_obtener_wo_tk` (llamada desde `simular_cierre_marcaje`) | Recalcula `wo_number` y `MIN(tk_id)` por `wo_job` + centro de costo + actividad, **sin filtrar estado**. Si no encuentra la actividad, toma una OT cualquiera del centro de costo con `tk_id = 0`; si nada, `0, 0`. SQL por concatenación (R-15) |
| Relevo MT | `services/persistencia_marcajes_service.py::iniciar_relevo_mt_real_bd` | Reconstruye `num_ot` como `OP+"01"` |
| Frontend | `static/js/app.js::buscarOp`, `::cargarActividadesPorRecurso`, `::abrirSelectorActividadNoCotizada`, `::seleccionarActividad` → `iniciar-real-bd` y `::reabrirActividadDespuesImproductivo` (segunda vía de apertura) | Mostraba «OT: OP01» y la enviaba en cada llamada |

Inconsistencias observadas: `ordenes_service` lee `wo200`, `cierres_service` lee `wo` (P-17, cerrada).

### 1.1 Esquema de Optimus (`SHOW COLUMNS`, aportado por el usuario el 2026-11-24) [C]

| Tabla | Columnas que usa el diseño | Claves e índices |
|---|---|---|
| `wo` | `wo_number int NOT NULL`, `wo_job int`, `wo_status char(1)`, `wo_seq smallint`, `wo_title2 varchar(60)` (nulables salvo `wo_number`) | `wo_number` PRI; `wo_job` y `wo_status` indexados |
| `wo200` | Mismas columnas y tipos, **sin ninguna clave ni índice** y con menos columnas que `wo` | — |
| `job200` | `j_number int NOT NULL`, `j_status char(1)`, `j_state char(1)`, `j_locked char(1) DEFAULT '0'`, `j_title1 varchar(60)`, `j_quantity bigint` | `j_number` PRI |
| `wo_task200` | `tk_id int NOT NULL`, `tk_wonum int`, `tk_code varchar(10)`, `tk_status char(1)`, `tk_seq smallint` | `tk_id` PRI; `tk_wonum` y `tk_status` indexados; `tk_code` **sin índice** |
| `act` | `act_code varchar(10) NOT NULL`, `act_cc varchar(10)`, `act_name varchar(30)`, `act_discont char(1) DEFAULT '0'` | `act_code` PRI; `act_cc` indexado |

Consecuencias para el diseño:
- Se lee **`wo`** (tabla con clave e índice por `wo_job`). `wo200` [I] es una copia o vista parcial; no se usa en código nuevo.
- `wo_number`, `wo_job`, `tk_wonum`, `tk_id`, `wo_seq` y `tk_seq` son enteros: no hay tipos mezclados. `tk_id` nunca es nulo (PRI). `wo_seq` y `tk_seq` sí pueden serlo.
- Los estados son `char(1)` nulables. `j_locked` y `act_discont` son texto (`'0'`/`'1'`), no enteros.
- La OP (`j_number`) es entera: la entrada del operario debe validarse como dígitos antes de consultar.

## 2. Diseño implementado

### 2.1 Módulo nuevo `services/resolucion_ot_service.py`

Dos funciones **puras** (sin BD), que son el núcleo probado:

- `evaluar_elegibilidad_op(fila_job200) -> (ok, codigo, mensaje)`: orden de comprobación de PRODIGOS §3 (`X` cancelada → completitud desconocida → `j_state` → `j_locked`). Las OP `C` son elegibles.
- `resolver(ots, tareas, ot_elegida=None) -> dict`: PRODIGOS §5.3, §5.4 y §6 tal cual. Devuelve `estado`, `wo_number`, `tk_id`, `titulo_ot`, `ots_candidatas` (lista ordenada para la pantalla) o un rechazo `SELECCION_OT_REQUERIDA` / `OT_NO_CANDIDATA`.

**Decisiones de implementación (iteración 1, 2026-11-24)** [C] (`services/resolucion_ot_service.py`):
- `evaluar_elegibilidad_op` devuelve `{"ok", "codigo", "mensaje"}` y no una tupla, según la especificación de la fase 1. Solo exige las claves que evalúa (`j_status`, `j_state`, `j_locked`); si faltan o la fila no es un `dict` → `ValueError`.
- `wo_number` y `numeroOt` se devuelven normalizados como `str(x).strip()`, la misma forma en que se comparan. `tk_id` y `secuencia` (`wo_seq`) se devuelven sin convertir.
- Orden por número de OT: primero los numéricos (por valor) y luego los no numéricos (como texto).
- `wo_seq`, `tk_seq` y `tk_id` se comparan con su tipo nativo, sin convertir. Si Optimus los entrega con tipos mezclados (por ejemplo, `int` y `str` en la misma consulta), `sorted` lanza `TypeError`: revisarlo en la iteración 2 con los tipos reales (P-17).
- `ot_elegida` cuenta como enviada siempre que no sea `None` (`""` → `OT_NO_CANDIDATA`).
- Si `ots` trae dos filas con el mismo `wo_number`, gana la última. No debería ocurrir con la clave de `wo` [?].

Y una función de lectura que las combina (la **única** que usan la pantalla y la apertura):

- `resolver_desde_optimus(num_op, actividad, ot_elegida=None)`: lee `job200`, `wo` (≤100) y `wo_task200` (≤500) con `dtbOptimus1` parametrizado, valida límites y llama a `resolver`. Distingue «sin filas» de «error de Optimus» (R-03): error → `OPTIMUS_NO_DISPONIBLE`.
- OP `12345` (improductivo): no consulta Optimus → `SIN_TAREA`.

**Decisiones de implementación (iteración 2, 2026-11-24)** [C]:
- Se extrae `leer_op(num_op)` (validación + `job200` + elegibilidad), que usan `buscar_orden_produccion` y `resolver_desde_optimus`. Si tiene éxito devuelve `{ok, fila, orden:{num_op, descripcion, cantidad}}`; `orden.num_op` es `j_number` como texto (un `042150` tecleado pasa a `42150`).
- «Solo dígitos» significa dígitos **ASCII** tras `strip()` (`es_numero_op`): se rechazan `²` y otros dígitos Unicode, y también `51847-01` o `OP 51847`, que antes se limpiaban.
- `RESPUESTA_INVALIDA` también si `job200` devuelve 2 filas (imposible con la clave primaria, pero se comprueba).
- `orden` se añade también a los rechazos que vienen de `resolver` (`SELECCION_OT_REQUERIDA`, `OT_NO_CANDIDATA`). En los rechazos de lectura (`OP_*`, `OPTIMUS_NO_DISPONIBLE`, `RESPUESTA_INVALIDA`) solo hay `{ok, codigo, mensaje}`.
- Las OT se pasan a `resolver` aunque no estén abiertas (`wo_status != 'N'`): `resolver` las descarta. Sus números sí entran en el `IN` de tareas.
- `buscar_orden_produccion` lee la OP **antes** de identificar al usuario: con una OP inválida y un usuario inexistente, el mensaje es el de la OP.
- La lista de recursos (`obtener_recursos_de_orden`) sigue leyendo `wo200` sin filtro (R-10, fuera de alcance). Solo se le quitó el parámetro `num_ot`, que no usaba.

### 2.2 Actividades (se conserva el botón «no cotizadas»)

- **Cotizadas** (implementado en v20.25): actividades vigentes del centro de costo que tienen alguna tarea en **cualquier** OT de la OP (`wo_job`), sin filtrar estado, como hoy pero sin el supuesto `OP+"01"`.
- **No cotizadas**: vigentes del centro de costo que no están en la lista anterior. Al abrir resultan siempre `SIN_TAREA`.
- Las peticiones pasan de `num_ot` a `num_op` (`models/schemas.py::ActividadesRequest`).
- Implementado (iteración 2): `EXISTS`/`NOT EXISTS` sobre `wo_task200 ⨝ wo` con `wo.wo_job = %s`, más `act.act_discont = '0'` y `act.act_cc = %s`; parámetros `(recurso, num_op)`. `num_op` no numérico → `ValueError` en el servicio (la API ya lo rechaza con 422).

### 2.3 API

| Ruta | Cambio |
|---|---|
| `POST /api/op/buscar` | Elegibilidad por `job200`; sin rango (P-20, resuelta). En la iteración 2 siguió devolviendo `orden.num_ot` como campo heredado; **retirado en la iteración 5**. Mantiene 400 con `detail` texto |
| `POST /api/actividades/recurso`, `/no-cotizadas` | Reciben `num_op` |
| `POST /api/op/ots` (nueva) | `{num_op, actividad}` → `{requiereEleccion, ots:[{numeroOt, titulo, secuencia}]}`. Solo lectura. **Iteración 2**: modelo `OtsActividadRequest` con `num_op` de solo dígitos y `actividad` no en blanco (422); `SELECCION_OT_REQUERIDA` → 200 con `requiereEleccion: true`; `OPTIMUS_NO_DISPONIBLE` → 503; otros rechazos → 409, ambos con `detail={ok, codigo, mensaje}` |
| `POST /api/marcajes/iniciar-real-bd` | Acepta `numero_ot` opcional. Recalcula con `resolver_desde_optimus` **antes** de cualquier efecto; rechazo → 409 con `detail={ok:false, codigo, mensaje}` |
| `POST /api/marcajes/iniciar-relevo-mt-real` | Hereda OT, tarea y estado del marcaje que se releva (no consulta Optimus) |

### 2.4 Persistencia (requiere migración autorizada)

Script listo para ejecutar, con verificación previa, posterior y reversa: `migraciones/2026-11-24_marcajeactivo_resolucion_ot.sql`. Resumen:

```sql
ALTER TABLE smartfactory.marcajeactivo
  ADD COLUMN wo_number        INT         NULL,  -- mismo tipo que Optimus y que resumenmarcajes
  ADD COLUMN tk_id            INT         NULL,
  ADD COLUMN estadoResolucion VARCHAR(12) NULL,  -- AUTOMATICA | ELEGIDA | SIN_TAREA
  ADD COLUMN tituloOt         VARCHAR(60) NULL;
```

DDL real verificado (2026-11-24, aportado por el usuario) [C]:
- `marcajeactivo`: `idRelacion` PK autoincremental; `numOp int`, `descrip varchar(100)`, `cantidad int`, `recurso`/`actividad varchar(50)`, `username varchar(45)`, `topic`/`produccionUnidad varchar(100)`; charset `utf8mb3`. **Sin UNIQUE de negocio** (solo sobre `idRelacion`): nada impide en la BD dos filas del mismo operario o máquina (P-03, R-06).
- `resumenmarcajes.wo_number` y `.tk_id`: `int NULL`.
- Todo el código actual lee y escribe `marcajeactivo` con listas de columnas explícitas [C], así que la migración es compatible hacia atrás y puede aplicarse antes de desplegar la iteración 4. [?] La app PyQt de `../src`, si sigue en uso (P-02), no se ha revisado.

- La apertura escribe las 4 columnas en el mismo INSERT. El orden de efectos (INSERT → MQTT) **no cambia** (`04-flujos-marcajes.md` §0).
- El cierre lee `wo_number` y `tk_id` de la fila de `marcajeactivo` y los copia a `resumenmarcajes` (columnas existentes). `_obtener_wo_tk` solo queda para filas con `estadoResolucion` nulo (marcajes abiertos antes del despliegue, P-19).
- `SIN_TAREA` → en `resumenmarcajes` se escribe `0` / `0`, como hoy cuando no hay coincidencia (P-19).
- Auditoría: una línea en `marcajes_reales.log` con estado, OT, tarea, nº de OT candidatas y si el operario eligió.

**Implementación (iteración 4, 2026-11-24)** [C]:
- `construir_insert_marcajeactivo` escribe `wo_number` y `tk_id` como entero sin comillas o `NULL`. Un valor no entero, o un `estadoResolucion` fuera de `AUTOMATICA`/`ELEGIDA`/`SIN_TAREA`/`None`, lanza `ValueError` (error de programación → 500). `tituloOt` va con `limpiar_sql` entre comillas.
- `iniciar_marcaje_real_bd(payload, resolucion=None)`: resuelve con `resolver_desde_optimus` **antes** de `simular_inicio_marcaje`; el relevo pasa `resolucion`. Una actividad en blanco devuelve `VALIDACION_BLOQUEADA` antes de consultar Optimus (`resolver_desde_optimus` lanzaría `ValueError`).
- `resolucion` en la respuesta: `{wo_number, tk_id, estadoResolucion, tituloOt, ots_candidatas: nº de OT, ot_elegida: bool}`. En el relevo solo trae los 4 primeros. El log `APERTURA_REAL_OK` registra `ot_elegida=si|no|heredada`.
- Los campos de resolución se inyectan en el servidor; el navegador no puede enviarlos (Pydantic ignora campos extra).
- La vista previa (`preparar_inicio_marcaje`, que usa `simular_inicio_marcaje`) sustituye `num_ot` por `wo_number`. Los endpoints `preparar-inicio`/`simular-inicio` no resuelven la OT (vista previa con `NULL`).
- Relevo con `SIN_TAREA`: el cierre envía `0`/`0` en `valores` (lo que va a `resumenmarcajes`), así que el relevo acepta `0` como vacío (decisión del usuario, 2026-11-24). `AUTOMATICA`/`ELEGIDA` exigen enteros **positivos**.
- Cierre: un `estadoResolucion` desconocido se trata como nulo (respaldo `_obtener_wo_tk`) para no bloquear el cierre. `dtbSmartFactory` no admite parámetros: `_obtener_ot_fijada` usa `limpiar_sql`, como el SELECT de existencia.
- `/iniciar-improductivo-bd` (productivo con nombre engañoso, sin uso en la UI) también resuelve la OT, pero responde 409 incluso con `OPTIMUS_NO_DISPONIBLE` (solo `iniciar-real-bd` mapea el 503).

### 2.5 Frontend (lo más simple posible)

- Tras elegir la actividad, `POST /api/op/ots`. Si `requiereEleccion`: un `Swal` con `input: "radio"` titulado «¿En qué parte de la orden trabaja?», una opción por OT (`titulo` y «OT n»), con el orden del servidor y solo «Volver».
- Se envía `numero_ot` solo si el operario eligió. Ante 409 `SELECCION_OT_REQUERIDA`/`OT_NO_CANDIDATA`: se repite la consulta y se muestra el aviso «Las partes de la orden cambiaron; vuelva a elegir».
- Lo mismo en `reabrirActividadDespuesImproductivo` (`static/js/app.js:635`).
- Se quita la línea «OT: OP01» y se muestra «Parte: título u OT n» en la confirmación y en el diálogo de éxito (en la tarjeta del sidebar, no: ver la implementación más abajo). Textos con `escaparHtml` (R-27).

**Implementación (iteración 5, 2026-11-24)** [C]:
- `static/js/resolucion_ot.js` (lógica pura): `etiquetaOt` (HTML escapado: título y, debajo, `<small>OT n</small>`; sin título, «OT n») y `construirOpcionesOt` (devuelve un `Map`, porque un objeto reordenaría las claves numéricas y perdería el orden por `wo_seq`). SweetAlert2 acepta un `Map` en `inputOptions` y pinta las etiquetas como HTML.
- `app.js`: `elegirOtParaInicio(numOp, actividadCodigo, aviso)` (consulta `op/ots`; «Continuar» / «Volver»; `null` si vuelve atrás) e `iniciarMarcajeRealConOt(cuerpo, numeroOt)` (envía `numero_ot` solo si hay elección; ante 409 de OT, nueva elección con aviso y **un** reintento; `null` si el operario vuelve atrás). `postJson` añade `error.status` y `error.detail`.
- Inicio normal: la elección va **antes** de la confirmación; «Volver» registra «Inicio cancelado» y deja la pantalla en el paso de la actividad. «Volver» en la nueva elección tras un 409 hace lo mismo. La consulta `op/ots` está dentro del `try`: sus errores (p. ej. 503) muestran el diálogo «No se pudo iniciar el marcaje».
- «Parte» se muestra en la confirmación (si hubo elección) y en el diálogo de éxito (`AUTOMATICA`/`ELEGIDA`). **No** en la tarjeta del sidebar: la memoria y `listar_marcajes_activos_bd` no conocen la OT (fuera del alcance de esta iteración).
- Reapertura tras improductivo: reutiliza `registro.wo_number` del último resumen (entero > 0) como `numero_ot`. Si ya no es candidata → 409 → nueva elección con aviso; «Volver» → error «No se pudo reanudar la actividad…», sin crear nada.
- `orden.num_ot` se quitó de `/api/op/buscar` y las líneas «OT:» de `infoOrden`. Solo quedan menciones a `num_ot` en pruebas que comprueban que el campo antiguo se ignora o se rechaza.

## 3. Iteraciones

Cada una deja las pruebas en verde y se entrega por separado.

| # | Entrega | Toca | Autorización |
|---|---|---|---|
| 1 | `resolucion_ot_service.py` con `evaluar_elegibilidad_op` y `resolver` + pruebas (PRODIGOS §14, casos 1-6 y 8). **Implementada el 2026-11-24** (`tests/test_resolucion_ot.py`) | Solo código nuevo | No |
| 2 | Lecturas de Optimus (`resolver_desde_optimus`, actividades vigentes) + `op/buscar` y actividades por `num_op` + endpoint `op/ots`. **Implementada el 2026-11-24** (`tests/test_resolucion_ot_optimus.py`) | `ordenes_service`, `ordenes_api`, `schemas`, `app.js` (solo `num_ot` → `num_op` en las 5 llamadas de actividades) | No (lectura). P-17 cerrada |
| 3 | Migración de `marcajeactivo` | BD de producción | **Hecha (2026-11-24)**: ejecutada por el usuario en `smartfactory`; verificada |
| 4 | Apertura con resolución y 409; relevo hereda; cierre lee de `marcajeactivo` con respaldo. **Implementada el 2026-11-24** (`tests/test_ot_fijada.py`) | `persistencia_marcajes_service`, `marcajes_service`, `cierres_service`, `marcajes_api`, `schemas`, `app.js` (solo `construirRelevoPendienteDesdeCierre`) | **Sí** (cierre), autorizada el 2026-11-24 |
| 5 | Frontend (§2.5). **Implementada el 2026-11-24** (`tests/js/resolucion_ot.test.js` + comprobación manual pendiente en el navegador) | `app.js`, `resolucion_ot.js` (nuevo), `index.html`, `ordenes_service` (quita `orden.num_ot`) | No |
| 6 | Documentación final y versión 20.25.0 (`readme/README_V20_25.md`). **Hecha el 2026-11-24** | `docs/ai`, `CLAUDE.md`, `main.py`, `templates/index.html` (versión) | Versión autorizada el 2026-11-24 |

## 4. Pruebas críticas (solo estas)

- `resolver`: 0/1/varias OT; tarea repetida con `tk_seq` nulo; OT o tarea no abiertas; orden `wo_seq` con nulos al final; `OT_NO_CANDIDATA`; `SELECCION_OT_REQUERIDA`.
- Elegibilidad: `X`, `R`, `S`, bloqueada, valores desconocidos o nulos; `C` elegible.
- Límites: 101 OT o 501 tareas → error, sin abrir.
- Apertura: un rechazo de resolución no produce INSERT ni MQTT (`bd.secuencia()` vacía); `ELEGIDA` escribe OT y tarea en el INSERT.
- Cierre: copia OT/tarea de `marcajeactivo` sin consultar Optimus; fila antigua sin estado → respaldo `_obtener_wo_tk`.
- Las pruebas de caracterización de apertura y cierre siguen en verde salvo las expectativas que cambia este diseño, actualizadas con la referencia a la decisión del 2026-11-24.
