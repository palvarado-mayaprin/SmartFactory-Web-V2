# SmartFactory Web v13 - Validación temprana de marcaje activo

## Objetivo

Esta versión cambia el flujo del paso 1:

1. El usuario se identifica por huella simulada o código manual.
2. El backend valida si el usuario ya tiene marcaje activo.
3. Si NO tiene marcaje activo, permite ingresar OP.
4. Si SÍ tiene marcaje activo, bloquea el ingreso de OP y muestra panel de cierre.

## Validaciones nuevas

- Consulta estado vivo en memoria.
- Consulta `smartfactory.marcajeactivo`.
- Devuelve `siguiente_paso`:
  - `ingresar_op`
  - `cerrar_marcaje`
- El frontend muestra una tarjeta de cierre cuando corresponde.

## Importante

El cierre real sigue protegido por la variable:

```powershell
$env:SMARTFACTORY_ENABLE_REAL_DB_WRITES="1"
```

Si no está activa, el sistema valida pero no elimina registros reales.
