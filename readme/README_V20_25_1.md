# SmartFactory Web v20.25.1

## Elección de la parte de la orden con un select

Esta versión parte de v20.25.0 y solo cambia el diálogo «¿En qué parte de la orden trabaja?».

### Motivo

En la prueba en el navegador (2026-11-24), el diálogo de radios de v20.25.0 se deformaba con los estilos globales de `input` y `label`, y las opciones se salían del cuadro.

### Qué cambia para el operario

- La parte de la orden se elige en un **select**, como el de actividades no cotizadas. Muestra **solo la descripción** de cada OT (`wo_title2`), en el orden de la orden (`wo_seq`).
- El número de OT solo aparece si la OT no tiene descripción («OT n») o si dos OT candidatas comparten la misma descripción («descripción (OT n)»).
- «Continuar» exige elegir una opción. «Volver» cancela sin crear nada.
- **Parte** en la confirmación y en el aviso de éxito muestra solo la descripción.

### Cambios técnicos

- `static/js/resolucion_ot.js`: `textoOt` y `construirOpcionesOt`. Devuelve un `Map`, para no reordenar las OT, con las etiquetas escapadas.
- `static/js/app.js`: `elegirOtParaInicio` usa `input: "select"` con los estilos existentes `swal-actividad-popup` / `swal-actividad-select`. La fila «Parte» muestra solo la descripción.
- `main.py`: versión 20.25.1. `templates/index.html` sigue mostrando «v20.25».
- Pruebas: `tests/js/resolucion_ot.test.js`.

### Compatibilidad

Sin cambios en el backend, la base de datos ni el CSS, y sin migraciones. La API, la resolución de OT y los cierres son los de v20.25.0.

### Despliegue

Basta con actualizar `static/js` y `main.py`, y recargar la página en las PCs. La lista de comprobación en planta es la de `README_V20_25.md`, con la elección hecha en el select.
