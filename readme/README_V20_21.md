# SmartFactory Web v20.21

## Apertura opcional de tiraje después de cierre FINAL de arreglo

Esta versión agrega un flujo de conveniencia para actividades cuyo **código** contiene la secuencia `ARR` en cualquier posición, sin importar mayúsculas/minúsculas.

### Regla de activación

El nuevo flujo se ejecuta únicamente cuando:

1. el tipo de cierre es `FINAL`;
2. el cierre real terminó correctamente; y
3. el código de actividad cerrada cumple una condición equivalente a `actividad.toUpperCase().includes("ARR")`.

No aplica a cierres `MT` ni `MD`.

### Flujo

Después del mensaje normal de cierre exitoso, si la actividad es un arreglo, se pregunta:

> ¿Desea aperturar tiraje de esta misma orden?

- **No:** el flujo termina normalmente.
- **Sí:** se conservan temporalmente únicamente el usuario, la OP y el recurso del marcaje cerrado. La información de la OP se consulta nuevamente mediante `/api/op/buscar`, se valida que el recurso heredado continúe disponible y se consultan sus actividades mediante `/api/actividades/recurso`.

Se reutiliza la interfaz normal del paso 3 (`cardActividad`, `prepararRecursos`, `renderActividades` y `seleccionarActividad`). El nuevo marcaje no se crea hasta que el usuario selecciona y confirma una actividad mediante el flujo existente.

### Datos que NO se heredan

No se copian directamente actividad anterior, MAC, topic, conteos MQTT, cantidadreal, tiempos ni estados del marcaje finalizado.

### Manejo de errores

Si el recurso heredado ya no está disponible, la OP no puede recuperarse o falla la consulta de actividades, el cierre FINAL permanece válido y no se crea ningún marcaje parcial. El usuario queda en el flujo normal de búsqueda de OP para continuar manualmente.

### Alcance técnico

- Modificado: `static/js/app.js`
- Versionado: `main.py`, `templates/index.html`
- Sin cambios en endpoints/backend de cierres.
- Sin dependencias nuevas.
- Sin cambios de esquema de base de datos.
