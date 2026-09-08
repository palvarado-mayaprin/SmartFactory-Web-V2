# SmartFactory v19.3 — Huella real estabilizada

## Objetivo

Estabilizar el endpoint local:

```text
POST /api/huella/identificar
```

para que la lectura real desde `EnrollmentSample CS.exe` devuelva siempre JSON válido al frontend.

## Cambios

- Versión del servicio local: `19.3.0`.
- Se agrega lock global para evitar lecturas simultáneas del lector.
- Se normaliza la respuesta de `_identificar_real()` a tipos simples serializables por JSON.
- Se evita que FastAPI falle con `jsonable_encoder` cuando la respuesta interna trae objetos no serializables.
- Se mantiene un campo `detalle` con diagnóstico, pero convertido a strings/listas/dicts seguros.

## Validación

1. Levantar FastAPI principal:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```

2. Levantar servicio local:

```powershell
uvicorn huella_local.main:app --host 127.0.0.1 --port 9001
```

3. Validar health:

```text
http://127.0.0.1:9001/api/huella/health
```

Debe mostrar:

```text
version: 19.3.0
```

4. Presionar `Identificar con huella` desde la interfaz.

Debe devolver algo similar:

```json
{
  "ok": true,
  "modo": "REAL",
  "codigo_usuario": "M1328",
  "raw": "M1328,...",
  "datos": ["M1328", "..."],
  "mensaje": "Huella real leída correctamente desde EnrollmentSample CS.exe."
}
```

## Nota

Si el lector queda ocupado, el servicio responde:

```text
Ya hay una lectura de huella en proceso en esta PC.
```
