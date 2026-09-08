# SmartFactory Web v20.19

## Objetivo

Agregar trazabilidad diagnóstica para investigar los casos esporádicos en los que el cálculo de `cantidadreal` resulta negativo al cerrar un marcaje.

## Cambio implementado

Se agregó un log independiente en:

```text
logs/cantidadreal_negativos.log
```

El log se genera únicamente cuando:

```python
cantreal_calculada < 0
```

No se modifica la fórmula actual, no se corrige automáticamente el valor y no se bloquea el cierre.

## Información registrada

Cada alerta conserva:

- Fecha y hora del diagnóstico.
- Modalidad de cierre: FINAL, MD o MT.
- Diccionario completo del marcaje recibido.
- `numOp`, recurso, actividad, cantidad cotizada, username, topic, MAC y totalUsuario.
- `cantreal_original`.
- `suma_mt_anterior`.
- Fórmula exacta utilizada.
- `cantreal_calculada`.
- Tiempo inicial, tiempo final y duración obtenidos desde `datossensados`.
- Query original utilizada para calcular los datos de cierre.
- Todos los registros de `datossensados` de la misma OP + actividad + MAC.
- Query utilizada para sumar cierres MT anteriores.
- Todos los registros MT de `resumenmarcajes` considerados por la lógica vigente.
- `wo_number`, `tk_id` y query de Optimus utilizada para obtenerlos.

## Consideración de rendimiento

Las consultas diagnósticas adicionales (`SELECT *` de `datossensados` y `resumenmarcajes`) solamente se ejecutan cuando el cálculo ya resultó negativo. El flujo normal de cierres positivos no recibe estas consultas adicionales.

## Regla vigente observada

La suma de MT anteriores continúa filtrándose por:

```text
numOp + actividad + estado = MT
```

y no por recurso o MAC. Este comportamiento no fue modificado en v20.19; se documenta y se registra en el log para poder determinar con evidencia si participa en la causa raíz.

## Versionado

- FastAPI: `20.19.0`
- Interfaz: `v20.19`
