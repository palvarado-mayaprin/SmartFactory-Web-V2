# SmartFactory Web v2 — Fase 1: auditoría del repositorio (instantánea)

> **INSTANTÁNEA HISTÓRICA (2026-11-13). No se edita.** Reconstrucción fiel del resumen de la Fase 1 que se entregó en la conversación.
> La documentación vigente está en `docs/ai/`. Base: commit `3d325c0` más el cambio sin commit de `services/marcajes_service.py:32`.

## Corrección posterior (Fase 3)

El resumen de la Fase 1 describía la apertura así: "valida → publica MQTT de inicio → si OK, INSERT `marcajeactivo`". **Es incorrecto.**

El código real (`services/persistencia_marcajes_service.py::iniciar_marcaje_real_bd`) hace:

1. Validaciones.
2. **INSERT** en `marcajeactivo` (línea 248).
3. **Publicación MQTT de inicio después** (líneas 273-295).

Si la publicación falla, el marcaje queda abierto y la respuesta sigue siendo `ok:true`.

En los cierres FINAL/MD el orden es el inverso: primero MQTT y luego BD. Ver `docs/ai/04-flujos-marcajes.md` §0 ("Orden de efectos por ruta").

## Resumen original (con la corrección aplicada)

1. **Raíz**: `D:\VSCODE\SMARTFACTORY\src_web`, un solo repo git.
   - Rama `main`, remoto GitHub `palvarado-mayaprin/SmartFactory-Web-V2`, 6 commits (2026-09-07 → 2026-10-12).
   - Git exige `-c safe.directory=...` por "dubious ownership".
   - `../src` es la app PyQt heredada; `main.py:11-13` la añade a `sys.path`.
2. **Código fuente**: unas 7.760 líneas, en `main.py`, `config.py`, `db/`, `api/`, `services/`, `realtime/`, `models/`, `huella_local/`, `static/`, `templates/`.
3. **Puntos de entrada**:
   - `uvicorn main:app` en el puerto 8000.
   - `uvicorn huella_local.main:app` en el puerto 9001.
   - Frontend en `GET /`.
4. **Stack**: FastAPI 0.136.1, Starlette 1.0.0, uvicorn 0.46.0, pydantic 2.13.4, paho-mqtt 2.1.0, mysql-connector 9.7.0, pyodbc 5.3.0, Python 3.10.4. `requirements.txt` no fija versiones.
5. **Endpoints**: 27 HTTP en el backend (25 de los routers más `/` y `/api/health`), 2 WebSockets y 5 HTTP en el servicio de huella. El hilo de paho se arranca en `startup`.
6. **BD**:
   - MySQL `smartfactory` (lectura y escritura).
   - MySQL Optimus `mayaprin` (lectura).
   - SQL Server `entregasDiarias` (código comentado).
   - SQL construido con f-strings que solo escapan `'`.
   - Credenciales en texto plano en `db/conexion.py`, versionado en git.
7. **Integraciones**:
   - MQTT: suscripción a `{mac}-*`; publicación de inicio y paro en `{mac}-OP`.
   - Huella: `EnrollmentSample CS.exe` vía TCP 8888 (no incluido en el repo).
   - Firmware ESP: no incluido en el repo.
8. **Seguridad**:
   - Flags de escritura real en "1" por defecto.
   - Sin autenticación en el servidor; los roles solo existen en el frontend.
   - El backend confía en el `codigo_usuario` que envía el navegador.
9. **Git / pruebas**:
   - Un cambio sin commit en `services/marcajes_service.py:32` (`OR recursoalternativo`).
   - No hay tests, CI ni linters.
10. **Hipótesis críticas** (estado actualizado en la Fase 2: `2026-11-13-fase2-reglas-negocio.md` §12):
    - entorno de producción;
    - cierre no atómico;
    - validaciones que pasan ante un error de BD;
    - carreras en la apertura;
    - `publicar` que devuelve éxito falso;
    - sincronización que vacía la memoria;
    - cantidades negativas;
    - recursos sin filtrar por OT;
    - credenciales versionadas;
    - log de 658 MB sin rotación.
