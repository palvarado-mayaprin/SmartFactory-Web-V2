# SmartFactory Web v20.25

## Resolución de la OT (parte de la orden) al abrir un marcaje

Esta versión parte de v20.24 y deja de suponer que una OP tiene una sola OT (`OP + "01"`). Se toman todas las OT de la OP en Optimus (`wo.wo_job`), se resuelve en cuál trabaja el operario y esa OT y su tarea quedan **fijadas al abrir** el marcaje. Adaptación de la lógica de PRODIGOS V2; diseño completo en `docs/ai/14-resolucion-ot.md`.

### Requisito previo de base de datos

La migración `migraciones/2026-11-24_marcajeactivo_resolucion_ot.sql` debe estar aplicada **antes** de desplegar. Ya fue ejecutada y verificada en `smartfactory` (2026-11-24). Añade a `smartfactory.marcajeactivo`, todas nulables:

```sql
wo_number        INT         NULL,
tk_id            INT         NULL,
estadoResolucion VARCHAR(12) NULL,  -- AUTOMATICA | ELEGIDA | SIN_TAREA
tituloOt         VARCHAR(60) NULL
```

Si un backend apunta a una base de datos sin estas columnas, toda apertura falla.

### Qué cambia para el operario

- **Elección de la parte de la orden**: si la actividad elegida está en 2 o más OT de la OP, aparece el diálogo «¿En qué parte de la orden trabaja?», con una opción por OT (título y «OT n») en el orden de la orden. «Volver» cancela sin crear nada. Si la actividad está en una sola OT o en ninguna, no se pregunta.
- La confirmación y el aviso de éxito muestran la fila **Parte** cuando hay una OT asignada. La línea «OT: OP01» de la tarjeta de la orden desaparece.
- Si las partes de la orden cambian entre la elección y la confirmación, se vuelve a preguntar con el aviso «Las partes de la orden cambiaron; vuelva a elegir» (un solo reintento).
- **Actividades dadas de baja** en Optimus (`act_discont <> '0'`) ya no aparecen, ni entre las cotizadas ni entre las no cotizadas. Las cotizadas son las que tienen tarea en **cualquier** OT de la OP.
- **Validación de la OP por su estado**: la OP debe ser solo dígitos, existir en Optimus y estar abierta. Se rechazan las OP canceladas, reservadas, suspendidas o bloqueadas, con un mensaje que lo indica. Las OP completadas sí se pueden marcar. **Ya no hay rango** 10.000–1.000.000.
- **Reanudar tras un tiempo improductivo** reutiliza la OT del marcaje anterior; solo pregunta si ya no es válida.
- El **relevo MT** hereda la OT del marcaje cerrado: no pregunta ni consulta Optimus.

### Qué cambia técnicamente

- **Resolución en el servidor**: `services/resolucion_ot_service.py` (nuevo).
  - Funciones puras `evaluar_elegibilidad_op` y `resolver` (estados `SIN_TAREA`, `AUTOMATICA` y `ELEGIDA`).
  - Lectura de Optimus `resolver_desde_optimus`: SELECT parametrizados sobre `job200`, `wo` y `wo_task200`, con límites de 100 OT y 500 tareas.
  - La apertura resuelve la OT **antes** de cualquier efecto: un rechazo no escribe ni publica MQTT.
- **Columnas nuevas de `marcajeactivo`**: las aperturas productiva, improductiva (siempre `SIN_TAREA`) y de relevo las escriben en el mismo INSERT. El orden de efectos INSERT → MQTT no cambia.
- **El cierre copia la OT y la tarea** de `marcajeactivo` a `resumenmarcajes` (fila del operario y fila `F`) sin recalcularlas. Con `SIN_TAREA` escribe `0`/`0`. Si no puede leer la OT, el cierre se rechaza **antes** de publicar o escribir (409 `ERROR_BD_OT`).
- **El relevo MT hereda** `wo_number`, `tk_id`, `estadoResolucion` y `tituloOt` y solo valida su forma. Si los datos son incoherentes, responde 409 `DATOS_RELEVO_INCOMPLETOS`.
- **Endpoint nuevo `POST /api/op/ots`** `{num_op, actividad}` → `{ok, requiereEleccion, ots:[{numeroOt, titulo, secuencia}]}`. Es de solo lectura.
- **`POST /api/marcajes/iniciar-real-bd`**: acepta `numero_ot` (opcional, entero ≥ 1) y deja de usar `num_ot`.
  - **409** con `detail={modo: "RESOLUCION_OT", codigo, mensaje, ots_candidatas?}`. Códigos: `SELECCION_OT_REQUERIDA`, `OT_NO_CANDIDATA`, `OP_INEXISTENTE`, `OP_CANCELADA`, etc.
  - **503** con `OPTIMUS_NO_DISPONIBLE`.
  - La respuesta correcta incluye `resolucion`.
