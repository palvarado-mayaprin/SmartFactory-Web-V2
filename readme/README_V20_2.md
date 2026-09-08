# SmartFactory Web v20.2 — Validación de usuarios elevados

Esta versión agrega la primera fase de limpieza del frontend para permisos elevados.

## Agregado

- Botón **Opciones avanzadas**.
- Login con SweetAlert2 para usuario/contraseña.
- Endpoint `POST /api/auth/usuario-elevado`.
- Consulta contra `smartfactory.superusuarios`.
- Soporte inicial para tipos:
  - `ADMIN`
  - `SU`
  - `NO`
- Panel visual de modo elevado activo.

## Importante

Esta versión solo valida credenciales y guarda el tipo de usuario elevado en frontend.
Todavía no oculta ni muestra módulos específicos. Eso se trabajará en la siguiente fase.

## Validaciones

1. Presionar **Opciones avanzadas**.
2. Ingresar usuario/contraseña inválidos.
   - Debe mostrar Swal de error.
3. Ingresar usuario tipo `SU`.
   - Debe mostrar acceso soporte.
4. Ingresar usuario tipo `ADMIN`.
   - Debe mostrar acceso administrador.
5. Presionar **Salir modo elevado**.
   - Debe limpiar el estado elevado.
