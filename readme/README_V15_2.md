# SmartFactory Web v15.2

Corrección de simulación de cierre:

- El panel de simulación se renderiza de forma más robusta.
- Se agrega `console.log` con la respuesta del endpoint `/api/marcajes/simular-cierre`.
- Se optimizan las lecturas a `datossensados` para obtener cantidad, inicio, final y duración en una sola consulta.
- Sigue sin ejecutar INSERT, DELETE ni publicación MQTT real.

Validación principal:

1. Identificar usuario con marcaje activo.
2. Seleccionar FINAL, MD o MT.
3. Presionar Simular cierre.
4. Debe aparecer el panel con MQTT, SQL y valores calculados.
