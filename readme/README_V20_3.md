# SmartFactory Web v20.3 - Visibilidad por roles

Esta versión agrega control visual por permisos sin modificar la lógica operativa validada.

## Reglas

- Marcajes activos: visibles siempre para todos los usuarios.
- Usuario normal: operación normal + marcajes activos.
- SU: operación normal + marcajes activos + herramientas soporte.
- ADMIN: operación normal + marcajes activos + herramientas soporte + MQTT + administración.

## Validaciones

1. Entrar sin usuario elevado: debe verse operación normal y marcajes activos.
2. Validar usuario SU: debe mostrarse panel soporte, pero no panel MQTT/admin.
3. Validar usuario ADMIN: debe mostrarse MQTT, soporte y administración.
4. Salir modo elevado: debe ocultar opciones SU/ADMIN y mantener marcajes activos visibles.
