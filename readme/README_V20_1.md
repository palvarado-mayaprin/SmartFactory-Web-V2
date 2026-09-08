# SmartFactory v20.1 — SweetAlert en identificación de usuario

Esta versión mantiene la lógica operativa de v20 y reintegra alertas SweetAlert2 en el flujo de identificación.

## Cambios

- Al identificar usuario válido sin marcaje activo:
  - muestra: `Bienvenido/a <usuario>, por favor ingresa orden a trabajar`.
- Al identificar usuario con marcaje activo:
  - muestra aviso para cierre de actividad.
- Al identificar usuario con relevo MT pendiente:
  - muestra aviso para continuar relevo.
- Si el backend responde `Usuario no encontrado o descontinuado`:
  - muestra Swal de error con ese mensaje.
- Se agregó CDN de SweetAlert2 en `templates/index.html`.

## Validación

1. Identificar usuario válido por huella real.
2. Validar que aparezca el Swal de bienvenida.
3. Probar usuario inexistente o descontinuado.
4. Validar que aparezca el Swal de error.
