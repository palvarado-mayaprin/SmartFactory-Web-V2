# SmartFactory Web v20.10 - cierre finalizado para despliegue operativo

Cambios incluidos sobre v20.9:

1. El botón **Identificar otro usuario** dentro del flujo de cierre queda visible únicamente para ADMIN.
2. Usuarios normales mantienen el flujo operativo por huella y el botón global Cancelar.
3. Se conserva el cierre general por huella, cierre elevado SU/ADMIN, MQTT automático y frontend corporativo Mayaprin.

## Validación rápida

- Usuario normal: no debe ver **Identificar manual** ni **Identificar otro usuario**.
- ADMIN: debe ver **Identificar manual**, **Identificar otro usuario**, Eventos y controles MQTT.
- SU: conserva el cierre elevado de marcajes activos según la lógica existente.
- Marcajes activos siguen visibles para todos.
