# 01 — Arquitectura, estructura y estado

## 1. Propósito del sistema

SmartFactory Web v2 es la versión web de la app de escritorio PyQt (`../src`) para **registrar el tiempo y la producción de los operarios de planta** (Mayaprin). En la práctica:

- Un operario se identifica con su huella.
- Abre un *marcaje* (operario + OP + recurso/máquina + actividad).
- El sensor ESP de la máquina envía conteos por MQTT.
- Al cerrar, se calculan la cantidad producida y los tiempos, que quedan en `smartfactory.resumenmarcajes` [C].

## 2. Componentes en ejecución

```
 Navegador (index.html + app.js)
   │  HTTP/WS  http://127.0.0.1:8000           HTTP  http://127.0.0.1:9001
   ▼                                            ▼
 Backend FastAPI (main.py)                    Servicio de huella (huella_local/main.py)
   ├─ api/*  → services/*                       └─ TCP 127.0.0.1:8888 → EnrollmentSample CS.exe [?]
   ├─ WS /ws/marcajes, /ws/mqtt
   ├─ hilo paho-mqtt (services/mqtt_service.py) ⇄ broker MQTT ⇄ ESP de cada máquina [?]
   └─ db/conexion.py → MySQL smartfactory (L/E) · MySQL Optimus "mayaprin" (L) · SQL Server entregasDiarias (sin uso activo)
```

- **[C]** Los dos servicios se arrancan con `iniciar_todo_piloto.bat`.
- **[C]** El navegador habla **directamente** con el servicio de huella (`static/js/app.js:63,86`).
- **[C]** El CORS de la huella solo admite el origen `127.0.0.1:8000` y `localhost:8000` (`huella_local/main.py:55-64`).
- **[I]** Se despliega **un backend por PC de marcaje**. Lo sugieren el CORS, que los `.bat` escuchen en 127.0.0.1 y la evidencia de filas duplicadas (ver `10-decisiones-pendientes.md` P-02). **No está confirmado.**

## 3. Estructura del repositorio

| Ruta | Rol |
|---|---|
| `main.py` | App FastAPI v20.24.0: monta `static/`, plantillas, 5 routers, `/`, `/api/health`, WS `/ws/marcajes` (83-106) y `/ws/mqtt` (109-131). Arranca y detiene MQTT en los eventos `startup`/`shutdown` (37-66). Añade `../src` a `sys.path` (11-13) |
| `config.py` | Carga `.env` desde el directorio actual, el del proyecto y el padre, sin sobrescribir variables existentes (14-41). Define 3 flags con valor por defecto **"1"** (50-52) |
| `db/conexion.py` | Clases `dtbSmartFactory` (9-50), `dtbOptimus` (53-73), `dtbOptimus1` (76-109) y `dtbEntregasDiarias` (112-140). **Contiene credenciales en claro** |
| `api/usuarios_api.py` | `/api/usuario/identificar-prueba` |
| `api/ordenes_api.py` | `/api/op/*`, `/api/actividades/*` |
| `api/marcajes_api.py` | 16 endpoints `/api/marcajes/*` |
| `api/mqtt_api.py` | `/api/mqtt/{iniciar,detener,estado}` |
| `api/auth_api.py` | `/api/auth/usuario-elevado` |
| `models/schemas.py` | Modelos Pydantic de entrada. `marcaje` en los cierres es un `dict` sin esquema (57) |
| `services/usuarios_service.py` | Identificación en Optimus `staf`; marcaje activo del usuario (memoria → BD) |
| `services/auth_service.py` | Login de usuario elevado contra `smartfactory.superusuarios` |
| `services/ordenes_service.py` | OP/OT, recursos y actividades (Optimus); recursos para improductivo (`macdirectorio`) |
| `services/marcajes_service.py` | Validaciones previas a la apertura, MAC por recurso, payload MQTT de inicio, texto del INSERT. **Lo "simulado" forma parte del camino real** |
| `services/persistencia_marcajes_service.py` | Apertura real (productiva e improductiva), cierre heredado `cerrar_marcaje_real_bd`, relevo MT |
| `services/cierres_service.py` | Cierres FINAL/MD/MT, `cantidadreal`, diagnóstico de negativos, último resumen |
| `services/mqtt_service.py` | `MqttMonitorService`: conexión, suscripción, `_on_message` y `publicar` |
| `services/mqtt_persistencia_simulada_service.py` | Persistencia **real** de DATOS en `mensajes_mqtt` y `datossensados` (el nombre es heredado) |
| `services/marcajes_estado_service.py` | Lista en memoria de marcajes activos; asociación con mensajes MQTT |
| `services/mqtt_estado_service.py` | Estado MQTT y buffer de los últimos 80 mensajes |
| `realtime/websocket_manager.py`, `realtime/mqtt_websocket_manager.py` | Broadcast a los WebSockets conectados **a este proceso** |
| `huella_local/main.py` | Servicio FastAPI independiente para el lector de huella |
| `static/js/app.js` | Toda la lógica de la UI (≈2.000 líneas, JS sin framework, SweetAlert2 desde CDN) |
| `templates/index.html` | Página única |
| `static/css/estilos.css` | Estilos |
| `*.bat` | Arranque piloto (fijan los flags a 1) |
| `readme/README_V*.md` | Notas por versión (histórico; intención, no comportamiento verificado) |
| `cambios_*.diff`, `resumen_cambios.txt` | Diffs históricos versionados. **No editar** |
| `logs/` (ignorado) | Logs operativos reales: `marcajes_reales.log`, `cantidadreal_negativos.log`, `mqtt_persistencia.log` (≈658 MB, sin rotación), `mqtt_conglomerado_alertas.log` |
| `venv/` (ignorado) | Python 3.10.4, entorno de **producción** (lo usan los `.bat`) |
| `.venv-test/` (ignorado) | Entorno de **pruebas** aislado, sin drivers de BD ni MQTT (`requirements-dev.txt`) |
| `tests/`, `pytest.ini`, `requirements-dev.txt` | Pruebas automatizadas (`11-pruebas.md`) |
| `.claude/settings.json` | Permisos de Claude Code: matriz de autonomía de `12-procedimiento-desarrollo.md` §2 |
| `docs/ai/`, `CLAUDE.md` | Esta documentación |

