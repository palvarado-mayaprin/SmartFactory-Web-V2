# 05 — Cálculo de cantidades y tiempos (`cantidadreal`)

> Zona de **máximo riesgo**. Cualquier cambio altera la producción que se reporta y, probablemente, lo que se exporta al ERP (P-05). **No cambies la fórmula sin una decisión aprobada** (P-04).

## 1. Fórmula actual [C]

Se calcula en `services/cierres_service.py::simular_cierre_marcaje` (499-508). La consulta principal está en `_obtener_datos_cierre_datossensados` (167-216) y la suma de MT en `_obtener_suma_mt_anterior` (310-321):

```
cantreal_original = cantpliegos de la ÚLTIMA fila de datossensados
                    WHERE numOp=? AND actividad=? [AND mac=?]  ORDER BY fechatiempo DESC LIMIT 1
                    → 0 si no hay filas
suma_mt_anterior  = SUM(cantidadreal) FROM resumenmarcajes
                    WHERE numOp=? AND actividad=? AND estado='MT'
                    ← SIN filtro de recurso, MAC, usuario, fecha ni sesión
cantidadreal      = cantreal_original − suma_mt_anterior      ← sin límite inferior (puede ser < 0)
tiempoinicio      = MIN(fechatiempo)  (mismo filtro que cantreal)  → hora del servidor si no hay filas
tiempofinal       = MAX(fechatiempo)                               → hora del servidor si no hay filas
duracion          = TIMESTAMPDIFF(MINUTE, MIN, MAX)                → 0 si no hay filas
```

- `mac` sale del objeto marcaje (`marcaje.mac` o la parte del `topic` antes del guion).
- Si `cantidadreal < 0`, se escribe en `logs/cantidadreal_negativos.log` un diagnóstico completo (`_obtener_diagnostico_cantidadreal_negativa` 324-410). **El cierre continúa sin cambios**: el valor negativo se guarda (README_V20_20) [C].

**Agregado FINAL** (`ejecutar_cierre_marcaje_real` 815-861) [C]:
```
SUM(cantidadreal), MIN(tiempoinicio), MAX(tiempofinal), SUM(duracion)
FROM resumenmarcajes WHERE actividad=? AND numOp=?
```
Se calcula **después** de insertar la fila del usuario. No filtra por `estado`, así que **incluye las filas `F` anteriores**, ni por recurso ni por fecha.

**Si el SELECT del agregado falla** (`None`) [C] (E2, Fase 4): la rama `else` (`cierres_service.py:830-834`) usa los valores del operario actual (`cantreal_calculada`, sus tiempos y su duración) y **la fila `F` se inserta igualmente**, sin aviso. La fila `F` representa entonces solo el último cierre, no el agregado de la actividad.

### Errores de MySQL durante el cálculo [C] (E1, Fase 4)

Las lecturas del cálculo usan `dtbSmartFactory`, que devuelve `None` ante `mysql.connector.Error` (`02-base-de-datos.md` §1). Los helpers convierten ese `None` en valores por defecto **sin avisar**, y el cierre continúa con las escrituras:

| Lectura que falla | Helper | Valor que se usa | Efecto en `cantidadreal` |
|---|---|---|---|
| Última lectura de `datossensados` | `_obtener_datos_cierre_datossensados` (`if not resultado`, 197) | `cantreal=0`, tiempos = hora del servidor, duración 0 | `0 − MT` → **0 o negativo** |
| Suma de MT | `_obtener_suma_mt_anterior` → `_consulta_un_valor(…, 0)` (157-164) | `suma_mt_anterior=0` | Sin resta → **sobrevalorado** si había MT |
| Agregado FINAL | Rama `else` (830-834) | Valores del operario actual | Fila `F` incorrecta (ver arriba) |

- En ningún caso se distingue el error de "sin filas" (R-03), ni se informa en la respuesta HTTP.
- La lectura de Optimus (`_obtener_wo_tk`) se comporta distinto: `dtbOptimus` **lanza** la excepción y el cierre termina en HTTP 500 sin escribir nada (R-28).

**Lo que NO interviene** [C]:
- `totalUsuario` (cantidad manual): solo se guarda.
- `pliegosIncorrectos` (v20.24, pliegos rechazados declarados): solo se guarda. **No se resta** de `totalUsuario` ni de `cantidadreal`. En la fila `F` es la suma de las filas de operario, calculada con una consulta **aparte**: la consulta del agregado de `cantidadreal` no cambia.
- `mensajes_mqtt.unidadesCalculadasConglomerado`: solo se guarda y genera alertas.
- Los contadores en memoria (`conteo_mqtt_actual`, `delta_ultimo_mensaje`): solo se muestran.
- `cantidadcot`: cantidad cotizada de Optimus (`job200.j_quantity`); solo se guarda.

## 2. Modelo implícito del contador del ESP

