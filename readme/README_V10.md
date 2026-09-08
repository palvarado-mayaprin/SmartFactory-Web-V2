# SmartFactory Web v10 - Marcajes reales controlados

Esta versión prepara la activación real de marcajes en `smartfactory.marcajeactivo` con más protección que v9.

## Qué agrega v10

- Validación antes de INSERT real:
  - bloquea si el usuario ya tiene marcaje activo,
  - bloquea si el recurso/topic ya tiene marcaje activo,
  - valida campos críticos vacíos.
- Cierre real más seguro:
  - valida que el marcaje exista antes de borrar,
  - usa condición compuesta con `username`, `numOp`, `recurso`, `actividad` y `topic` cuando existe.
- Logs locales:
  - `logs/marcajes_reales.log`
- Modo protegido sigue activo por defecto.

## Modo protegido

Por defecto NO ejecuta INSERT/DELETE real.

Para probar sin escribir:

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Activar escritura real

Solo para prueba controlada:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

En CMD:

```cmd
set SMARTFACTORY_ENABLE_REAL_DB_WRITES=1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Qué validar

1. Que en modo protegido indique que no escribe.
2. Que si el usuario ya tiene marcaje activo, bloquee apertura.
3. Que si la máquina/recurso ya tiene marcaje activo, bloquee apertura.
4. Que con escritura real habilitada inserte un marcaje real.
5. Que al sincronizar desde BD se vea el marcaje real.
6. Que al reiniciar backend y sincronizar desde BD vuelva a aparecer.
7. Que el cierre real elimine únicamente el marcaje seleccionado.

## Importante

MQTT sigue en memoria. Esta versión todavía NO guarda producción MQTT definitiva en BD.
