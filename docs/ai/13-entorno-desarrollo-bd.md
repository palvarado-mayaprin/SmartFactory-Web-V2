# 13 — Entorno de desarrollo y aislamiento de MySQL (PROPUESTA)

> **Estado: propuesta preparada y NO implementada (2026-11-13).** No se ha modificado `db/conexion.py` ni ninguna conexión.
> Implementarla exige la autorización explícita M-15 (`10-decisiones-pendientes.md`). Hasta entonces, el único entorno seguro es el de pruebas con dobles (`11-pruebas.md`).

## 1. Situación actual [C]

- `db/conexion.py` contiene **cuatro configuraciones fijas** (host, usuario, contraseña, base), sin variables de entorno. Para cambiar de BD hay que editar el código.
- Ninguna sentencia de escritura pasa por los flags de forma centralizada: cada servicio comprueba `ENABLE_REAL_*` por separado. Las **lecturas** van siempre a producción.
- **Todo el SQL califica las tablas con el nombre del esquema**: 77 apariciones de `smartfactory.<tabla>` en `services/` y `api/`, y 8 de `mayaprin.<tabla>`.
  - **Consecuencia**: una BD de desarrollo **tiene que llamarse `smartfactory`** y vivir en **otro servidor o instancia MySQL**. Cambiar solo el nombre de la base no aísla nada.
- Al arrancar, `main.py` se conecta al broker de producción y persiste los DATOS. Si el backend arrancara apuntando a una BD de desarrollo, **guardaría en ella los DATOS reales de planta** y, con el flag de publicación activo, **publicaría a máquinas reales**.

## 2. Objetivos

1. Elegir el entorno con una variable, sin editar código: `SMARTFACTORY_DB_ENTORNO = produccion | desarrollo`.
2. Que **producción siga funcionando exactamente igual** si nadie define nada: `produccion` es el valor por defecto, con la configuración actual.
3. Que sea **imposible escribir en producción por accidente** estando en `desarrollo`.
4. Que el código nuevo no contenga credenciales y use SQL parametrizado.
5. Que las pruebas automatizadas sigan sin necesitar BD ni broker.

## 3. Diseño propuesto

### 3.1 Selección de entorno (`db/entorno.py`, nuevo)

```text
SMARTFACTORY_DB_ENTORNO=desarrollo          # por defecto: produccion
SMARTFACTORY_DEV_MYSQL_HOST=127.0.0.1       # instancia local (p. ej. MySQL 8 en Docker o en la PC)
SMARTFACTORY_DEV_MYSQL_PORT=3307
SMARTFACTORY_DEV_MYSQL_USER=sf_dev
SMARTFACTORY_DEV_MYSQL_PASSWORD=...         # solo en .env.desarrollo (ignorado por git: regla `.env.*`)
SMARTFACTORY_DEV_OPTIMUS=doble              # doble | lectura_produccion (esta última requiere aprobación)
```

- `obtener_config("smartfactory")` devuelve:
  - en `produccion`: la configuración actual, tal cual, para no cambiar el comportamiento;
  - en `desarrollo`: la de las variables `DEV_*`.
- La base siempre se llama `smartfactory`, por la calificación de §1.
- Se incluirá una plantilla `.env.desarrollo.example` sin secretos. La regla `!.env.*.example` de `.gitignore` permite versionarla.

### 3.2 Barreras contra escrituras productivas (todas obligatorias en `desarrollo`)

| Barrera | Mecanismo |
|---|---|
| B1 — Marca de entorno | Antes de la **primera escritura** de cada proceso se comprueba `SELECT valor FROM smartfactory.sf_entorno WHERE clave='entorno'` = `'desarrollo'`. Producción no tiene esa tabla, así que la escritura se rechaza. El resultado se cachea |
| B2 — Host distinto | En `desarrollo`, si el host y el puerto coinciden con la configuración de producción, el proceso se niega a arrancar. La comparación se hace sin imprimir los valores |
| B3 — MQTT apagado | En `desarrollo` se fuerzan a `0` `ENABLE_REAL_MQTT_PUBLISH` y `ENABLE_REAL_MQTT_DB_WRITES`, y no se conecta al broker al arrancar (requiere `SMARTFACTORY_MQTT_AUTOSTART=0` en `main.py`, ver §4) |
| B4 — Optimus | Por defecto, un doble con datos de ejemplo. La lectura del Optimus productivo (usuario de solo lectura) solo se activa con `lectura_produccion` y aprobación |
| B5 — Visibilidad | `/api/health` y la cabecera de la UI muestran el entorno activo (cambio de UI pequeño) |

### 3.3 Acceso a datos para funcionalidades NUEVAS (`db/consultas.py`, nuevo)

- `consultar(sql, params) -> list[tuple]` y `ejecutar(sql, params) -> int` (filas afectadas), siempre **parametrizados** (`%s`).
- **Lanzan una excepción** ante un error de BD. Así no se repite R-03 (confundir error con "sin filas").
- `with transaccion() as tx:` para operaciones de varias sentencias. Una conexión y `commit`/`rollback`.
- Aplican B1 y B2 en las escrituras.
- **El código existente no se migra** salvo que un requisito lo exija. Si se migra, se hace función por función, con pruebas de caracterización previas (`11-pruebas.md`).

### 3.4 Esquema de la BD de desarrollo

- Hace falta el DDL real (P-03). Para obtenerlo: `SHOW CREATE TABLE` de las 6 tablas, **solo lectura y con autorización**.
- Esquema parcial ya conocido: `02-base-de-datos.md` §2.
- Script versionado propuesto: `tests/bd_desarrollo/esquema.sql` (DDL + tabla `sf_entorno`) y `semilla.sql` (datos mínimos ficticios: 2 MAC, 2 usuarios, 1 OP).

### 3.5 Pruebas contra la BD de desarrollo (opcional)

- Marcador `bd_desarrollo` (ya registrado en `pytest.ini`). Esas pruebas se omiten salvo que `SMARTFACTORY_DB_ENTORNO=desarrollo` y la barrera B1 se cumpla.
- Requieren el driver MySQL, que **no** está en `.venv-test` a propósito. Se usaría un entorno aparte (`requirements-integracion.txt`), **nunca** el de pruebas por defecto.

## 4. Cambios en código existente que exigirá la implementación (requieren autorización)

| Archivo | Cambio mínimo | Riesgo |
|---|---|---|
| `db/conexion.py` | Las clases obtienen la configuración de `db/entorno.py`. Valores de producción idénticos por defecto | Medio: es el punto de acceso de todo el sistema. Validar con pruebas y revisión de diff |
| `main.py` | Respetar `SMARTFACTORY_MQTT_AUTOSTART` (por defecto `1`) en el evento `startup` | Bajo |
| `config.py` | Forzar los flags MQTT a `0` cuando `SMARTFACTORY_DB_ENTORNO=desarrollo` | Bajo |

Mover las credenciales de producción a variables de entorno es un paso **separado** (M-07, P-12): toca la operación de planta y los `.bat`.

## 5. Verificación del aislamiento (antes de la primera escritura real en desarrollo)

1. Con `desarrollo` activo, `/api/health` muestra el entorno.
2. Una escritura contra una BD **sin** `sf_entorno` es rechazada (prueba automatizada con un doble y prueba manual).
3. No hay conexión al broker (revisar `/api/mqtt/estado`).
4. Con el `.env` de producción y sin variables, el comportamiento no cambia (pruebas de caracterización en verde).