| Supuesto | Nivel | Base |
|---|---|---|
| `cantpliegos` es un **contador acumulado** de la sesión del ESP | I | Se toma "la última lectura" como total; `_calcular_unidades_conglomerado` (`mqtt_persistencia_simulada_service.py:157-187`) resta lecturas consecutivas |
| En un MT el contador **no** se reinicia (el ESP no se detiene) | I | No se publica paro en MT; por eso se restan los MT anteriores |
| Tras FINAL o MD y un nuevo inicio, el contador **se reinicia** | I | Los MD no se restan; 1.382 alertas de tipo `RESET` en `logs/mqtt_conglomerado_alertas.log` |
| Al **reenviar el inicio con la misma OP y actividad** (relevo MT), el contador se mantiene | **?** | Firmware fuera del repo (P-01). Desde la v20.19 (2026-09-07) no se ha registrado ningún negativo productivo, lo que apunta a que **no** se reinicia o a que el caso es raro [I] |

## 3. Esperado

- Regla vigente declarada en el código: "cantidadreal = último cantpliegos de datossensados − SUM(cantidadreal de MT anteriores)" (`cierres_service.py:387`) [C].
- [?] El ámbito correcto de "MT anteriores" (misma sesión, recurso, MAC, fecha). **No hay una regla aprobada** (P-04).

## 4. Escenarios de valores negativos, duplicados o inconsistentes

| # | Escenario | Resultado | Nivel | Evidencia |
|---|---|---|---|---|
| N1 | Filas MT de **otro recurso, usuario o fecha** con el mismo numOp+actividad | Se restan → negativo o infravalorado | **C** | Único evento del log (2026-10-12 16:12, FINAL `12345/COMIDA`, recurso PEG CAJ2): restó un MT de `12345/COMIDA` del **2026-08-21** en otro recurso y con otro usuario → `0 − 1 = −1` |
| N2 | Los improductivos comparten OP 12345 y motivo → **contaminación en toda la planta** | Negativos recurrentes | C | Igual que N1 |
| N3 | MT → MD → reapertura de la misma OP y actividad: los MT anteriores siguen restando sobre un contador nuevo | Negativo o infravalorado | C (fórmula) / ? (contador) | — |
| N4 | MT → relevo: se reenvía el inicio; si el firmware reinicia el contador → (nuevo − MT) | Negativo o infravalorado | ? | P-01 |
| N5 | Sin filas DATOS (inicio no publicado, ESP apagado o desconectado, MQTT caído) **o error de MySQL en esa lectura** (E1) | 0, tiempos = ahora, duración 0; con MT previos → negativo | C | — |
| N5b | Error de MySQL en la suma de MT (E1) | Se toma 0 → cantidad sobrevalorada | C (mecanismo) | — |
| N6 | El ESP envía una numOp o actividad distinta de la del marcaje (solo se avisa en memoria, `marcajes_estado_service.py:173-181`) | Cantidad 0 y filas huérfanas que el DELETE no borra | C (mecanismo) | — |
| N7 | Filas huérfanas en `datossensados` (DELETE fallido, DATOS después del paro, hueco tras un MT) | `tiempoinicio` antiguo → duración inflada; cantidad incorrecta si la última fila es huérfana | C (mecanismo) / I (frecuencia) | — |
| N8 | Segundo FINAL de la misma numOp+actividad (también cualquier FINAL de un improductivo) | La nueva fila `F` suma las `F` anteriores → **doble conteo acumulativo**; `duracion` crece | C (código) / ? (magnitud) | El selector de tipo de cierre tiene FINAL por defecto |
| N9 | Filas duplicadas en `datossensados` (sin UNIQUE) | **Sin efecto** en cantidad ni tiempos (se usa la última fila y MIN/MAX) | C | 774 mensajes × 2 filas en el log |
| N10 | Doble cierre concurrente del mismo marcaje | 2 filas de resumen; la segunda puede ser 0 | C (sin guarda) / I (probabilidad) | — |
| N11 | Reintento tras un cierre parcial (DELETE de `marcajeactivo` fallido) | Segunda fila `0 − MT`, tiempos = ahora | C | — |
| N12 | El ESP se reinicia en mitad de la sesión | Infravalorado; con MT previos → negativo | ? / C (no se detecta) | — |

## 5. Riesgos al modificar

- Filtrar la suma de MT por recurso o MAC cambia los resultados de los relevos **legítimos** si un relevo cambiara de recurso (no debería, porque se reutiliza el recurso [C]). Hay que validarlo con datos históricos.
- Acotar a la "misma sesión" exige una noción de sesión que **no existe** en el esquema. No hay id de sesión ni hora de inicio en `marcajeactivo` [C].
- Truncar a 0 (`max(0, …)`) **oculta** errores. README_V20_20 dice expresamente que hoy no existe tal truncado.
- El agregado `F` probablemente lo consume otro sistema (P-05). Cambiarlo afecta a los reportes ya exportados.

## 6. Recomendaciones (NO aprobadas)

Detalle en `10-decisiones-pendientes.md`:
- Resolver P-01 y P-04 antes de tocar nada.
- Añadir pruebas de caracterización (`11-pruebas.md`) que fijen el comportamiento actual de N1-N11.
- Considerar un identificador de sesión del marcaje.
