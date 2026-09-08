# SmartFactory v16 — Apertura real completa con MQTT de inicio

## Objetivo

Esta versión corrige el punto crítico de apertura: después de insertar el marcaje real en `smartfactory.marcajeactivo`, el backend puede publicar el mensaje MQTT de inicio al ESP para que el tiraje realmente cambie a la OP/actividad seleccionada.

## Seguridad

Hay dos variables separadas:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH="1"
```

- `SMARTFACTORY_ENABLE_REAL_DB_WRITES=1`: permite INSERT/DELETE reales de marcajes.
- `SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1`: permite publicar mensajes MQTT reales hacia el ESP.

## Importante

Para que el publish funcione, primero debes presionar **Conectar MQTT** en la interfaz. El publish usa la conexión MQTT viva del backend.

## Qué validar

1. Iniciar FastAPI con ambas variables activas.
2. Abrir interfaz y presionar **Conectar MQTT**.
3. Identificar usuario.
4. Buscar OP.
5. Seleccionar actividad.
6. Simular inicio y revisar topic/payload.
7. Presionar **Iniciar marcaje real BD**.
8. Validar que:
   - se inserte en `marcajeactivo`,
   - se publique MQTT de inicio,
   - el ESP empiece a enviar `DATOS` con la OP/actividad nueva,
   - `mensajes_mqtt` y `datossensados` reciban esos datos.

## Ejecución recomendada

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES="1"
uvicorn main:app --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
uvicorn huella_local.main:app --host 127.0.0.1 --port 9001
```
