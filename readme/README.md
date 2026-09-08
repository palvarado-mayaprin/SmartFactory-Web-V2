# SmartFactory Web - Fase v8

Esta fase agrega asociación en vivo entre mensajes MQTT reales y marcajes activos simulados.

## Qué hace

- Mantiene FastAPI principal.
- Mantiene servicio local de huella simulado.
- Mantiene WebSockets para marcajes activos.
- Mantiene MQTT real en modo lectura.
- Al recibir un topic `MAC-DATOS`, busca un marcaje activo simulado con la misma MAC.
- Si encuentra marcaje, actualiza en memoria:
  - conteo MQTT actual,
  - delta del último mensaje,
  - cantidad de mensajes asociados,
  - último payload,
  - última fecha MQTT.
- Notifica a todas las pantallas por WebSocket.

## Qué NO hace todavía

- No inserta en base de datos.
- No publica mensajes MQTT.
- No cierra marcajes reales.
- No guarda producción definitiva.

## Ejecución

Terminal 1:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
uvicorn huella_local.main:app --reload --host 127.0.0.1 --port 9001
```

## Validación recomendada

1. Identificar usuario.
2. Buscar OP.
3. Seleccionar actividad.
4. Agregar a marcajes activos simulados.
5. Conectar MQTT.
6. Esperar mensajes `MAC-DATOS` de la misma máquina/MAC.
7. Validar que el sidebar actualice conteo y mensajes asociados sin refrescar.
