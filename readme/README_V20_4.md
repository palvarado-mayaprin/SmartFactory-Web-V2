# SmartFactory Web · v20.4

Versión basada en `v20.3_visibilidad_por_roles`.

## Cambios incluidos

1. **MQTT automático al iniciar backend**
   - El backend FastAPI inicia `mqtt_monitor.iniciar()` en el evento `startup`.
   - El botón `Conectar MQTT` se mantiene como herramienta de administración/debug, pero ya no es necesario para el flujo normal.
   - Si el broker MQTT no responde, el backend no se cae; el error queda disponible en el estado MQTT.

2. **Apagado ordenado de MQTT**
   - El backend ejecuta `mqtt_monitor.detener()` en el evento `shutdown`.

3. **Eventos solo para administradores**
   - El visor `Eventos` ahora usa las clases `admin-only permission-hidden`.
   - Los marcajes activos continúan visibles para todos los usuarios.

## Archivos modificados

- `main.py`
- `templates/index.html`

## Nota técnica

No fue necesario reemplazar `loop_forever()` por `loop_start()` porque esta versión ya utilizaba `loop_start()` dentro de `services/mqtt_service.py`.
