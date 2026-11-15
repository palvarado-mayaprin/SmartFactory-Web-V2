# 08 — Configuración, despliegue y entorno

## 1. Flags de escritura (`config.py`) [C]

| Variable | Valor por defecto en el código | Controla |
|---|---|---|
| `SMARTFACTORY_ENABLE_REAL_DB_WRITES` | **"1"** | INSERT/DELETE de marcajes y resúmenes |
| `SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES` | **"1"** | INSERT de `mensajes_mqtt` y `datossensados` |
| `SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH` | **"1"** | Publicación de inicio y paro al ESP |

- Valores verdaderos: `1, true, yes, on, si, sí` (`config.py:44-46`).
- Los flags se leen **al importar** el módulo; para cambiarlos hay que reiniciar uvicorn.
- `.env` se busca en el directorio actual, en el del proyecto y en el padre; **no sobrescribe** variables ya definidas (`config.py:14-41`).
- El `.env` local (ignorado por git) activa los tres flags [C, revisado sin mostrar valores sensibles].
- Los `.bat` piloto también los fijan a 1.

⚠️ **Consecuencia**: arrancar el backend o importar `config`/`db`/`services` en esta copia puede **escribir en producción y publicar a las máquinas**. Para cualquier prueba hay que forzar los flags a `"0"` en el entorno **antes** de importar, **y además** sustituir `db.conexion` por un mock (los flags no protegen las lecturas ni la conexión a MQTT).

## 2. Otras variables [C]

- MQTT: `SMARTFACTORY_MQTT_BROKER`, `_PORT`, `_USER`, `_PASSWORD` (con valores por defecto en el código).
- Huella: `SMARTFACTORY_HUELLA_MODO`, `_HOST`, `_PORT`, `_COMANDO`, `_TIMEOUT_SEGUNDOS`, `_REINTENTOS_CONEXION`, `_ESPERA_REINTENTO`, `_REINICIAR_EXE_ANTES_LECTURA`, `_USUARIO`, `SMARTFACTORY_ENROLLMENT_EXE_PATH`.
- `SMARTFACTORY_BACKEND_HOST/PORT` (en `.env.piloto.example` e `iniciar_backend_piloto.bat`) y `SMARTFACTORY_HUELLA_LOCAL_HOST/PORT` (solo en `.env.piloto.example`) **no las lee ningún código Python** [C]. El host y el puerto los fija la línea de `uvicorn` en el `.bat`.
- **La BD no es configurable**: los hosts y credenciales están fijos en `db/conexion.py` [C].

## 3. Arranque [C]

| Script | Acción |
|---|---|
| `iniciar_todo_piloto.bat` | Abre dos ventanas: backend y huella |
| `iniciar_backend_piloto.bat` | Flags a 1, activa `venv`, `uvicorn main:app --host 127.0.0.1 --port 8000` |
| `iniciar_huella_local_piloto.bat` | Modo REAL, `uvicorn huella_local.main:app --host 127.0.0.1 --port 9001` |
| `run_huella_local.bat` | Huella con `--reload` |
| `verificar_servicios_piloto.bat` | `curl` a los dos `/health` |

## 4. Dependencias [C]

- `requirements.txt` **no fija versiones**: fastapi, uvicorn, jinja2, pydantic, paho-mqtt, mysql-connector-python, pyodbc, websockets.
- Instaladas en el `venv` (Python 3.10.4): FastAPI 0.136.1, Starlette 1.0.0, uvicorn 0.46.0, pydantic 2.13.4, paho-mqtt 2.1.0, mysql-connector-python 9.7.0, pyodbc 5.3.0, Jinja2 3.1.6, websockets 16.0.
- Frontend: SweetAlert2 desde CDN (`@11`, sin versión exacta).
- `pyodbc` requiere "ODBC Driver 17 for SQL Server" solo para `dtbEntregasDiarias`, que no se usa.
- **Entorno de pruebas** `.venv-test` (Python 3.10.4, creado el 2026-11-13):
  - Usa las mismas versiones de FastAPI, Starlette, pydantic y Jinja2 que producción, más pytest 8.4.2 y httpx 0.28.1.
  - **No** incluye `mysql-connector-python`, `pyodbc` ni `paho-mqtt`, a propósito.
  - Ver `requirements-dev.txt` y `11-pruebas.md`.
- [I] En `__pycache__/` hay `.pyc` de CPython 3.13 fechados el 2026-09-09: alguien ejecutó el proyecto con 3.13 en algún momento. Producción y pruebas usan 3.10.4.

## 5. Despliegue

- **[C]** Cada PC con lector ejecuta el servicio de huella local (README_V20, README_V20_12).
- **[I]** Cada PC también ejecuta su propio backend, por el CORS de la huella y el host 127.0.0.1. README_V20 contempla un "servidor central" que la configuración actual no permite sin cambios. **Pendiente de confirmar** (P-02).
- **[?]** Número de PCs, si la app PyQt sigue en uso en paralelo, y cómo se actualiza el código en cada PC.
- **Versión**: `main.py:25` y `/api/health` indican `20.24.0`. Cada versión documenta sus cambios en `readme/README_V*.md`.

## 6. Logs (`logs/`, ignorado por git) [C]

| Archivo | Escritor | Contenido |
|---|---|---|
| `marcajes_reales.log` | `persistencia_marcajes_service::_log_accion` | Aperturas (OK, bloqueadas, protegidas, error) y el cierre heredado. **No registra los cierres de `ejecutar_cierre_marcaje_real`** |
| `cantidadreal_negativos.log` | `cierres_service::_log_cantidadreal_negativa` | Diagnóstico JSON completo de cada `cantidadreal < 0` (incluye esquemas y filas) |
| `mqtt_persistencia.log` | `mqtt_persistencia_simulada_service::_log` | Una línea por INSERT; ≈658 MB, **sin rotación** |
| `mqtt_conglomerado_alertas.log` | `::_log_alerta_conglomerado` | Valores > 48 |

Los logs contienen **datos operativos reales**: trátalos como confidenciales y no los subas a servicios externos.

## 7. Git [C]

- Remoto: `github.com/palvarado-mayaprin/SmartFactory-Web-V2`, rama `main`. [?] Visibilidad pública o privada (P-12).
- En esta máquina, git rechaza el repo por "dubious ownership". Usa `git -c safe.directory=D:/VSCODE/SMARTFACTORY/src_web <cmd>` y **no cambies la configuración global** sin autorización.
- El cambio `OR recursoalternativo` (`services/marcajes_service.py:32`), sin commit al 2026-11-13, se versiona en un commit propio previo a v20.24 (aprobado el 2026-11-15). **No lo modifiques ni lo reviertas** sin autorización (P-09).
- **Prerrequisitos de despliegue [?]**: `macdirectorio.recursoalternativo` (P-09) y `resumenmarcajes.pliegosIncorrectos` (P-15) deben existir en **cada** BD a la que apunte un backend. Sin la primera, toda apertura responde "No existe sensor/MAC"; sin la segunda, todo cierre responde 409.
- Los mensajes de commit históricos son en español, con fecha `DDMMAAAA`.
