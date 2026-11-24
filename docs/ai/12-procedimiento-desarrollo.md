# 12 — Procedimiento de desarrollo, autonomía y mantenimiento

## 0. Prioridad actual (desde 2026-11-13)

**Desarrollo de funcionalidades frontend y backend**:
- pantallas, formularios y UX;
- endpoints FastAPI y servicios Python;
- consultas MySQL;
- integración frontend/backend;
- validación y gestión de errores;
- pruebas específicas de lo desarrollado.

**Postergado**: simulador MQTT, emulación de ESP e infraestructura de pruebas con sensores (`06-mqtt-sensores.md` §0).
Evita refactorizaciones generales que el requisito no necesite.

## 1. Procedimiento obligatorio (10 pasos)

1. **Interpretar el requerimiento.**
   - Reformúlalo en una o dos frases: qué ve o hace el usuario y qué cambia en los datos.
   - Si hay ambigüedad que cambie la solución, pregunta. Si no, elige el valor por defecto obvio y decláralo.
2. **Consultar la documentación**: `CLAUDE.md`, el documento del área, `09-riesgos.md` y `10-decisiones-pendientes.md`. Comprueba si el requisito toca una P-xx abierta.
3. **Localizar código y dependencias.**
   - Grep de funciones, endpoints e IDs del DOM.
   - Traza UI (`app.js`/`index.html`) → endpoint (`api/`) → servicio → SQL/MQTT → memoria/WebSocket.
   - Lista los llamadores de lo que vayas a tocar.
   - Verifica que las referencias `archivo:línea` de la documentación siguen siendo válidas.
4. **Evaluar impacto y riesgos.** Clasifica con la matriz de §2. Identifica efectos sobre:
   - cantidades;
   - el orden de efectos (`04-flujos-marcajes.md` §0);
   - payloads MQTT;
   - `resumenmarcajes`;
   - varios backends (P-02).
5. **Diseñar una solución simple y compatible.**
   - Reutiliza los patrones existentes (§3).
   - Para lo nuevo, mejor añadir que modificar.
   - No cambies firmas, contratos JSON, IDs del DOM ni textos de error que la UI interpreta sin una razón explícita.
6. **Implementar solo lo necesario.** Sin limpiezas ajenas al requisito. No modifiques ni reviertas el `OR recursoalternativo` de `services/marcajes_service.py:32` (P-09).
7. **Ejecutar las pruebas pertinentes.**
   - `.venv-test\Scripts\python.exe -m pytest`, con pruebas nuevas según `11-pruebas.md` §6.
   - `py_compile` de los archivos tocados.
8. **Revisar el diff y las regresiones.**
   - Comprueba con `git -c safe.directory=… diff` que solo cambiaron los archivos previstos, que no aparecen credenciales y que no hay `print` de depuración.
   - Revisa los contratos de la UI.
9. **Actualizar la documentación** del área, más §0 de flujos si cambió el orden de efectos y el estado de R/P/M. `test_docs_referencias` debe pasar.
10. **Entregar un resumen técnico**:
    - qué cambió (archivos);
    - por qué;
    - cómo se validó (pruebas y resultado);
    - qué **no** se validó (p. ej. "sin prueba en planta", "sin BD real");
    - riesgos residuales;
    - pasos manuales que necesite el usuario.

## 2. Autonomía y autorizaciones

| Puedes hacerlo sin preguntar (dentro del requisito aprobado) | Requiere autorización explícita |
|---|---|
| Crear y modificar archivos en `api/`, `services/`, `models/`, `realtime/`, `static/`, `templates/`, `tests/`, `docs/ai/`, `CLAUDE.md` | **Escrituras en producción** (cualquier ejecución que conecte a MySQL, Optimus, SQL Server o MQTT reales) |
| Nuevos endpoints, servicios, pantallas y consultas SQL (parametrizadas) | **Cambios de esquema** productivos y **migraciones** |
| Ejecutar pytest en `.venv-test` y `py_compile` | **Cambios que afecten a MQTT o sensores**: payloads, `publicar`, `_on_message`, persistencia DATOS, suscripciones |
| Corregir errores que introdujo tu propia implementación | **Cálculo de cantidades o tiempos** (`cierres_service.py`), y cualquier corrección de los defectos R-xx que cambie resultados de negocio |
| Leer código, logs (sin copiarlos fuera) y documentación | **Operaciones destructivas** (borrar archivos versionados, `git reset`/`checkout` de cambios ajenos) |
| | **Credenciales y conexiones**: `db/conexion.py`, `config.py`, `.env*`, `.bat` |
| | **Arrancar** el backend o el servicio de huella; **instalar** paquetes |
| | **Despliegues** productivos |
| | **Commits y pushes**, salvo autorización expresa para la tarea |

