# SmartFactory Web v20.5 - Flujo operacional directo

Esta versión parte de `v20.4_mqtt_auto_eventos_admin` y elimina las etapas intermedias de simulación/confirmación manual del flujo operativo.

## Cambios principales

### 1. Inicio de marcaje directo

Antes:

```text
Usuario -> OP -> Actividad -> Simulación de inicio -> Iniciar marcaje REAL BD
```

Ahora:

```text
Usuario -> OP -> Actividad -> INSERT marcajeactivo + MQTT inicio
```

Al seleccionar una actividad se llama directamente a:

```text
POST /api/marcajes/iniciar-real-bd
```

Se mantiene la validación crítica de backend:

- usuario con marcaje activo
- recurso/máquina con marcaje activo
- campos obligatorios
- escritura real controlada por flags
- publicación MQTT de inicio según configuración

### 2. Cierre directo

Antes:

```text
Usuario con marcaje activo -> tipo cierre -> Simulación cierre -> Ejecutar cierre real
```

Ahora:

```text
Usuario con marcaje activo -> tipo cierre -> Ejecutar cierre
```

El botón de cierre llama directamente a:

```text
POST /api/marcajes/ejecutar-cierre-real
```

Se mantiene la lógica crítica:

- FINAL publica MQTT stop antes de cierre BD
- MD publica MQTT stop antes de cierre BD
- MT no publica MQTT stop
- FINAL/MD limpian `datossensados` según lógica existente
- todos los cierres registran `resumenmarcajes` según el servicio actual

### 3. Relevo MT automático

Antes:

```text
MT -> relevo pendiente -> operario B se identifica -> botón iniciar relevo
```

Ahora:

```text
MT -> relevo pendiente -> operario B se identifica -> apertura automática del relevo
```

El sistema reutiliza:

- OP
- recurso/máquina
- actividad
- datos del cierre MT

### 4. Limpieza visual

Se retiraron del HTML operativo:

- card de simulación de inicio
- card de simulación de cierre
- botón “Agregar a marcajes activos simulados”
- botón “Iniciar marcaje REAL BD”
- botón “Simular cierre”
- botón manual “Iniciar marcaje de relevo”

### 5. Se conserva

- MQTT automático de v20.4
- visor Eventos solo ADMIN
- marcajes activos visibles para todos
- login elevado ADMIN/SU
- herramientas técnicas ocultas para usuario normal
- validaciones críticas backend
- flags de seguridad para despliegue controlado

## Archivos modificados

- `templates/index.html`
- `static/js/app.js`
- `README_V20_5.md`

## Nota técnica

Algunas funciones frontend antiguas se conservan como wrappers de compatibilidad para evitar errores si algún navegador conserva cache o si existe una referencia antigua. Ya no ejecutan simulaciones operativas.
