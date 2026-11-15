# 07 — Identificación, biometría y roles

## 1. Servicio local de huella (`huella_local/main.py`) [C]

- Es un FastAPI independiente en `127.0.0.1:9001` (`iniciar_huella_local_piloto.bat`). CORS solo admite `127.0.0.1:8000` y `localhost:8000` (55-64).
- Se comunica por TCP con **`EnrollmentSample CS.exe`** en `127.0.0.1:8888`.
  - Ese `.exe` **no está en el repo** [?].
  - Se busca en `SMARTFACTORY_ENROLLMENT_EXE_PATH` o en `../src/servicios/Enrollment/bin/Debug/` y otras rutas relativas (`_obtener_ruta_exe` 137-155).
- Configuración: `SMARTFACTORY_HUELLA_*` (20-46).
  - En modo `SIMULACION` devuelve siempre el usuario de `SMARTFACTORY_HUELLA_USUARIO` (539-548).
  - Los `.bat` piloto fijan el modo `REAL`.

### Lectura (`identificar_huella` 517-568 → `_identificar_real` 377-427)

1. Lock global **no bloqueante**. Si hay una lectura en curso → `ok:false` ("Ya hay una lectura de huella en proceso en esta PC").
2. Por cada variante de comando (`enrollFingerPrint`, `+\n`, `+\r\n`):
   1. `_preparar_exe_para_lectura`: `taskkill /F` del `.exe` → espera 0,7 s → lo relanza → espera hasta 12×0,5 s a que el puerto aparezca en LISTENING (lo comprueba con `netstat`, sin abrir el socket).
   2. `_enviar_comando_socket` (332-374): conecta, envía, hace **un único `recv(4096)`** con timeout de 30 s.
   3. `_normalizar_respuesta` (307-329): `split(",")` → **el primer campo es `codigo_usuario`**; sustituye `?` por `ñ`.
3. Peor caso ≈ 3 × (0,7 + 6 + 30) s ≈ 110 s.
4. Se supone que el `.exe` es un servidor de "una sola lectura" (comentario 27-33) [I].

## 2. Identificación en el backend [C]

1. El navegador escribe el código recibido en `#codigoUsuario` y llama a `POST /api/usuario/identificar-prueba` (`app.js:82-107`, `131-237`).
2. `usuarios_service::identificar_usuario_prueba` (30-52): consulta Optimus `staf` con `staf_discontinued='0'`.
3. `consultar_marcaje_activo` (55-85): memoria primero, BD después (`marcajeactivo WHERE username=…`).

**Respuesta** (`usuarios_service.py:46-52`) [C]: `{code: staf_code, username: staf_name, resource: staf_resource}`. ⚠️ (E4, Fase 4) Aquí `usuario.username` es el **nombre**, mientras que en `marcajeactivo` y `resumenmarcajes` la columna `username` guarda el **código** (`staf_code`). La UI envía `usuarioActual.code` como `codigo_usuario`. Detalle en `02-base-de-datos.md` §3.

### Hechos de seguridad [C]

- **El backend no verifica que el código provenga de una huella.** Cualquier cliente puede enviar cualquier `codigo_usuario`. La identificación manual solo está oculta con CSS para quien no es ADMIN (`templates/index.html:104-108`).
- Si Optimus falla, el operario ve "Usuario no encontrado o descontinuado" (mensaje engañoso).
- No hay sesión ni token: el "usuario actual" es una variable JS.

## 3. Usuarios elevados (SU / ADMIN) [C]

- `POST /api/auth/usuario-elevado` → `auth_service::validar_usuario_elevado` (16-58).
  - `SELECT * FROM smartfactory.superusuarios WHERE username='…' AND password='…'`: **contraseña en claro**, SQL concatenado.
  - Tipo de usuario leído de `fila[8]`, es decir, **por posición**.
- Permisos que devuelve: `SU` → marcajes; `ADMIN` → marcajes, MQTT y admin.
- **Solo se aplican en el navegador** (`aplicarVisibilidadPorRol`, `app.js:1972-1987`). Recargar la página pierde el modo elevado.
- Capacidades en la UI:
  - **SU/ADMIN**: "Cierre SU/ADMIN" de cualquier marcaje sin huella.
  - **ADMIN**: identificación manual, panel MQTT (conectar/detener), log de eventos, "Identificar otro usuario".

## 4. Esperado, problemas y pendientes

- **Esperado** (texto de la UI): "Solo el dueño del marcaje podrá cerrarlo con huella" (`app.js:1548`). Se cumple en la UI; **no en la API** [C].
- **Problemas**: R-05 (sin autenticación ni autorización en el servidor), R-14 (credenciales), R-15 (SQL concatenado en el login), R-21 (no se registra quién cerró).
- **Recomendaciones (no aprobadas)**:
  - Firmar la identificación en el servicio de huella.
  - Sesión en el servidor.
  - Contraseñas con hash.
  - Usar `usuarioFinalizacion`.
- **Pendiente**: P-11 (procedimientos manuales y responsables).
