# SmartFactory v19.1 — Huella real por EnrollmentSample CS.exe

Esta versión reemplaza la simulación del servicio local de huella por comunicación real con:

```text
src\servicios\Enrollment\bin\Debug\EnrollmentSample CS.exe
```

El servicio local `huella_local` se comunica por socket TCP con:

```text
127.0.0.1:8888
```

y envía el comando:

```text
enrollFingerPrint
```

## Ejecutar

Terminal 1 — backend principal:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — servicio local de huella:

```powershell
uvicorn huella_local.main:app --host 127.0.0.1 --port 9001
```

## Validar health

Abrir:

```text
http://127.0.0.1:9001/api/huella/health
```

Debe mostrar:

```json
"modo": "REAL"
```

Si no encuentra el exe, configura:

```powershell
$env:SMARTFACTORY_ENROLLMENT_EXE_PATH="D:\VSCODE\SMARTFACTORY\src\servicios\Enrollment\bin\Debug\EnrollmentSample CS.exe"
```

## Volver a modo simulación

```powershell
$env:SMARTFACTORY_HUELLA_MODO="SIMULACION"
$env:SMARTFACTORY_HUELLA_USUARIO="M1328"
uvicorn huella_local.main:app --host 127.0.0.1 --port 9001
```

## Qué validar

1. El servicio local responde `/api/huella/health`.
2. `socket_escuchando` aparece en `true` si `EnrollmentSample CS.exe` ya está abierto.
3. Si el exe no está abierto, el servicio intenta abrirlo automáticamente.
4. Al presionar “Identificar con huella”, el frontend llama a `:9001/api/huella/identificar`.
5. El servicio envía `enrollFingerPrint` a `localhost:8888`.
6. El servicio devuelve `codigo_usuario`.
7. El backend principal valida el usuario y continúa el flujo normal.

## Notas

La respuesta cruda del exe se devuelve en:

```json
"raw"
```

y la lista separada por comas se devuelve en:

```json
"datos"
```
