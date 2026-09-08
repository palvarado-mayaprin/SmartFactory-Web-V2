# SmartFactory Web v9 - Persistencia real preparada

## Objetivo de esta fase

Esta fase prepara la persistencia real de marcajes en `smartfactory.marcajeactivo`, manteniendo el conteo MQTT en memoria.

Incluye:

- Sincronizar marcajes abiertos desde BD.
- Preparar apertura real de marcaje en BD.
- Preparar cierre real de marcaje en BD.
- Mantener WebSockets y MQTT funcionando.
- Proteger INSERT/DELETE reales con variable de entorno.

## Seguridad

Por defecto, la escritura real está deshabilitada.

El sistema corre en modo protegido si no existe esta variable:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
```

En modo protegido:

- NO ejecuta INSERT real.
- NO ejecuta DELETE real.
- Sí muestra el SQL que se ejecutaría.
- Sí permite seguir validando UI/API/flujo.

## Cómo activar escritura real en una prueba controlada

PowerShell:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

CMD:

```cmd
set SMARTFACTORY_ENABLE_REAL_DB_WRITES=1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Para volver a modo protegido, cierre la terminal y vuelva a iniciar sin la variable.

## Endpoints agregados

- `GET /api/marcajes/modo-persistencia`
- `POST /api/marcajes/iniciar-real-bd`
- `POST /api/marcajes/cerrar-real-bd`
- `GET /api/marcajes/activos-bd`
- `POST /api/marcajes/sincronizar-desde-bd`

## Qué validar primero

1. Ejecutar sin activar la variable de entorno.
2. Confirmar que la UI muestra `Modo protegido`.
3. Generar una simulación.
4. Presionar `Iniciar marcaje REAL BD`.
5. Confirmar que NO inserta y muestra advertencia de modo protegido.
6. Presionar `Sincronizar BD`.
7. Confirmar que carga marcajes existentes de `smartfactory.marcajeactivo`.

Luego, en prueba controlada:

1. Activar `SMARTFACTORY_ENABLE_REAL_DB_WRITES=1`.
2. Reiniciar uvicorn.
3. Verificar que la UI muestra `BD real habilitada`.
4. Iniciar marcaje real.
5. Revisar en MySQL que el registro aparece en `smartfactory.marcajeactivo`.
6. Sincronizar BD.
7. Cerrar marcaje real.
8. Revisar en MySQL que el registro fue eliminado.
