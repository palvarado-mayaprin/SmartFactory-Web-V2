# SmartFactory Web - v14 Persistencia MQTT real controlada

Esta fase agrega persistencia real opcional de mensajes MQTT.

## Flujo implementado

```text
MQTT recibido
↓
parsear payload DATOS
↓
armar idmensaje = MAC + fecha + tiempo
↓
buscar cantpliegos anterior por MAC
↓
calcular unidadesCalculadasConglomerado
↓
INSERT IGNORE smartfactory.mensajes_mqtt
↓
INSERT IGNORE smartfactory.datossensados
↓
actualizar frontend por WebSocket
```

## Modo protegido por defecto

Por defecto NO inserta en BD.

Para ejecutar normal en modo protegido:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Activar escritura MQTT real

En PowerShell:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES="1"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

En CMD:

```cmd
set SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES=1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Requisitos previos de base de datos

Ya debe existir:

```sql
ALTER TABLE smartfactory.mensajes_mqtt
ADD COLUMN unidadesCalculadasConglomerado INT NULL;
```

También debe existir antes de activar escritura real:

```sql
ALTER TABLE smartfactory.datossensados
ADD COLUMN idmensaje VARCHAR(100) NULL;
```

Para que `INSERT IGNORE` realmente evite duplicados en `datossensados`, se recomienda agregar un índice único cuando ya se haya validado que no hay duplicados:

```sql
ALTER TABLE smartfactory.datossensados
ADD UNIQUE KEY uq_idmensaje (idmensaje);
```

Sin ese índice, `INSERT IGNORE` no impedirá duplicados por `idmensaje` en `datossensados`.

## Logs

La persistencia MQTT registra eventos en:

```text
logs/mqtt_persistencia.log
```

## Qué validar

1. En modo protegido, los mensajes deben mostrar SQL pero no insertar.
2. Con `SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES=1`, cada mensaje `MAC-DATOS` debe insertarse en `mensajes_mqtt` y `datossensados`.
3. `idmensaje` debe ser igual en ambas tablas.
4. `unidadesCalculadasConglomerado` debe calcularse usando el último `cantpliegos` de la misma MAC.
5. El frontend debe seguir actualizándose en vivo.
6. Marcajes activos y asociación MQTT deben seguir funcionando.