`.claude/settings.json` refleja esta matriz como permisos (`allow`/`ask`/`deny`). Ante la duda, pregunta.

## 3. Estrategia frontend/backend

### Backend (FastAPI)

- **Endpoint**: en el router del área (`api/*_api.py`) o en uno nuevo registrado en `main.py` (`include_router`; tocar `main.py` pide confirmación).
  - Entrada con un modelo Pydantic en `models/schemas.py`, nunca `dict` libre.
- **Servicio**: en `services/`. Devuelve `{"ok": bool, "mensaje": str, "modo"?: str, ...}`.
  - El endpoint traduce: un error operativo da **409** con `detail=resultado` (como `api/marcajes_api.py`); una validación de entrada da **400** o **422**.
  - La UI lee `detail.mensaje` (`app.js::postJson`).
- **Estado de marcajes**: si se modifica, actualiza la memoria (`marcajes_estado_service`) y emite `MARCAGES_ACTIVOS_ACTUALIZADOS` por `realtime.websocket_manager.manager`.
- **SQL en funcionalidades nuevas**:
  - Optimus (lectura): `dtbOptimus1(query, params)` con `%s`.
  - SmartFactory: `dtbSmartFactory` **no admite parámetros**. La primera funcionalidad que necesite SQL parametrizado contra SmartFactory requiere crear `db/consultas.py` (diseño en `13-entorno-desarrollo-bd.md` §3.3). Es código nuevo en `db/` y **pide autorización**.
  - Hasta entonces, no concatenes valores del usuario en SQL nuevo.
- **Errores**: no repitas `if not resultado` para distinguir "sin filas" de "error" en código nuevo (R-03).
- **Escrituras nuevas**: respeta `ENABLE_REAL_DB_WRITES` como los servicios existentes (modo `PROTEGIDO`) y deja log de auditoría.

### Frontend

- `static/js/app.js` es un script global sin módulos.
  - Para cambios pequeños, añade funciones siguiendo el estilo existente.
  - Para una pantalla nueva y grande, crea `static/js/<funcionalidad>.js` y cárgalo en `templates/index.html` **después** de `app.js`. Reutiliza `postJson`, `log`, `activarPaso`, `Swal` y los globales de estado.
- Expón en `window` las funciones que se llamen desde `onclick` (patrón `app.js:1985-2149`).
- Paneles con la clase `card`/`hidden`. Para la visibilidad por rol, usa `admin-only` / `su-admin-only` + `permission-hidden`.
  - **Esto solo oculta**: cualquier permiso real debe validarse en el backend.
- **En código nuevo, escapa los datos** antes de interpolarlos en `innerHTML` (o usa `textContent`) (R-27).
- Estilos en `static/css/estilos.css`, reutilizando las clases existentes.
- Lógica pura (validaciones, formatos): en un archivo sin efectos al cargar, para poder probarla con `node --test` (`11-pruebas.md` §6).
- **Versión**: si es una versión entregable, `readme/README_V{n}.md` + versión en `main.py` (2 sitios) y `templates/index.html` (pide confirmación).

## 4. Restricciones permanentes

- No arrancar servicios ni conectar a sistemas reales sin autorización (R-25).
- No editar el histórico: `logs/`, `cambios_*.diff`, `resumen_cambios.txt`. Lo existente en `readme/` y `docs/ai/auditoria/` solo se amplía con archivos nuevos.
- No copiar credenciales, hosts ni datos de logs fuera de la máquina.
- No cambiar la configuración global de git.

## 5. Mantenimiento de `docs/ai`

- Cada cambio de comportamiento actualiza:
  - el documento del área;
  - §0 de `04-flujos-marcajes.md`, si cambia el orden de efectos;
  - el estado en `09-riesgos.md` y `10-decisiones-pendientes.md`.
- No subas [I] o [?] a [C] sin evidencia citada.
- Las respuestas humanas se anotan en `10-decisiones-pendientes.md` con fecha y responsable.
- Referencias: `archivo:línea` cuando sea estable; si no, `archivo::función`. `tests/test_docs_referencias.py` falla si alguna apunta a algo inexistente. Revisa a mano que siga señalando lo correcto.
- `docs/ai/auditoria/` es histórico: no se edita; se añaden archivos fechados.
- `CLAUDE.md` se mantiene corto; el detalle va en `docs/ai/`.
