# docs/ai — Base de conocimiento técnico de SmartFactory Web v2

Documentación para desarrolladores y para sesiones de Claude Code. Entrada principal: `CLAUDE.md` (raíz).

**Base verificada**: commit `3d325c0` (2026-10-12) más el cambio `OR recursoalternativo` en `services/marcajes_service.py:32` (P-09) y v20.24 (pliegos incorrectos). Última revisión: 2026-11-15.
Si el código cambió después, **las referencias `archivo:línea` pueden haberse desplazado**: confirma siempre con Grep antes de actuar.

## Etiquetas de certeza (obligatorias)

| Etiqueta | Significado |
|---|---|
| **[C]** | Confirmado leyendo el código ejecutable o con evidencia directa (logs, git) |
| **[I]** | Inferido a partir de evidencia; plausible pero no demostrado |
| **[?]** | No verificable desde el repo (firmware, `.exe`, esquema completo de BD, despliegue, decisiones de negocio) |

Además, cada documento separa estos cinco planos. **No los mezcles**:

- **Actual**: lo que el sistema hace hoy.
- **Esperado**: la regla de negocio conocida o declarada. Solo es regla aprobada si un humano lo confirmó.
- **Problemas**: defectos identificados (IDs `R-xx` en `09-riesgos.md`).
- **Recomendaciones**: propuestas **no aprobadas**.
- **Pendiente**: decisiones o preguntas abiertas (IDs `P-xx` en `10-decisiones-pendientes.md`).

## Índice

| Doc | Contenido | Úsalo cuando… |
|---|---|---|
| [01-arquitectura.md](01-arquitectura.md) | Componentes, estructura del repo, mapa de dependencias, estado en memoria, frontend | Necesitas ubicarte o saber qué módulo toca qué |
| [02-base-de-datos.md](02-base-de-datos.md) | Orígenes de datos, tablas, esquema observado, quién lee y escribe, semántica de `db/conexion.py` | Vas a tocar SQL o persistencia |
| [03-endpoints-websockets.md](03-endpoints-websockets.md) | Catálogo de endpoints HTTP/WS (backend y huella), uso desde la UI, efectos | Vas a añadir o cambiar un endpoint |
| [04-flujos-marcajes.md](04-flujos-marcajes.md) | Apertura productiva e improductiva, cierres FINAL/MD/MT, relevo, pausa, ARR, retorno, sincronización | Vas a tocar cualquier flujo de marcaje |
| [05-cantidadreal.md](05-cantidadreal.md) | Fórmula de cantidades y tiempos, escenarios de error N1-N12 | Vas a tocar cálculos o cierres |
| [06-mqtt-sensores.md](06-mqtt-sensores.md) | Broker, topics, formatos de payload, persistencia DATOS, publicación | Vas a tocar MQTT o la integración con ESP |
| [07-identificacion-biometria.md](07-identificacion-biometria.md) | Servicio de huella local, identificación, roles elevados | Vas a tocar login, huella o permisos |
| [08-configuracion-despliegue.md](08-configuracion-despliegue.md) | Flags, `.env`, `.bat`, versiones, logs, despliegue | Vas a arrancar, configurar o desplegar |
| [09-riesgos.md](09-riesgos.md) | Registro de riesgos R-01… con evidencia y estado | Antes de cualquier cambio |
| [10-decisiones-pendientes.md](10-decisiones-pendientes.md) | Preguntas P-xx para humanos, recomendaciones no aprobadas, discrepancias doc↔código | Antes de "corregir" algo que podría ser intencional |
| [11-pruebas.md](11-pruebas.md) | Infraestructura pytest aislada, fixtures, pruebas existentes, estrategia por tipo de cambio | Vas a validar un cambio |
| [12-procedimiento-desarrollo.md](12-procedimiento-desarrollo.md) | **Procedimiento de 10 pasos**, matriz de autonomía, estrategia frontend/backend, mantenimiento | Siempre |
| [13-entorno-desarrollo-bd.md](13-entorno-desarrollo-bd.md) | Propuesta (no implementada) de aislamiento de MySQL por entorno | Vas a necesitar SQL real o escrituras en desarrollo |
| [auditoria/](auditoria/) | Instantáneas históricas de las fases 1 y 2 (no se editan) | Para rastrear el origen de un hallazgo |

## Fuentes de evidencia

- Código del repo (fuente primaria).
- `git log` y `git diff` (solo lectura).
- Logs locales en `logs/` (ignorados por git; contienen datos operativos reales).
- READMEs históricos en `readme/README_V*.md`: describen la **intención** de cada versión, no el comportamiento actual.
- App PyQt heredada en `../src`: solo para comparar reglas originales.
