# 03 — Endpoints HTTP y WebSockets

> **[C] Ningún endpoint exige autenticación ni autorización.** Los roles ADMIN/SU solo ocultan botones en el navegador. Cualquiera que llegue al puerto 8000 puede invocar cualquier ruta (R-05). Por defecto uvicorn escucha en `127.0.0.1` (`iniciar_backend_piloto.bat`), lo que limita el acceso a la propia PC [C]. Si alguna instalación cambió el host, es [?].

Leyenda de **Efecto**: L = solo lectura · M = escribe en la memoria del proceso · BD = escribe en MySQL · MQTT = publica al ESP · WS = broadcast.

## 1. Backend principal (`main.py`, puerto 8000)

| Método y ruta | Handler → servicio | Efecto | Usado por la UI | Notas |
|---|---|---|---|---|
| GET `/` | `main.py::inicio` | L | Sí | Sirve `templates/index.html` |
| GET `/api/health` | `main.py::health_check` | L | `revisarBackend` | |
| POST `/api/usuario/identificar-prueba` | `usuarios_api` → `identificar_usuario_prueba`, `consultar_marcaje_activo` | L | `identificarUsuario` | 404 si el usuario no existe **o si falla Optimus** (R-03) |
| POST `/api/op/buscar` | `ordenes_api` → `buscar_orden_produccion` | L | `buscarOp`, ARR, retorno | OP numérica, existente y elegible en `job200` (sin rango, P-20). 400 con `detail` texto. Desde v20.25 ya no devuelve `orden.num_ot`. Recursos sin filtrar por OT (R-10) |
| POST `/api/op/ots` (2026-11-24) | `ordenes_api` → `resolucion_ot_service::resolver_desde_optimus` | L | `elegirOtParaInicio` (inicio normal y, tras un 409 de OT, reapertura tras improductivo) | `{num_op, actividad}` → 200 `{ok, requiereEleccion, ots:[{numeroOt, titulo, secuencia}]}`; 409 rechazo de la OP y 503 `OPTIMUS_NO_DISPONIBLE`, ambos con `detail={ok, codigo, mensaje}`; 422 si `num_op` no es solo dígitos o `actividad` está en blanco |
| POST `/api/op/buscarRecursosExistentes` | `ordenes_api` → `buscar_recursos_improductivo` | L | `SeleccionarRecurso` | Todos los recursos de `macdirectorio` |
| POST `/api/actividades/recurso` | `obtener_actividades_por_recurso` | L | Sí | Recibe `{num_op, recurso}` (antes `num_ot`; 422 si `num_op` no es solo dígitos). Vigentes con tarea en cualquier OT de la OP |
| POST `/api/actividades/no-cotizadas` | `obtener_actividades_no_cotizadas_por_recurso` | L | Sí | Recibe `{num_op, recurso}` (antes `num_ot`). Vigentes sin tarea en ninguna OT de la OP |
| POST `/api/auth/usuario-elevado` | `auth_service::validar_usuario_elevado` | L | `abrirLoginUsuarioElevado` | Contraseña comparada en claro en SQL. 401/403. No emite token |
| POST `/api/mqtt/iniciar` | `mqtt_monitor.iniciar` | Conexión | Panel ADMIN | |
| POST `/api/mqtt/detener` | `mqtt_monitor.detener` | Conexión | Panel ADMIN | Detiene la persistencia DATOS y bloquea los cierres FINAL/MD |
| GET `/api/mqtt/estado` | `mqtt_monitor.estado` | L | Sí | |
| POST `/api/marcajes/ultimo-resumen-recurso-usuario` | `cierres_service::obtener_ultimo_resumen_recurso_usuario` | L | Retorno tras improductivo | |
| GET `/api/marcajes/modo-persistencia` | flags | L | Sí | |
| POST `/api/marcajes/preparar-inicio` | `preparar_inicio_marcaje` | L | No (heredado) | |
| POST `/api/marcajes/simular-inicio` | `simular_inicio_marcaje` | L | No (heredado) | |
| POST `/api/marcajes/iniciar-real-bd` | `persistencia_marcajes_service::iniciar_marcaje_real_bd` | **BD + MQTT + M + WS** | `seleccionarActividad`, retorno | 409 ante bloqueo. (2026-11-24) `PrepararMarcajeRequest` ya no tiene `num_ot` (se ignora si llega) y acepta **`numero_ot: int ≥ 1` opcional**. Resuelve la OT antes de cualquier efecto: rechazo → 409 `detail={ok:false, modo:'RESOLUCION_OT', codigo, mensaje, ots_candidatas?}`; **`OPTIMUS_NO_DISPONIBLE` → 503**. La respuesta correcta incluye `resolucion` |
| POST `/api/marcajes/iniciar-improductivo` | `::iniciar_marcaje_improductivo_bd` | **BD + MQTT + M + WS** | Improductivo y pausa | El handler se llama igual que el anterior (`api_iniciar_marcaje_real_bd`, línea 102). La ruta funciona [C] |
| POST `/api/marcajes/iniciar-improductivo-bd` | **`iniciar_marcaje_real_bd` (productivo)** | BD + MQTT + M + WS | No | Nombre engañoso (`api/marcajes_api.py:127-149`) |
| POST `/api/marcajes/iniciar-relevo-mt-real` | `::iniciar_relevo_mt_real_bd` | BD + MQTT + M + WS | Relevo MT | Body `dict` sin esquema. (2026-11-24) `relevo` lleva `wo_number`, `tk_id`, `estadoResolucion` y `tituloOt` (heredados, sin consultar Optimus); incoherentes → 409 `DATOS_RELEVO_INCOMPLETOS` |
| GET `/api/marcajes/activos-bd` | `listar_marcajes_activos_bd` | L | No | |
| POST `/api/marcajes/sincronizar-desde-bd` | `reemplazar_estado_marcajes` | **M (reemplazo total) + WS** | **Cada carga de página** y botón *Sincronizar BD* | Ante un error de lectura deja la memoria vacía (R-07) |
| GET `/api/marcajes/activos-simulados` | memoria | L | Respaldo de la carga inicial | |
| POST `/api/marcajes/activar-simulacion` | `agregar_marcaje_simulado` | M + WS | No (retirado en v20.5) | Puede bloquear máquinas en memoria |
| POST `/api/marcajes/cerrar-simulacion` | `cerrar_marcaje_simulado` | M + WS | No | Elimina **cualquier** id de memoria |
| POST `/api/marcajes/simular-cierre` | `cierres_service::simular_cierre_marcaje` | L (+ log de diagnóstico si sale negativo) | No | Ejecuta las consultas de cálculo. Mismo cuerpo que `ejecutar-cierre-real` (incluido `pliegos_incorrectos`) |
| POST `/api/marcajes/ejecutar-cierre-real` | `cierres_service::ejecutar_cierre_marcaje_real` | **MQTT + BD + M + WS** | `ejecutarCierreRealMarcajeActivoDelUsuario` | Ver `04-flujos-marcajes.md` §4-6. Cuerpo `SimularCierreMarcajeRequest`: `marcaje`, `tipo_cierre`, `total_usuario`, `pausa_improductiva` y (v20.24) **`pliegos_incorrectos`**, opcional: entero estricto entre 0 y 2147483647, o `null`; si falta → `NULL`. Un valor inválido → **422**. El fallo del INSERT de operario → **409** `INSERT_RESUMEN_FALLIDO` |
| POST `/api/marcajes/cerrar-real-bd` | `persistencia_marcajes_service::cerrar_marcaje_real_bd` | **BD (solo DELETE)** + M + WS | No hay botón | Borra el marcaje **sin resumen** (R-11) |

