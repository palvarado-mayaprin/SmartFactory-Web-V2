# SmartFactory v19.2 — Huella real robusta con EnrollmentSample CS.exe

## Objetivo

Corregir la integración de huella real cuando `EnrollmentSample CS.exe` corta la conexión o deja de escuchar después del primer intento.

## Cambios principales

1. `health` ya **no abre una conexión TCP** al `.exe` para revisar si escucha. Ahora usa `netstat`, porque abrir una conexión de prueba podía consumir el socket del `.exe`.
2. El servicio local puede **cerrar y reabrir** `EnrollmentSample CS.exe` antes de cada lectura, imitando el flujo anterior de PyQt.
3. Se prueban variantes de comando:
   - `enrollFingerPrint`
   - `enrollFingerPrint\n`
   - `enrollFingerPrint\r\n`
4. Se agregan endpoints de diagnóstico:
   - `GET /api/huella/diagnostico`
   - `POST /api/huella/reiniciar-exe`
   - `POST /api/huella/probar-comando`

## Cómo ejecutar

Terminal 1:

```powershell
cd D:\VSCODE\SMARTFACTORY\src_web
.\venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd D:\VSCODE\SMARTFACTORY\src_web
.\venv\Scripts\Activate.ps1
uvicorn huella_local.main:app --host 127.0.0.1 --port 9001
```

## Validaciones

### 1. Diagnóstico

Abrir:

```text
http://127.0.0.1:9001/api/huella/health
```

Debe mostrar:

```json
"version": "19.2.0"
```

### 2. Reiniciar exe desde el servicio local

POST:

```text
http://127.0.0.1:9001/api/huella/reiniciar-exe
```

### 3. Probar comando

POST:

```text
http://127.0.0.1:9001/api/huella/probar-comando
```

Body opcional:

```json
{
  "comando": "enrollFingerPrint",
  "reiniciar_exe": true
}
```

### 4. Probar desde la interfaz

Presionar:

```text
Identificar con huella
```

El servicio intentará leer con las variantes de comando y devolverá los intentos si falla.

## Variable útil

Si deseas NO reiniciar el `.exe` antes de cada lectura:

```powershell
$env:SMARTFACTORY_HUELLA_REINICIAR_EXE_ANTES_LECTURA="0"
```

Por defecto está en `1`.
