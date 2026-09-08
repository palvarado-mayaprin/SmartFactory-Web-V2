# SmartFactory v19.4 — Huella real estable y serialización segura

## Cambios

- Corrige referencia circular en `intentos`.
- El endpoint `/api/huella/identificar` devuelve solo JSON seguro.
- Mantiene bloqueo de lecturas simultáneas.
- Mantiene CORS para `http://127.0.0.1:8000`.
- Mantiene integración real con `EnrollmentSample CS.exe` por socket `127.0.0.1:8888`.

## Validación

1. Inicia FastAPI principal en `:8000`.
2. Inicia huella local en `:9001`.
3. Revisa:

```text
http://127.0.0.1:9001/api/huella/health
```

Debe mostrar `version: 19.4.0`.

4. Presiona **Identificar con huella** en la interfaz.
5. Debe devolver usuario real y continuar el flujo normal.

## Respuesta esperada

```json
{
  "ok": true,
  "modo": "REAL",
  "codigo_usuario": "M1476",
  "raw": "M1476,Nombre Usuario",
  "datos": ["M1476", "Nombre Usuario"],
  "mensaje": "Huella real leída correctamente desde EnrollmentSample CS.exe."
}
```
