# SmartFactory Web v20 — Preparación para primera versión funcional

Esta versión no agrega lógica operativa nueva. Su objetivo es dejar el sistema listo para un piloto controlado.

## Incluye

- Scripts `.bat` para iniciar el backend principal y el servicio local de huella.
- Archivo `.env.piloto.example` como referencia de configuración.
- Carpeta `logs/` preparada.
- Checklist de validación de flujo completo.
- Variables de seguridad activas para piloto:
  - `SMARTFACTORY_ENABLE_REAL_DB_WRITES=1`
  - `SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES=1`
  - `SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1`

## Archivos nuevos

```text
iniciar_backend_piloto.bat
iniciar_huella_local_piloto.bat
iniciar_todo_piloto.bat
verificar_servicios_piloto.bat
.env.piloto.example
logs/.gitkeep
README_V20.md
```

## Cómo iniciar

Desde la carpeta `src_web`, ejecutar:

```bat
iniciar_todo_piloto.bat
```

Esto abre dos ventanas:

```text
Backend principal: http://127.0.0.1:8000
Huella local:      http://127.0.0.1:9001
```

Luego abrir:

```text
http://127.0.0.1:8000
```

## Verificación rápida

Ejecutar:

```bat
verificar_servicios_piloto.bat
```

Debe responder correctamente:

```text
/api/health
/api/huella/health
```

## Checklist funcional piloto

Validar en este orden:

1. Backend principal inicia sin errores.
2. Servicio local de huella inicia sin errores.
3. `EnrollmentSample CS.exe` abre y lee huella real.
4. Usuario válido muestra Swal de bienvenida.
5. Usuario no encontrado muestra Swal de error.
6. OP se consulta correctamente.
7. Actividades se muestran correctamente.
8. Inicio real de marcaje inserta en `marcajeactivo`.
9. Inicio real publica MQTT hacia ESP.
10. ESP empieza a enviar `DATOS` con OP/actividad correcta.
11. `mensajes_mqtt` recibe registros reales.
12. `datossensados` recibe registros reales.
13. Sidebar muestra marcaje activo en vivo.
14. Cierre `MD` publica MQTT antes de tocar BD.
15. Cierre `MT` no publica MQTT y activa relevo.
16. Relevo MT identifica nuevo operario y reutiliza OP/máquina/actividad.
17. Cierre `FINAL` inserta resumen final `SMARTFACTORY` estado `F`.
18. `datossensados` se limpia al cerrar.
19. `marcajeactivo` se limpia al cerrar.
20. `resumenmarcajes` queda correcto.

## Recomendación para piloto

Primero probar con:

```text
1 PC
1 lector de huella
1 máquina
1 OP real controlada
1 usuario operador
1 usuario supervisor
```

No iniciar con todas las máquinas al mismo tiempo.

## Notas importantes

- Para cierres `FINAL` y `MD`, el backend debe tener MQTT conectado antes de ejecutar el cierre real.
- Si MQTT no está conectado, el sistema debe bloquear cierre `FINAL`/`MD` para evitar cerrar BD sin detener el ESP.
- `mensajes_mqtt` es histórico permanente.
- `datossensados` es tabla operativa temporal y se limpia al cierre del marcaje.
- El servicio de huella corre en cada PC con lector; el backend principal puede correr en el servidor central.
