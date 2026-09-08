# SmartFactory Web v15.1

Corrección sobre v15:

- Se elimina el cierre directo desde el sidebar.
- Tanto marcajes simulados como reales ahora usan el botón **Preparar cierre**.
- El sistema muestra el panel de selección de tipo de cierre antes de cualquier acción:
  - FINAL = Finalización de actividad
  - MD = Reporte parcial con máquina detenida
  - MT = Reporte parcial sin detener máquina
- Esta fase sigue siendo simulación: no borra BD, no inserta resumen y no publica MQTT real.

## Validación principal

1. Crear o sincronizar un marcaje activo.
2. En el sidebar presionar **Preparar cierre**.
3. Confirmar que se muestre el selector FINAL / MD / MT.
4. Seleccionar tipo, ingresar total usuario y presionar **Simular cierre**.
5. Validar SQL/MQTT preparado.
