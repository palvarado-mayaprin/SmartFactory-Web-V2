# SmartFactory Web v20.7 - Recurso completo en confirmación de inicio

Versión basada en v20.6.

## Cambio aplicado

En el Swal de confirmación de inicio de marcaje, el campo **Recurso** ahora muestra el texto completo visible del selector de recursos.

Antes:

```text
Recurso: PEG CAJ5
```

Ahora:

```text
Recurso: PEG CAJ5 - Pegadoras de Cajas BestFold
```

## Nota técnica

El backend sigue recibiendo el código interno del recurso (`PEG CAJ5`) para mantener compatibilidad con BD/MQTT. El cambio es únicamente visual en el Swal para mejorar validación operacional del operario.
