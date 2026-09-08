# SmartFactory Web v20.9 · Front productivo corporativo

Cambios incluidos:

- Botón flotante **Cancelar** para refrescar la página y reiniciar el flujo operativo.
- Se ocultó/eliminó visualmente el estado técnico `modoPersistenciaEstado`.
- Encabezado reconstruido con imagen corporativa de Mayaprin.
- Se agregó logo de Mayaprin en `static/img/logo_mayaprin.png`.
- La identificación manual quedó restringida a usuarios **ADMIN**.
- Se mantiene el flujo v20.8: cierre general por huella y cierre elevado para SU/ADMIN.

Nota operacional:

El botón Cancelar limpia el estado visible del frontend mediante recarga de página. No modifica base de datos, MQTT ni marcajes activos.
