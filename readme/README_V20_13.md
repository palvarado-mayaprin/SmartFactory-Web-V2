# SmartFactory Web v20.13

## Cambio principal

Se agregó el botón **Agregar actividad no cotizada** en la pantalla de selección de actividades.

## Comportamiento

- Después de buscar OP y seleccionar recurso, el usuario puede abrir un selector de actividades adicionales.
- El backend consulta `mayaprin.act` por recurso y excluye las actividades ya cotizadas en la OT.
- La actividad seleccionada se agrega visualmente a la lista.
- Al seleccionarla, se usa el mismo flujo operacional de inicio real de marcaje, con Swal de confirmación, MQTT inicio e INSERT en `marcajeactivo`.

## Archivos modificados

- `templates/index.html`
- `static/js/app.js`
- `static/css/estilos.css`
- `api/ordenes_api.py`
- `services/ordenes_service.py`
