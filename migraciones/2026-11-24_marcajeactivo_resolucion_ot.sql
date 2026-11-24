-- =====================================================================
-- Migración: OT y tarea fijadas al abrir un marcaje (iteración 3)
-- Diseño: docs/ai/14-resolucion-ot.md §2.4 · Decisiones: P-18, P-19
-- Base de datos: SOLO smartfactory (P-18, 2026-11-24)
-- Ejecuta: el usuario (el asistente no se conecta a MySQL)
--
-- Compatibilidad: todas las columnas son NULL y van al final. El código
-- actual usa listas de columnas explícitas en sus INSERT y SELECT sobre
-- marcajeactivo, así que la migración puede aplicarse ANTES de desplegar
-- el código de la iteración 4 sin cambiar el comportamiento.
-- Las filas ya existentes quedan con estadoResolucion = NULL: el cierre
-- las tratará con el cálculo anterior (_obtener_wo_tk), P-19.
-- =====================================================================

-- 1. ANTES: comprobar el estado actual (debe devolver 0 filas)
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'smartfactory'
  AND TABLE_NAME = 'marcajeactivo'
  AND COLUMN_NAME IN ('wo_number', 'tk_id', 'estadoResolucion', 'tituloOt');

-- 2. MIGRACIÓN
ALTER TABLE smartfactory.marcajeactivo
  ADD COLUMN wo_number        INT         NULL COMMENT 'OT asignada al abrir (Optimus wo.wo_number)',
  ADD COLUMN tk_id            INT         NULL COMMENT 'Tarea asignada al abrir (Optimus wo_task200.tk_id)',
  ADD COLUMN estadoResolucion VARCHAR(12) NULL COMMENT 'AUTOMATICA | ELEGIDA | SIN_TAREA; NULL = abierto antes de la iteración 4',
  ADD COLUMN tituloOt         VARCHAR(60) NULL COMMENT 'Copia de wo.wo_title2 al abrir';

-- 3. DESPUÉS: verificar (debe devolver las 4 columnas, todas YES en IS_NULLABLE)
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'smartfactory'
  AND TABLE_NAME = 'marcajeactivo'
  AND COLUMN_NAME IN ('wo_number', 'tk_id', 'estadoResolucion', 'tituloOt')
ORDER BY ORDINAL_POSITION;

-- =====================================================================
-- REVERSA (solo si hay que deshacer; con el código de la iteración 4
-- desplegado, primero hay que volver a la versión anterior del código)
-- =====================================================================
-- ALTER TABLE smartfactory.marcajeactivo
--   DROP COLUMN tituloOt,
--   DROP COLUMN estadoResolucion,
--   DROP COLUMN tk_id,
--   DROP COLUMN wo_number;
