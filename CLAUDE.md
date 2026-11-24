# SmartFactory Web v2 — guía para Claude Code

Sistema web de **marcajes de producción en planta** (Mayaprin). Los operarios se identifican con su huella y abren y cierran marcajes (operario + OP + recurso + actividad). Los sensores ESP envían conteos por MQTT. Al cerrar, se calcula la producción (`cantidadreal`) en MySQL `smartfactory.resumenmarcajes`. Sustituye a la app PyQt de `../src`. Versión 20.25.1.

**Stack**:
- Backend: Python 3.10 · FastAPI · uvicorn · paho-mqtt · mysql-connector.
- Frontend: JS sin framework + SweetAlert2.
- Servicio local de huella: FastAPI → `EnrollmentSample CS.exe` (no incluido en el repo).

## Prioridad actual

**Desarrollo frontend/backend**: pantallas, formularios, UX, endpoints, servicios, SQL, integración, validación y pruebas de lo desarrollado. **Postergado**: simulador MQTT y emulación de ESP. Si un requisito toca sensores, cálculos de producción o mensajes MQTT → analiza el impacto y **pide aprobación**. Nada de refactorizaciones generales que el requisito no necesite.

## ⚠️ Esta copia escribe en PRODUCCIÓN

`config.py` activa por defecto la escritura real en BD, la persistencia MQTT y la publicación a los ESP. `db/conexion.py` apunta a las BD reales. **Sin autorización explícita:**
- **No** arranques `uvicorn` ni los `.bat`, ni ejecutes con `venv\` nada que importe `config`/`db`/`services`. Las pruebas van **solo** en `.venv-test\`.
- **No** te conectes a MySQL, Optimus ni MQTT. Sin migraciones ni DML real.
- **No** cambies flags, `.env`, credenciales, `db/conexion.py`, `config.py` ni `.bat`.
- **No** hagas commit ni push. Para git: `git -c safe.directory=D:/VSCODE/SMARTFACTORY/src_web …`.
- **No** modifiques ni reviertas el `OR recursoalternativo` de `services/marcajes_service.py:32` (P-09: versionado en un commit propio; semántica y columna aún por confirmar).
- **No** edites el histórico (`logs/`, `cambios_*.diff`, `resumen_cambios.txt`). `readme/` y `docs/ai/auditoria/` solo se amplían.
- **No** copies credenciales ni datos de `logs/` fuera de la máquina.

Matriz completa de lo que puedes hacer solo y lo que requiere autorización: `docs/ai/12-procedimiento-desarrollo.md` §2 (reflejada en `.claude/settings.json`).

## Mapa rápido

| Necesito… | Ir a |
|---|---|
| Arranque, routers, WebSockets | `main.py` |
| Flags y `.env` | `config.py` |
| Acceso a BD (sin transacciones; `None` solo ante `mysql.connector.Error`, otras excepciones se propagan — `docs/ai/02-base-de-datos.md` §1; SmartFactory sin parámetros) | `db/conexion.py` |
| Endpoints / modelos de entrada | `api/*.py`, `models/schemas.py` |
| Apertura de marcajes | `services/marcajes_service.py`, `services/persistencia_marcajes_service.py` |
| Cierres FINAL/MD/MT y `cantidadreal` | `services/cierres_service.py` |
| MQTT | `services/mqtt_service.py`, `services/mqtt_persistencia_simulada_service.py` (escribe de verdad) |
| Estado en memoria | `services/marcajes_estado_service.py` |
| OP, recursos, actividades (Optimus) | `services/ordenes_service.py` |
| Identificación y usuarios elevados | `services/usuarios_service.py`, `services/auth_service.py`, `huella_local/main.py` |
| UI | `static/js/app.js`, `templates/index.html`, `static/css/estilos.css` |
| Pruebas | `tests/` (dobles en `tests/conftest.py`) |

## Documentación

Índice: [`docs/ai/README.md`](docs/ai/README.md).

| Doc | Contenido |
|---|---|
| `01-arquitectura` | Arquitectura y dependencias |
| `02-base-de-datos` | Tablas y quién escribe |
| `03-endpoints-websockets` | Catálogo de rutas |
| `04-flujos-marcajes` | **§0 orden de efectos** y todos los flujos |
| `05-cantidadreal` | Fórmula y escenarios de error |
| `06-mqtt-sensores` | Broker, topics, payloads (alcance actual en §0) |
| `07-identificacion-biometria` | Huella, identificación, roles |
| `08-configuracion-despliegue` | Flags, entornos, logs |
| `09-riesgos` | R-xx |
| `10-decisiones-pendientes` | P-xx, recomendaciones M-xx no aprobadas, discrepancias |
| `11-pruebas` | Pruebas y fixtures |
| `12-procedimiento-desarrollo` | **Procedimiento y estrategia** |
| `13-entorno-desarrollo-bd` | Aislamiento de MySQL: propuesta |
| `14-resolucion-ot` | Resolución de OT y tarea (PRODIGOS): diseño |

Etiquetas: **[C]** confirmado · **[I]** inferido · **[?]** no verificable. No conviertas hipótesis en hechos ni recomendaciones en reglas de negocio.

## Hechos que no se deben olvidar

- La **apertura** hace INSERT y **después** publica MQTT. Los cierres **FINAL/MD** publican **antes** de tocar la BD. **MT** no publica.
- El cierre **no es transaccional**. Solo comprueba el INSERT del operario: si falla, aborta sin DELETE (v20.24); el resto no se comprueba (R-01). `publicar` puede devolver éxito con el broker caído (R-04).
- `totalUsuario` (pliegos buenos declarados), `pliegosIncorrectos` (v20.24) y `cantidadreal` (sensor) son **independientes**: ninguno se resta de otro.
- La OT y la tarea se fijan al abrir (`marcajeactivo`) y el cierre las copia; no se recalculan (v20.25).
- Improductivo = OP centinela `12345`. `cantidadreal = última cantpliegos − SUM(MT de numOp+actividad)`, sin acotar (R-02).
- No hay autenticación en el servidor; los roles ADMIN/SU solo existen en CSS (R-05).
- Las pruebas marcadas `caracterizacion` fijan el comportamiento **actual**, defectos incluidos. No cambies su expectativa sin una decisión aprobada.

## Procedimiento obligatorio (detalle: `docs/ai/12-procedimiento-desarrollo.md` §1)

1. Interpretar el requerimiento.
2. Consultar la documentación del área, los riesgos y las decisiones pendientes.
3. Localizar el código y los llamadores (UI → API → servicio → SQL/MQTT → memoria/WS).
4. Evaluar impacto y riesgos con la matriz de autonomía.
5. Diseñar la solución más simple y compatible, reutilizando patrones.
6. Implementar solo lo necesario.
7. Pruebas: `.venv-test\Scripts\python.exe -m pytest` + pruebas nuevas.
8. Revisar el diff: solo archivos previstos, sin credenciales ni regresiones.
9. Actualizar `docs/ai` (área, §0 de flujos si cambia el orden, estado R/P/M).
10. Entregar un resumen técnico: qué, por qué, cómo se validó, qué **no** se validó y riesgos.

**Convenciones**:
- Código y mensajes en español.
- Los servicios devuelven `{"ok", "modo", "mensaje"}`; la API responde 409 con `detail=resultado` y la UI lee `detail.mensaje`.
- Los cambios de estado de marcajes actualizan la memoria **y** hacen broadcast `MARCAGES_ACTIVOS_ACTUALIZADOS`.
- Entrada con Pydantic. SQL nuevo **parametrizado**.
- En JS nuevo, escapa lo que va a `innerHTML`.
- Mantén este archivo corto; el detalle va en `docs/ai/`.