## 4. Mapa de dependencias entre módulos [C]

```
main ─┬─ api.usuarios ── services.usuarios ─┬─ db.conexion (Optimus1, SmartFactory)
      │                                     └─ services.marcajes_estado
      ├─ api.ordenes ── services.ordenes ─┬─ db.conexion (Optimus1, SmartFactory, EntregasDiarias*)
      │                                   └─ services.usuarios
      ├─ api.auth ── services.auth ── db.conexion
      ├─ api.mqtt ── services.mqtt
      ├─ api.marcajes ─┬─ services.marcajes ─┬─ db.conexion
      │                │                     ├─ services.usuarios
      │                │                     └─ services.marcajes_estado (import diferido)
      │                ├─ services.persistencia_marcajes ─┬─ config, db.conexion, services.marcajes
      │                │                                  └─ services.mqtt (import diferido: publicar)
      │                ├─ services.cierres ─┬─ config, db.conexion (SmartFactory, Optimus)
      │                │                    ├─ services.marcajes (limpiar_sql)
      │                │                    └─ services.mqtt (import diferido: publicar)
      │                ├─ services.marcajes_estado
      │                └─ realtime.websocket_manager
      ├─ realtime.* 
      └─ services.mqtt ─┬─ realtime.* (ambos managers)
                        ├─ services.mqtt_estado
                        ├─ services.marcajes_estado (asociar)
                        ├─ services.mqtt_persistencia_simulada ── config, db.conexion
                        └─ db.conexion
huella_local.main: independiente (no importa nada del backend)
```

\* `dtbEntregasDiarias` se importa, pero su consulta está comentada (`services/ordenes_service.py:36-55`).

**Puntos de alto acoplamiento**:

- `limpiar_sql` (`services/marcajes_service.py:8-19`) se usa en persistencia y cierres.
- `simular_inicio_marcaje*` (`services/marcajes_service.py:319-402`) **forma parte del camino real** de la apertura.
- `mqtt_monitor` es un singleton compartido por la apertura, el cierre y `main`.

## 5. Estado del sistema: tres fuentes de verdad

| Estado | Ubicación | Escritores | Lectores | Vida |
|---|---|---|---|---|
| Marcajes activos persistentes | Tabla `smartfactory.marcajeactivo` | Apertura (INSERT), cierre (DELETE) | Validaciones, sincronización | BD |
| Marcajes activos "en vivo" | `_MARCAJES_ACTIVOS_SIMULADOS` (`services/marcajes_estado_service.py:8`), **una lista por proceso** | Endpoints de apertura y cierre, sincronización, hilo MQTT (`asociar_mensaje_mqtt_a_marcaje`) | `consultar_marcaje_activo`, bloqueo de máquina en memoria, sidebar, WebSockets | Se pierde al reiniciar uvicorn |
| Estado de pantalla | Variables globales `app.js:1-12` (`usuarioActual`, `marcajeActivoUsuario`, `relevoMtPendiente`, rol elevado…) | Navegador | Navegador | Se pierde al recargar. El botón *Cancelar* recarga (`app.js:33-35`) |

Reglas de sincronización entre estas fuentes: `04-flujos-marcajes.md` §9.

Identificador en memoria [C]: `"{modo}|{username}|{numOp}|{recurso}|{actividad}"` con `modo=REAL_BD` (`services/persistencia_marcajes_service.py:48`, `services/usuarios_service.py:14`). Reabrir la misma combinación produce el mismo id.

## 6. Frontend [C]

- **Carga inicial** (`app.js:1687-1692`, `1869-1870`):
  - `revisarBackend`, `revisarServicioHuellaLocal`, `consultarModoPersistencia`.
  - `cargarMarcajesActivosIniciales` (**POST `sincronizar-desde-bd`**, que reemplaza la memoria del backend).
  - `conectarWebSocketMarcajes`, `aplicarVisibilidadPorRol`, `cargarEstadoMqtt`, `conectarWebSocketMqtt`.
- **Pasos de la UI**: 1 usuario → 2 OP → 3 actividad (`activarPaso`, `app.js:22-30`). Paneles: cierre, relevo MT, improductivo.
- **Roles** ADMIN/SU: **solo visibilidad CSS** (`.admin-only`, `.su-admin-only`; `app.js:1972-1987`). El backend no aplica ningún permiso.
- **Riesgo de XSS**: hay muchos `innerHTML` con datos de BD o MQTT sin escapar (p. ej. `app.js:1254`, `1533-1557`, `1825-1831`) [C]. Impacto [?] (los datos vienen de sistemas internos).
- **Dependencia externa**: SweetAlert2 desde `cdn.jsdelivr.net` sin versión exacta (`templates/index.html:210`). Sin internet, los diálogos fallan [I].
- **Funciones heredadas sin efecto** (se conservan por compatibilidad): `renderSimulacionCierre`, `renderSimulacionMarcaje`, `activarMarcajeSimulado`, `iniciarMarcajeRealBd`, `cerrarMarcajeSimulado`.
- `cerrarMarcajeRealBdDesdeTexto`/`cerrarMarcajeRealBd` siguen definidas y llaman al endpoint heredado `cerrar-real-bd`. **[C] No hay ningún botón que las invoque.**