- **`POST /api/op/buscar`**: elegibilidad por `job200`, sin rango, y sin `orden.num_ot`. Mantiene el 400 con `detail` de texto.
- **`/api/actividades/recurso` y `/no-cotizadas`**: reciben `num_op` en lugar de `num_ot`.
- **Frontend**:
  - `static/js/resolucion_ot.js` (nuevo, lógica pura) y diálogo de elección en `static/js/app.js`.
  - `postJson` conserva `status` y `detail` del error.
- **Versión**: `main.py` y `templates/index.html` pasan a 20.25.0.
- **Pruebas**:
  - Python: `tests/test_resolucion_ot.py`, `tests/test_resolucion_ot_optimus.py` y `tests/test_ot_fijada.py`.
  - Node: `tests/js/resolucion_ot.test.js`.
  - Total: 155 pruebas pytest y 6 de Node.

### Compatibilidad

- Los marcajes **abiertos antes del despliegue** no tienen la OT fijada (`estadoResolucion` NULL). Al cerrarlos se usa el cálculo anterior (`_obtener_wo_tk`). Su relevo MT se abre también sin OT.
- No cambian:
  - el cálculo de `cantidadreal` ni la resta de MT;
  - el agregado de la fila `F`, salvo de dónde salen `wo_number` y `tk_id`;
  - los pliegos buenos e incorrectos;
  - los payloads ni el orden MQTT;
  - el recurso, que sigue siendo el centro de costo.
- Las OT no viajan al ESP.

### Despliegue

**Backend y frontend juntos.** No se puede desplegar solo una parte: con el backend nuevo y la pantalla antigua, los marcajes de actividades que están en varias OT reciben 409 y el operario no tiene forma de elegir.

Recargar la página en todas las PCs tras el despliegue para que carguen `resolucion_ot.js` y el nuevo `app.js`.

### Lista de comprobación en planta

Empezar por **una sola PC** y una OP con varias OT (por ejemplo, la **51847**).

1. **Actividad en 1 OT o en ninguna**: no se pregunta. El éxito muestra «Parte» solo si hay OT.
2. **Actividad en 2 o más OT**: se pregunta, en el orden de la orden.
   - «Continuar» sin elegir avisa.
   - «Volver» no crea nada: ni marcaje ni MQTT.
   - La confirmación y el éxito muestran «Parte».
   - En `marcajeactivo` queda `estadoResolucion = 'ELEGIDA'` con la OT y la tarea elegidas.
3. **Las partes cambian entre la elección y la confirmación** (409): se repite la elección con el aviso, una sola vez.
4. **Actividad no cotizada**: no se pregunta y queda `SIN_TAREA`.
5. **Reanudar tras improductivo**: se reutiliza la OT anterior. Si ya no es válida, se pregunta con el aviso.
6. **Relevo MT**: no se pregunta y el nuevo marcaje conserva la OT.
7. **Cierre FINAL de un marcaje `ELEGIDA`**: la fila del operario y la fila `F` de `resumenmarcajes` llevan la OT y la tarea elegidas.
8. **Optimus caído**: «No se pudo iniciar el marcaje» y no se crea nada.
9. **OP cancelada, bloqueada o inexistente**: mensaje claro al buscarla.

### Riesgos abiertos

- **R-34**: la resta de MT de `cantidadreal` y el agregado `F` agrupan por OP + actividad, **no por OT**. Si la misma actividad se trabaja en dos OT de una OP, sus MT y resúmenes se mezclan. No está corregido; requiere decisión (P-04).
- **R-10**: la lista de recursos sigue sin filtrarse por la OP (lee `wo200` sin filtro). Sin cambios en esta versión (P-08).
- **P-02**: si alguna PC sigue usando la app PyQt, sus aperturas no escriben la OT (no se ha revisado). Esos marcajes se cierran con el cálculo anterior.
- La fila «Parte» no aparece en la tarjeta del sidebar: la memoria no conoce la OT.

### Pendiente

- Prueba en planta con la lista anterior.
- Decidir R-34 antes de usar en serio la elección entre varias OT para la misma actividad.
