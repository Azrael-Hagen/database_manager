# Guía Fase B & Tablero de Salud - Migración y Diagnóstico

**Fecha**: 2026-03-24  
**Estado**: Listo para uso  
**Aplicabilidad**: Post Fase A (Estabilización de Alias y Sync)

---

## 🎯 Objetivo General

Esta guía documenta dos herramientas complementarias:

1. **Migración Fase B**: Normalizar columnas `alias`, `ubicación`, `fp`, `fc`, `grupo`, `numero_voip` desde JSON a columnas dedicadas de `datos_importados`
2. **Tablero de Salud SQL**: Diagnosticar integridad, duplicados, desalineación y anomalías en toda la base de datos

Ambas herramientas están diseñadas para ser **seguras, reversibles y monitoreadas**.

---

## 📋 Requisitos Previos

### Antes de ejecutar cualquier script:

1. **Backup de la BD**:
```bash
# Windows (PowerShell)
mysqldump -u root -proot database_manager > backup_database_manager_$(Get-Date -f 'yyyyMMdd_HHmmss').sql

# En caso de error, restaurar:
mysql -u root -proot database_manager < backup_database_manager_20260324_120000.sql
```

2. **Verificar estado actual**:
```bash
# Primero, ejecutar Tablero de Salud para diagnóstico inicial
python backend/scripts/health_check_dashboard.py
```

3. **Credenciales y acceso**:
- Usuario MySQL: `root` / `root` (ajustar en scripts si es diferente)
- Acceso local a BD principal: `database_manager`
- Acceso local a BD legacy (opcional): `registro_agentes`

4. **Python y dependencias**:
```bash
# Asegurar que está en entorno correcto
pip list | grep sqlalchemy  # Debe estar instalado
```

---

## 🔍 Parte 1: Tablero de Salud SQL (PRE-MIGRACIÓN)

### ¿Qué hace?

Diagnostica la integridad actual de la BD detectando:
- **Duplicados**: Registros con email/teléfono duplicados
- **Huérfanos**: Agentes sin líneas asignadas
- **Desalineación Legacy**: Diferencias entre `database_manager` y `registro_agentes`
- **JSON corrupto**: Datos_adicionales con JSON inválido
- **QR Status**: Seguimiento de impresión de QR
- **Pagos anómalos**: Registros inconsistentes en pagos semanales
- **Asignaciones rotas**: Líneas sin agente, agentes sin línea
- **Auditoría**: Historial de cambios recientes

### Ejecución - Opción A (Recomendado: Entorno Local)

```bash
# Terminal en workspace
cd c:\Users\Azrael\OneDrive\Documentos\Herramientas\database_manager

# Ejecutar tablero
python backend/scripts/health_check_dashboard.py
```

**Salida esperada**:
```
================================================================================
TABLERO DE SALUD SQL - DIAGNÓSTICO DE INTEGRIDAD
================================================================================
✓ Conexión a BD principal exitosa
✓ Conexión a BD legacy exitosa

[1/8] VERIFICANDO DUPLICADOS...
[2/8] VERIFICANDO REGISTROS HUÉRFANOS...
[3/8] VERIFICANDO DESALINEACIÓN CON LEGACY...
[4/8] VERIFICANDO INTEGRIDAD JSON...
[5/8] VERIFICANDO STATUS QR...
[6/8] VERIFICANDO PAGOS SEMANALES...
[7/8] VERIFICANDO ASIGNACIONES DE LÍNEA...
[8/8] VERIFICANDO AUDITORÍA...

✓ BASE DE DATOS EN BUEN ESTADO
Reporte completo: c:\...\logs\health_check_20260324_120000.log
```

### Ejecución - Opción B (Usando SQL directo)

Si prefieres ejecutar consultas manualmente en MySQL Workbench/CLI:

```sql
-- 1. DUPLICADOS POR EMAIL
SELECT 
    email, 
    COUNT(*) as cantidad,
    GROUP_CONCAT(id) as ids,
    GROUP_CONCAT(nombre) as nombres
FROM database_manager.datos_importados
WHERE email IS NOT NULL AND email != ''
GROUP BY email
HAVING COUNT(*) > 1
ORDER BY cantidad DESC;

-- 2. AGENTES SIN LÍNEAS
SELECT 
    d.id, d.nombre, d.email,
    COUNT(ala.id) as num_lineas
FROM database_manager.datos_importados d
LEFT JOIN database_manager.agente_linea_asignaciones ala 
    ON d.id = ala.agente_id AND ala.es_activa = TRUE
WHERE d.es_activo = TRUE
GROUP BY d.id
HAVING num_lineas = 0;

-- 3. INTEGRIDAD JSON
SELECT 
    COUNT(*) as total,
    SUM(IF(datos_adicionales IS NULL, 1, 0)) as sin_json,
    SUM(IF(JSON_VALID(datos_adicionales) = 1, 1, 0)) as json_valido,
    SUM(IF(JSON_VALID(datos_adicionales) = 0 AND datos_adicionales IS NOT NULL, 1, 0)) as json_invalido
FROM database_manager.datos_importados;

-- 4. DESALINEACIÓN CON LEGACY
SELECT di.id, di.nombre, di.email
FROM database_manager.datos_importados di
LEFT JOIN registro_agentes.agentes ra ON di.id = ra.id
WHERE ra.id IS NULL AND di.es_activo = TRUE
LIMIT 20;

-- 5. PROBLEMAS DE PAGOS
SELECT ps.id, ps.agente_id, ps.semana_inicio, ps.monto
FROM database_manager.pagos_semanales ps
LEFT JOIN database_manager.datos_importados di ON ps.agente_id = di.id
WHERE di.id IS NULL
LIMIT 20;
```

### Interpretar Resultados

| Problemas | Severidad | Acción Recomendada |
|-----------|-----------|-------------------|
| **Duplicados email/teléfono** | 🔴 ALTA | Consolidar antes de normalizar. Asignar líneas al "principal". |
| **Agentes sin líneas** | 🟡 MEDIA | Documentar; asignar líneas o marcar como inactivos. |
| **JSON corrupto** | 🔴 ALTA | Investigar en logs; reparar manualmente si es crítico. |
| **Desalineación legacy** | 🟡 MEDIA | Sincronizar manualmente; refuerza necesidad de Fase B. |
| **Pagos anómalos** | 🔴 ALTA | Revisar integridad de pagos_semanales antes de continuar. |

---

## 🚀 Parte 2: Migración Fase B (Normalización de Columnas)

### ¿Qué hace?

1. Agrega 6 nuevas columnas a `datos_importados`:
   - `alias` (VARCHAR 255)
   - `ubicacion` (VARCHAR 255)
   - `fp` (VARCHAR 100) — Fecha de início
   - `fc` (VARCHAR 100) — Fecha de conclusión
   - `grupo` (VARCHAR 100)
   - `numero_voip` (VARCHAR 50)

2. **Extrae datos** desde JSON `datos_adicionales` hacia columnas
3. **Crea índices** en `alias`, `grupo`, `numero_voip` para performance
4. **Valida integridad** post-migración
5. **Permite rollback** automático en caso de error

### Riesgos Mitigados

| Riesgo | Mitigación |
|--------|-----------|
| Pérdida de datos | Backup automático + validación post-migración |
| Downtime | Migración sin bloqueo; transacciones atomizadas |
| Incompatibilidad | JSON sigue siendo accesible; nuevas columnas son complementarias |
| Corrupción | Rollback automático si validación falla |

### Ejecución - Paso a Paso

#### Paso 1: Diagnosis (Pre-migración)

```bash
# Ejecutar tablero de salud PRIMERO
python backend/scripts/health_check_dashboard.py

# Guardar el log para referencia:
# logs/health_check_20260324_120000.log
```

Revisar que NO hay:
- Duplicados críticos
- JSON corrupto significativo
- Pagos anómalos

#### Paso 2: Backup (CRÍTICO)

```bash
# PowerShell
$timestamp = Get-Date -f 'yyyyMMdd_HHmmss'
mysqldump -u root -proot database_manager > "backup_prePhaseB_$timestamp.sql"

# Verificar tamaño
ls -la "backup_prePhaseB_$timestamp.sql"
# Debería ser > 1MB (signo de datos)

# En caso de necesidad de rollback:
# mysql -u root -proot database_manager < backup_prePhaseB_20260324_120000.sql
```

#### Paso 3: Ejecutar Migración

```bash
# Desde workspace root
python backend/scripts/migrate_phase_b_normalize_columns.py
```

