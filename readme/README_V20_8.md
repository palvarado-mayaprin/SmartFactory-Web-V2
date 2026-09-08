# SmartFactory Web v20.8

## Cambio principal

Se separó el cierre de marcajes activos en dos apartados operativos:

1. **Cierre general**
   - Visible para cualquier usuario.
   - El botón **Preparar cierre** solicita lectura de huella.
   - El cierre solo continúa si la huella corresponde al dueño del marcaje activo.
   - Técnicamente reutiliza el mismo flujo de `identificarConHuellaLocal()`.

2. **Cierre SU / ADMIN**
   - Visible únicamente para usuarios elevados `SU` y `ADMIN`.
   - Conserva el flujo anterior: seleccionar un marcaje activo desde el listado y preparar su cierre directamente.
   - Pensado para casos donde el operario abandona turno o no puede cerrar su marcaje.

## Se mantiene

- MQTT automático.
- Eventos solo ADMIN.
- Marcajes activos visibles para todos.
- Confirmación Swal antes de iniciar y cerrar marcajes.
- FINAL/MD con MQTT stop obligatorio.
- MT orientado a continuidad operacional y relevo.
