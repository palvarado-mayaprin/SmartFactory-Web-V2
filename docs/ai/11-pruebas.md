# 11 — Pruebas automatizadas

## 1. Estado (2026-11-14) [C]

- Infraestructura **mínima operativa**: pytest en un entorno aislado, **57 pruebas** (56 de comportamiento + 1 de consistencia de la documentación). Ejecución ≈3 s. Además, 3 pruebas de Node para la validación pura del formulario de cierre.
- Antes de la Fase 5 no existía ninguna prueba. La validación era manual, en planta y con datos reales.
- Frontend: solo la lógica pura de `static/js/cierre_validacion.js` (Node). El resto, sin pruebas automatizadas (ver §6).

## 2. Cómo ejecutar

```bash
# Una sola vez (ya hecho en esta máquina; .venv-test/ está ignorado por git)
venv\Scripts\python.exe -m venv .venv-test
.venv-test\Scripts\python.exe -m pip install -r requirements-dev.txt

# Siempre
.venv-test\Scripts\python.exe -m pytest              # todo
.venv-test\Scripts\python.exe -m pytest tests/test_cierre_marcaje.py -k final
.venv-test\Scripts\python.exe -m pytest -m "not caracterizacion"
```

**Nunca** ejecutes las pruebas con `venv\` (el de producción): ese entorno sí tiene drivers de MySQL y MQTT.

## 3. Garantías de aislamiento (`tests/conftest.py`)

| Barrera | Mecanismo | Verificada por |
|---|---|---|
| Sin drivers reales | `.venv-test` no instala `mysql-connector-python`, `pyodbc` ni `paho-mqtt` (`requirements-dev.txt`) | `tests/test_aislamiento.py::test_drivers_reales_no_disponibles` |
| Flags a 0 | `SMARTFACTORY_ENABLE_REAL_*="0"` antes de importar `config` | `test_flags_de_escritura_desactivados` |
| BD sustituida | `sys.modules["db.conexion"]` = doble que registra el SQL y responde por reglas | `test_db_conexion_es_el_doble` |
| Red bloqueada | `socket.connect` / `create_connection` lanzan error salvo loopback (asyncio en Windows usa socketpair local) | `test_red_externa_bloqueada` |
| MQTT sustituido | Fixture autouse `mqtt`: `publicar`, `iniciar` y `detener` falsos; las publicaciones se registran en el mismo orden que el SQL | Pruebas de orden de efectos |
| Logs reales intactos | Los `LOG_*` de los servicios se redirigen a `tmp_path` | `test_logs_reales_no_se_usan` |
| Árbol de código intacto | `sys.dont_write_bytecode = True`; `-p no:cacheprovider` | — |
| Ciclo de vida de FastAPI | Fixture `cliente` = `TestClient(app)` **sin** `with` → no ejecuta `startup` (que conectaría MQTT) | — |

Si `test_aislamiento.py` falla, **ninguna otra prueba es fiable**: corrige eso primero.

## 4. Herramientas del conftest

| Fixture | Uso |
|---|---|
| `bd` (autouse) | `bd.responder(regex, respuesta, origen=None)`. `respuesta` = filas, `None` (error de BD), una excepción o un callable. Orígenes: `smartfactory`, `optimus`, `optimus1`, `entregas`. Gana la primera regla que coincide. Sin regla: SELECT → `[]`; escritura en smartfactory → `"Operación exitosa"` |
| | Inspección: `bd.sql(origen)`, `bd.escrituras()`, `bd.secuencia()` (escrituras y MQTT en orden), `bd.eventos` |
| `mqtt` (autouse) | `mqtt.resultado = {...}` simula un fallo de publicación; `mqtt.publicaciones` |
| `escritura_habilitada` | Activa `ENABLE_REAL_*` **solo en los módulos** de persistencia y cierres (con los dobles activos) |
| `cliente` | `TestClient` de la app sin eventos de ciclo de vida |

## 5. Pruebas existentes

| Archivo | Cubre |
|---|---|
| `test_aislamiento.py` | Las barreras de §3 |
| `test_api_contrato.py` | Contrato HTTP que consume `app.js`: health, 422 de validación, 404 de usuario, 400 de OP, forma de `detail` en 409 |
| `test_apertura_marcaje.py` | Flags desactivados; **orden INSERT → MQTT**; payload exacto de inicio; publicación fallida (R-04); máquina ocupada; sin MAC; error de BD en validación (R-03); `recursoalternativo` (P-09); improductivo 12345 (R-18) |
| `test_cierre_marcaje.py` | Flags desactivados; **orden publicar → INSERT → INSERT F → DELETE → DELETE**; payload de paro; MT sin publicación y con relevo; pausa solo con MD; `variable01`; aborto si falla la publicación; INSERT de operario fallido → aborta sin DELETE (R-01 parcial, v20.24); negativo por MT sin filtrar (R-02); agregado `F` (R-13); retirada de memoria vía API |
| `test_pliegos_incorrectos.py` | v20.24: buenos e incorrectos por separado en FINAL/MD/MT; cero; valores inválidos en el servicio y en la API (422) sin efectos; contrato anterior sin el campo → `NULL`; suma de la fila `F` sin filas `F` y `NULL` si falla; improductivo → `NULL`; regresión: `cantidadreal` y la consulta del agregado no cambian |
| `tests/js/cierre_validacion.test.js` (Node) | Validación pura del campo *Pliegos incorrectos* y `escaparHtml`. Se ejecuta con `node --test "tests/js/*.test.js"` (no lo recoge pytest) |
| `test_docs_referencias.py` | CLAUDE.md y `docs/ai`: rutas, líneas, funciones, enlaces e IDs R/P/M válidos |

### Marcadores (`pytest.ini`)

- `caracterizacion`: fija el comportamiento **actual, incluidos los defectos documentados**.
  - **No cambies su expectativa** para "arreglar" una prueba.
  - Solo cambia cuando una decisión aprobada (P-xx/M-xx) modifica el comportamiento, y en el mismo cambio que lo implementa.
- `bd_desarrollo`: reservado para pruebas contra la BD de desarrollo (`13-entorno-desarrollo-bd.md`). Hoy no hay ninguna.

## 6. Estrategia por tipo de cambio

Elige por riesgo. No dupliques lo que ya está cubierto.

| Cambio | Pruebas mínimas |
|---|---|
| Endpoint nuevo | Contrato: éxito, validación (422), errores de negocio (400/404/409) con la forma de `detail` que espera la UI |
| Servicio nuevo con SQL | Doble de BD: SQL emitido (parámetros, no concatenación), respuesta ante `[]`, `None` y excepción |
| Escritura nueva | Orden de efectos (`bd.secuencia()`), comportamiento con los flags desactivados, comportamiento ante un fallo intermedio |
| Cambio en apertura o cierre | Las pruebas existentes deben seguir en verde. Si cambia el comportamiento, actualiza el caso de caracterización con la referencia de la decisión |
| Solo frontend | Sin automatización por defecto: lista de comprobación manual en el resumen. Si se añade **lógica pura** (validaciones de formulario, formateo), ponla en un módulo JS sin efectos al cargar y pruébala con `node --test` (Node 24 disponible, sin dependencias npm) |
| MQTT o sensores | **Fuera de alcance** por ahora (`06-mqtt-sensores.md` §0). Solo dobles de `publicar`; nada de brokers ni simuladores |

## 7. Límites conocidos

- El doble de BD no ejecuta SQL: verifica **qué** se envía, no que sea válido en MySQL. La validez real requiere la BD de desarrollo (M-15).
- `app.js` es un script con efectos al cargar (fetch y WebSocket); probarlo entero exigiría jsdom y dobles de red. No se justifica hoy.
- El verificador de documentación comprueba rangos, no semántica. La revisión humana sigue siendo necesaria (`12-procedimiento-desarrollo.md` §5).