### Códigos HTTP [C]

- Los bloqueos operativos devuelven **409** con `detail` = el dict de resultado completo.
- `postJson` (`app.js:109-133`) extrae `detail.mensaje`. Desde la iteración 5 de `14-resolucion-ot.md` (2026-11-24), el `Error` lanzado lleva además `status` y `detail` (sin cambiar `message`).
- Los errores no capturados (p. ej. una excepción de `dtbOptimus` en el cierre) devuelven **500**.

## 2. WebSockets (`main.py`)

| Ruta | Al conectar | Eventos emitidos | Emisores |
|---|---|---|---|
| `/ws/marcajes` (83-106) | `MARCAGES_ACTIVOS_ACTUALIZADOS` con la lista en memoria | `MARCAGES_ACTIVOS_ACTUALIZADOS` (`marcajes`, opcionalmente `marcaje`, `marcaje_cerrado`, `resultado_*`) | Endpoints de marcajes; `mqtt_service._broadcast_marcajes_desde_hilo` cuando un DATOS se asocia |
| `/ws/mqtt` (109-131) | `MQTT_ESTADO` | `MQTT_ESTADO`, `MQTT_MENSAJE_RECIBIDO` (`mensaje`, `estado`, `asociacion`, `persistencia_simulada`) | `mqtt_service` |

- [C] El tipo se escribe `MARCAGES` (con G). Es el contrato vigente con `app.js:1598`.
- [C] Los mensajes que envía el cliente se ignoran.
- [C] El broadcast solo llega a los clientes conectados **a ese proceso**.
- [C] Desde el hilo de paho se usa `asyncio.run_coroutine_threadsafe` con el loop capturado en `iniciar`.

## 3. Servicio de huella (`huella_local/main.py`, puerto 9001)

| Método y ruta | Función | Efecto |
|---|---|---|
| GET `/api/huella/health` | `health_check` (434-452) | Comprueba el puerto con `netstat`; no abre el socket |
| GET `/api/huella/diagnostico` | `diagnostico_huella` (455-470) | Igual |
| POST `/api/huella/reiniciar-exe` | `reiniciar_exe` (473-484) | `taskkill` y relanza el `.exe` |
| POST `/api/huella/probar-comando` | `probar_comando` (487-514) | Envía un comando arbitrario al `.exe` |
| POST `/api/huella/identificar` | `identificar_huella` (517-568) | Lectura con lock no bloqueante. Detalle en `07-identificacion-biometria.md` |

## 4. Al añadir o modificar un endpoint

1. Usa un modelo Pydantic (no `dict` libre).
2. Mantén los códigos 409/400/404 que la UI espera.
3. Si cambia el estado de marcajes, actualiza la memoria **y** haz el broadcast, como hacen los endpoints existentes.
4. Documenta la ruta en este archivo y añade su prueba (`11-pruebas.md`).