**Salida esperada**:

```
================================================================================
MIGRACIÓN FASE B - NORMALIZACIÓN DE COLUMNAS
================================================================================

FASE 1: VALIDACIÓN
--------------------------------------------------------------------------------
✓ Conexión a BD exitosa
✓ Tabla 'datos_importados' existe
✓ Todas las 6 columnas aún no existen
✓ Validación JSON: 500 registros analizados, 0 errores de parseo
  Cobertura de datos:
    - alias: 450/500 registros
    - ubicacion: 400/500 registros
    - fp: 380/500 registros
    - fc: 375/500 registros
    - grupo: 420/500 registros
    - numero_voip: 495/500 registros

FASE 2: BACKUP Y MIGRACIÓN
--------------------------------------------------------------------------------
✓ Backup creado: logs/backup_datos_adicionales_20260324_120000.json (500 registros)
✓ Columna 'alias' agregada
✓ Columna 'ubicacion' agregada
✓ Columna 'fp' agregada
✓ Columna 'fc' agregada
✓ Columna 'grupo' agregada
✓ Columna 'numero_voip' agregada
Iniciando migración de 500 registros...
  Procesados 100/500 registros...
  Procesados 200/500 registros...
  Procesados 300/500 registros...
  Procesados 400/500 registros...
✓ Migración completada: 500 actualizados, 0 errores
✓ Índice 'ix_datos_importados_alias' creado
✓ Índice 'ix_datos_importados_grupo' creado
✓ Índice 'ix_datos_importados_numero_voip' creado

FASE 3: VALIDACIÓN POST-MIGRACIÓN
--------------------------------------------------------------------------------
✓ Validación post-migración:
  - Total de registros: 500
  - Con alias: 450
  - Con ubicación: 400
  - Con grupo: 420
  - Con número VoIP: 495

================================================================================
✓ MIGRACIÓN FASE B COMPLETADA EXITOSAMENTE
================================================================================
Log: logs/migration_phase_b_20260324_120000.log
Backup: logs/backup_datos_adicionales_20260324_120000.json
```

#### Paso 4: Validación Post-Migración

```bash
# Tests unitarios
python -m pytest tests/test_migration_phase_b.py -v

# Salida esperada: 10-15 tests passed
```

Consulta SQL manual:
```sql
-- Verificar que columnas existen y tienen datos
SELECT 
    COUNT(*) as total,
    SUM(IF(alias IS NOT NULL, 1, 0)) as con_alias,
    SUM(IF(grupo IS NOT NULL, 1, 0)) as con_grupo,
    SUM(IF(numero_voip IS NOT NULL, 1, 0)) as con_voip
FROM database_manager.datos_importados;

-- Resultado esperado:
-- total | con_alias | con_grupo | con_voip
-- 500   |   450     |   420     |   495
```

#### Paso 5: Actualizar ORM y Modelos (Post-migración)

Una vez que la migración es exitosa, actualizar `backend/app/models.py`:

```python
# En la clase DatoImportado, agregue las nuevas columnas:
alias = Column(String(255), index=True, nullable=True)
ubicacion = Column(String(255), nullable=True)
fp = Column(String(100), nullable=True)  # Fecha inicio prestación
fc = Column(String(100), nullable=True)  # Fecha conclusión
grupo = Column(String(100), index=True, nullable=True)
numero_voip = Column(String(50), index=True, nullable=True)
```

Luego:**No necesario re-crear tablas** (las columnas ya existen).

#### Paso 6: Rollback (Si es necesario)

Si algo falla y necesitas revertir:

```bash
# Opción 1: Restaurar backup
mysql -u root -proot database_manager < backup_prePhaseB_20260324_120000.sql

# Opción 2: El script intenta rollback automático
# (ver logs/migration_phase_b_20260324_120000.log para detalles)
```

---

## 💡 Fase B: Casos de Uso Post-Migración

### Query 1: Búsqueda por Alias (ANTES vs DESPUÉS)

```sql
-- ANTES (búsqueda en JSON):
SELECT * FROM datos_importados
WHERE JSON_EXTRACT(datos_adicionales, '$.alias') = 'ALIAS_BUSCADO';

-- DESPUÉS (búsqueda indexada, rápida):
SELECT * FROM datos_importados
WHERE alias = 'ALIAS_BUSCADO';
-- ✓ Usa índice, mucho más rápido en BD grande
```

