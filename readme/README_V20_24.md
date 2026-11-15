# SmartFactory Web v20.24

## Registro de pliegos incorrectos al cerrar actividad

Esta versión parte de v20.23 y agrega el registro de los pliegos incorrectos declarados por el operario al cerrar un marcaje.

### Requisito de base de datos

La columna debe existir en `smartfactory.resumenmarcajes` **antes** de desplegar esta versión:

```sql
pliegosIncorrectos INT NULL DEFAULT NULL
```

Si un backend apunta a una base de datos sin la columna, el INSERT del resumen falla y el cierre se rechaza sin borrar el marcaje activo (ver «Fallo del INSERT del resumen»).

### Interfaz

- En el panel de cierre, debajo de la cantidad de pliegos buenos, se agrega el campo **Pliegos incorrectos**.
- El campo inicia en `0`. Si se deja vacío, se interpreta como `0`.
- Solo acepta enteros mayores o iguales a 0. Valores negativos, decimales, texto o notación científica se rechazan con un aviso y el cierre no se envía.
- En marcajes improductivos (`numOp = 12345`) el campo se oculta y no se envía.
- La confirmación del cierre muestra **Pliegos buenos (total reportado)** y **Pliegos incorrectos**.
- Se bloquea el doble envío del cierre mientras la solicitud está en curso.

### API

`/api/marcajes/simular-cierre` y `/api/marcajes/ejecutar-cierre-real` aceptan el campo opcional `pliegos_incorrectos`:

- Entero estricto entre `0` y `2147483647`, o `null`.
- Un valor inválido responde **422** sin efectos en BD ni MQTT.
- Si el campo no se envía (clientes anteriores), se guarda `NULL`.

### Persistencia

- **FINAL, MD y MT**: la fila del operario guarda el valor en `resumenmarcajes.pliegosIncorrectos`.
- **Fila F (FINAL)**: guarda la suma de `pliegosIncorrectos` de las filas de operario de la OP y actividad (excluye las filas `F`). Si la consulta de la suma falla, se guarda `NULL`.
- **Improductivo (12345)**: siempre `NULL`.
- **PAUSA POR ACTIVIDAD IMPRODUCTIVA**: el MD conserva `variable01 = 1` y guarda además los pliegos incorrectos.

Los pliegos incorrectos son independientes de `totalUsuario` (pliegos buenos declarados) y de `cantidadreal` (sensor): no se suman ni se restan entre sí.

### Fallo del INSERT del resumen

Si falla el INSERT de la fila del operario en `resumenmarcajes`, el cierre se aborta con **409** (`INSERT_RESUMEN_FALLIDO`):

- No se elimina el marcaje activo ni sus datos sensados; el cierre puede reintentarse.
- En FINAL y MD el paro MQTT ya fue publicado al ESP antes del INSERT; el mensaje lo indica expresamente.

Antes de esta versión el cierre continuaba, borraba el marcaje y respondía como exitoso aunque el resumen no se hubiera guardado.

### Cambios técnicos

- `templates/index.html`: campo de pliegos incorrectos y versión visual v20.24.
- `static/js/cierre_validacion.js`: validación del campo (nuevo).
- `static/js/app.js`: validación, confirmación, envío del campo y bloqueo de doble envío.
- `models/schemas.py`: campo opcional `pliegos_incorrectos` en el request de cierre.
- `api/marcajes_api.py`: propaga el campo al servicio de cierres.
- `services/cierres_service.py`: validación, columna en los INSERT, suma para la fila F y aborto ante fallo del INSERT del operario.
- `main.py`: versión 20.24.0.
- Pruebas: `tests/test_pliegos_incorrectos.py` y `tests/js/cierre_validacion.test.js`.

### Compatibilidad

No se modifica el cálculo de `cantidadreal`, el agregado de la fila F para `cantidadreal`, `duracion` y `totalUsuario`, la publicación MQTT, la persistencia DATOS, los conglomerados, la apertura de marcajes ni el flujo de retorno tras improductivo de v20.23.

### Pendiente

- Confirmar que la columna existe en cada base de datos a la que apunta un backend y quién consume el dato (P-15).
- Definir la semántica definitiva de la fila F, que mezcla alcances distintos por columna (P-16).
