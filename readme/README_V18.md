# SmartFactory Web v18 — Relevo operacional MT automático

Esta versión agrega el flujo de relevo para cierres `MT`:

```text
Operario A cierra como MT
↓
No se publica MQTT de paro
↓
Se inserta resumen MT y se limpia datossensados/marcajeactivo
↓
La interfaz queda en modo Relevo MT pendiente
↓
Operario B se identifica
↓
Sistema reutiliza OP, recurso y actividad
↓
Se abre nuevo marcaje real para Operario B
```

## Endpoint nuevo

```text
POST /api/marcajes/iniciar-relevo-mt-real
```

Payload:

```json
{
  "relevo": {
    "numOp": "49245",
    "recurso": "PEG CAJ5",
    "actividad": "B-ARR-L",
    "cantidad": "500000"
  },
  "codigo_usuario": "M1328"
}
```

## Validaciones esperadas

1. Cerrar marcaje como `MT`.
2. Confirmar que aparece panel `Relevo MT pendiente`.
3. Identificar al siguiente operario.
4. Presionar `Iniciar marcaje de relevo`.
5. Validar nuevo registro en `smartfactory.marcajeactivo`.
6. Validar que el sidebar muestre el nuevo marcaje.
7. Validar MQTT de inicio si `SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1` y MQTT está conectado.

## Variables para prueba completa

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH="1"
uvicorn main:app --host 127.0.0.1 --port 8000
```