### Query 2: Reportes por Grupo

```sql
-- Contar agentes por grupo
SELECT grupo, COUNT(*) as cantidad
FROM datos_importados
WHERE es_activo = TRUE
GROUP BY grupo
ORDER BY cantidad DESC;
```

### Query 3: Auditoría de asignaciones

```sql
-- Agentes sin grupo asignado
SELECT id, nombre, email
FROM datos_importados
WHERE grupo IS NULL AND es_activo = TRUE;
```

---

## 📊 Monitoreo Post-Migración

### Logs a revisar:

```bash
# Migración
logs/migration_phase_b_YYYYMMDD_HHMMSS.log

# Salud post
logs/health_check_YYYYMMDD_HHMMSS.log

# Backup
logs/backup_datos_adicionales_YYYYMMDD_HHMMSS.json
```

### Métricas a vigilar (24-48h post-migración):

```sql
-- Latencia de queries (debería mejorar):
SELECT 
    alias, COUNT(*) 
FROM datos_importados 
GROUP BY alias 
LIMIT 100;
-- Tiempo esperado: <100ms (antes era >500ms en JSON)

-- Cobertura de datos:
SELECT 
    ROUND(SUM(IF(alias IS NOT NULL, 1, 0))*100/COUNT(*), 2) as pct_alias,
    ROUND(SUM(IF(grupo IS NOT NULL, 1, 0))*100/COUNT(*), 2) as pct_grupo
FROM datos_importados;
```

---

## ❌ Troubleshooting

### Error: "Column 'alias' already exists"

```bash
# → Las columnas ya fueron creadas. Verificar:
SELECT * FROM information_schema.columns
WHERE table_name = 'datos_importados' AND column_name = 'alias';

# Si existen, saltarse la migración o hacer rollback primero.
```

### Error: "JSON_VALID() is not a function"

```bash
# → Base de datos MySQL < 5.7. Actualizar MySQL o usar:
SELECT * FROM datos_importados 
WHERE datos_adicionales LIKE '{%}';  # Fallback simple
```

### Error de Rollback fallido:

```bash
# → Las columnas no se pueden eliminar (acaso algún índice?).
# Rollback manual:
mysql -u root -proot database_manager < backup_prePhaseB_20260324_120000.sql
```

---

## 🔒 Guía de Seguridad

### Cuándo NO ejecutar:

- ❌ Durante horario pico (datos siendo modificados)
- ❌ Si BD legacy está inactiva (sin verificar primero)
- ❌ Sin backup previo
- ❌ Con conexiones activas (otros usuarios en UI)

### Cuándo SÍ es seguro:

- ✅ Noche/fin de semana (bajo uso)
- ✅ Con equipo de respaldo disponible (en caso de rollback)
- ✅ Después de backup confirmado
- ✅ Después de health check verde

---

## 📝 Checklist Final

Antes de considerar Fase B completada:

- [ ] Ejecutar tablero de salud PRE-migración
- [ ] Revisar resultados; resolver críticos
- [ ] Hacer backup completo
- [ ] Ejecutar script de migración
- [ ] Verificar NO hay "ROLLBACK" en logs
- [ ] Ejecutar tests: `pytest tests/test_migration_phase_b.py -v`
- [ ] Validación SQL post-migración OK
- [ ] Ejecutar tablero de salud POST-migración
- [ ] Actualizar ORM en models.py
- [ ] Reiniciar backend
- [ ] Hacer prueba manual en UI: buscar por alias
- [ ] Documentar rollback procedure en runbook
- [ ] Comunicar cambio a equipo

---

## 🎓 Referencia Rápida

| Script | Propósito | Duración | Riesgo |
|--------|-----------|----------|--------|
| `health_check_dashboard.py` | Diagnóstico | 2-5 min | ✅ Nulo (read-only) |
| `migrate_phase_b_normalize_columns.py` | Normalización | 5-30 min | 🔴 Alto (DDL+DML) |
| `test_migration_phase_b.py` | Validación | 1-2 min | ✅ Nulo (test DB) |

---

**Autor**: Database Architect  
**Revisión**: 2026-03-24  
**Estado**: Listo para Fase B
