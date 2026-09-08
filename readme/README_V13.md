# SmartFactory Web v13 - Simulación de persistencia MQTT

Esta versión prepara la gestión real de mensajes MQTT, pero **no inserta todavía en base de datos**.

## Objetivo

Cada mensaje MQTT tipo `MAC-DATOS` ahora arma en modo simulación:

1. `idmensaje` con la misma lógica del programa original:

```text
MAC + " " + fecha + " " + tiempo
```

2. Consulta del `cantpliegos` anterior de la misma MAC:

```sql
SELECT cantpliegos
FROM smartfactory.mensajes_mqtt
WHERE mac = %s
ORDER BY fechatiempo DESC
LIMIT 1;
```

3. Cálculo de `unidadesCalculadasConglomerado`:

```python
if actual >= anterior:
    produccion = actual - anterior
else:
    produccion = actual
```

Si no existe anterior, esta versión toma el `actual` como producción inicial calculada.

4. SQL simulado para:

```sql
INSERT IGNORE INTO smartfactory.mensajes_mqtt (..., unidadesCalculadasConglomerado)
```

5. SQL simulado para:

```sql
INSERT IGNORE INTO smartfactory.datossensados (idmensaje, ...)
```

## Importante antes de activar escritura real en una versión futura

Ya ejecutaste:

```sql
ALTER TABLE smartfactory.mensajes_mqtt
ADD COLUMN unidadesCalculadasConglomerado INT NULL;
```

Antes de insertar realmente en `datossensados`, debe existir la columna:

```sql
ALTER TABLE smartfactory.datossensados
ADD COLUMN idmensaje VARCHAR(100) NULL;
```

No agregues todavía el `UNIQUE KEY` hasta validar que la columna se llena correctamente.

## Qué validar

- Que los mensajes MQTT siguen apareciendo en vivo.
- Que los topics no `DATOS` no armen INSERT operativo.
- Que para `MAC-DATOS` se muestra:
  - `idmensaje`
  - cantpliegos anterior
  - cantpliegos actual
  - unidades calculadas por conglomerado
  - INSERT simulado para `mensajes_mqtt`
  - INSERT simulado para `datossensados`
- Que la asociación con marcaje activo sigue funcionando.
- Que no se escribe nada en BD todavía.

## Ejecución

Terminal backend principal:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Terminal huella local:

```bash
uvicorn huella_local.main:app --reload --host 127.0.0.1 --port 9001
```
