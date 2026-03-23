-- ============================================================
-- Script de mantenimiento inicial - database_manager
-- EJECUTADO: 2025-01-22 via tmp/mantenimiento.py (Python/SQLAlchemy)
-- Conservar como referencia. No volver a ejecutar.
-- ============================================================

USE database_manager;

-- 1. Eliminar registros de test E2E (ids 33, 34, 36, 38)
DELETE FROM datos_importados
WHERE id IN (33, 34, 36, 38)
  AND (email LIKE 'e2e_%@example.com'
       OR email LIKE 'fix_%@example.com'
       OR email LIKE 'fix2_%@example.com');

-- 2. Activar todos los 44 agentes inactivos (son agentes reales importados)
UPDATE datos_importados
SET es_activo = 1
WHERE es_activo = 0
  AND id NOT IN (33, 34, 36, 38);   -- precaución por si ya se eliminaron

-- 3. Eliminar usuario de prueba (test_user / test@test.com)
DELETE FROM usuarios
WHERE id = 4
  AND (username = 'test_user' OR email = 'test@test.com');

-- 4. Sincronizar activaciones a registro_agentes.agentes (módulo legacy)
--    Marca los mismos agentes como activos en la BD legado
UPDATE registro_agentes.agentes ra
    INNER JOIN database_manager.datos_importados di ON ra.ID = di.id
SET ra.es_activo = 1
WHERE di.es_activo = 1;

-- 5. Eliminar agentes test del legado
DELETE FROM registro_agentes.agentes
WHERE ID IN (33, 34, 36, 38);

-- Verificación final
SELECT 'datos_importados activos' AS tabla, COUNT(*) AS total
  FROM datos_importados WHERE es_activo = 1
UNION ALL
SELECT 'datos_importados inactivos', COUNT(*)
  FROM datos_importados WHERE es_activo = 0
UNION ALL
SELECT 'usuarios activos', COUNT(*)
  FROM usuarios WHERE es_activo = 1;
