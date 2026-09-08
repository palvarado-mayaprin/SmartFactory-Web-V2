# SmartFactory Web v15 - Simulación de cierre con 3 rutas operativas

Esta fase agrega el flujo correcto de cierre de marcaje antes de ejecutar cambios reales.

## Tipos de cierre

1. `FINAL` - Finalización de actividad.
   - Publicaría MQTT de finalización.
   - Prepararía resumen del usuario.
   - Prepararía resumen final `SMARTFACTORY` con estado `F`.
   - Prepararía `DELETE datossensados`.
   - Prepararía `DELETE marcajeactivo`.

2. `MD` - Reporte parcial con detenimiento de máquina.
   - Publicaría MQTT de finalización/detención.
   - Prepararía resumen del usuario con estado `MD`.
   - Prepararía `DELETE datossensados`.
   - Prepararía `DELETE marcajeactivo`.

3. `MT` - Reporte parcial sin detenimiento de máquina.
   - NO publicaría MQTT de paro.
   - Prepararía resumen del usuario con estado `MT`.
   - Prepararía `DELETE datossensados`.
   - Prepararía `DELETE marcajeactivo`.
   - El frontend debe continuar con identificación del siguiente operario.

## Endpoint nuevo

```text
POST /api/marcajes/simular-cierre
```

Payload:

```json
{
  "marcaje": {},
  "tipo_cierre": "FINAL",
  "total_usuario": 100
}
```

## Seguridad

v15 no ejecuta INSERT, DELETE ni publicación MQTT. Solo arma los textos SQL/MQTT y calcula valores para revisión.
