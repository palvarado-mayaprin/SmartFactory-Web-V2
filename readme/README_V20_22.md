# SmartFactory Web V2 - v20.22

## Nueva función: Pausa por actividad improductiva

Se agrega un botón visualmente diferenciado **PAUSA POR ACTIVIDAD IMPRODUCTIVA** en la interfaz de cierre posterior a la validación de huella.

### Flujo

1. El usuario debe ingresar obligatoriamente el total/cantidad realizada. El valor 0 es válido si fue ingresado explícitamente.
2. El botón ejecuta el mismo cierre real **MD** existente (reporte parcial con detenimiento de máquina).
3. Únicamente para cierres originados desde este botón, el INSERT del usuario en `smartfactory.resumenmarcajes` incluye `variable01 = 1`.
4. Un MD normal mantiene el INSERT histórico y omite `variable01`, conservando su DEFAULT `NULL`.
5. Solo después de un cierre MD exitoso se conserva temporalmente el usuario y recurso y se pregunta qué tiempo improductivo desea iniciar: COMIDA, MANTO, FALLA o CAMBIO.
6. Al seleccionar una opción se reutiliza `/api/marcajes/iniciar-improductivo`, incluyendo sus validaciones existentes y publicación MQTT. No se solicita nuevamente huella ni recurso.
7. Si el usuario cancela la selección, el cierre permanece válido, no se crea otro marcaje y la interfaz vuelve a la página principal.
8. Si el inicio improductivo falla, el cierre MD no se revierte y se informa al usuario.

### Cambios técnicos

- `templates/index.html`: nuevo botón y versión visual v20.22.
- `static/css/estilos.css`: estilo diferenciado del botón.
- `static/js/app.js`: flujo especial post-cierre e inicio automático del improductivo.
- `models/schemas.py`: campo opcional `pausa_improductiva` en el request de cierre.
- `api/marcajes_api.py`: propaga el indicador al servicio de cierres.
- `services/cierres_service.py`: valida que el indicador solo se use con MD y agrega `variable01 = 1` únicamente en ese INSERT.
- `main.py`: versión 20.22.0.

No se agregaron dependencias ni se modificaron las reglas existentes de FINAL, MD normal, MT, diagnóstico de cantidadreal, MQTT, huella o apertura de tiraje posterior a ARR.
