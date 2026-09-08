# SmartFactory Web v20.6 - Confirmaciones Swal de seguridad

Versión basada en v20.5 flujo operacional directo.

## Cambios aplicados

- Se agregó confirmación Swal antes de iniciar un marcaje real después de seleccionar la actividad.
- Se agregó confirmación Swal antes de ejecutar el cierre real de un marcaje.
- Se mantiene eliminado el flujo de simulación.
- Se mantiene MQTT automático.
- Se mantiene visor de Eventos solo ADMIN.
- Se mantiene marcajes activos visible para todos.

## Comportamiento esperado

### Inicio

Huella → OP → actividad → Swal de confirmación → inicio real BD + MQTT inicio.

### Cierre

Huella con marcaje activo → selección FINAL/MD/MT → Swal de confirmación → cierre real.

