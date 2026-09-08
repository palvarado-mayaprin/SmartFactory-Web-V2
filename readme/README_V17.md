# SmartFactory v17 — Cierre real controlado con 3 rutas

Incluye ejecución real de cierre para:

- FINAL: resumen usuario + resumen SMARTFACTORY estado F + delete datossensados + delete marcajeactivo + MQTT paro.
- MD: resumen usuario estado MD + delete datossensados + delete marcajeactivo + MQTT paro.
- MT: resumen usuario estado MT + delete datossensados + delete marcajeactivo + NO publica MQTT paro.

Variables requeridas para ejecutar real:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES="1"
$env:SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH="1"
uvicorn main:app --host 127.0.0.1 --port 8000
```

Notas:

- FINAL/MD no ejecutan cambios si MQTT publish real no está habilitado.
- MT no requiere MQTT publish porque la máquina continúa trabajando.
- Se recomienda simular cierre antes de ejecutar cierre real.
