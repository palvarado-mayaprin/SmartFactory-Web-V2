# SmartFactory Web v20.11

## Corrección incluida

Esta versión agrega los archivos faltantes para que el backend pueda importar correctamente:

```python
from db.conexion import dtbOptimus1, dtbSmartFactory, dtbOptimus, dtbEntregasDiarias
```

## Archivos agregados

- `db/conexion.py`
- `db/__init__.py`

## Ajuste adicional en requirements.txt

Se cambió:

```txt
uvicorn[standard]
```

por:

```txt
uvicorn
```

para evitar el error de compilación de `httptools` en Windows.

También se agregaron:

```txt
mysql-connector-python
pyodbc
```

## Comando recomendado

Desde la carpeta raíz del proyecto y con el entorno virtual activo:

```bat
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
