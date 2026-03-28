# CHECKPOINT PRE-IMPLEMENTACIÓN: Offline-First + Sincronización Automática

**Fecha:** 2026-03-26  
**Fase:** Diseño Arquitectónico - Offline-First & Sync  
**Estado:** 🔵 PRE-CAMBIOS (Validación de Riesgos)

---

## Objetivo

Permitir que la **aplicación móvil procese pagos en modo offline**, guardando datos esenciales localmente, y sincronizando automáticamente con el servidor cuando hay conexión.

**User Story:**
> "Necesito, si es posible, que en la aplicación se guarde parte de la página para que pueda procesar pagos y en cuanto detecte el servidor sincronice la información."

---

## Alcance Confirmado

### Datos a Guardar (IndexedDB)
- **Agentes:** ID, nombre, teléfono, empresa, estatus_agente
- **Deuda/Saldo Actual:** deuda_base_total, ajuste_manual_deuda, saldo_acumulado
- **2 Últimas Semanas:** resúmenes de pagos (para contexto histórico)
- **Semana Actual:** para permitir altas rápidas

**Exclusiones Deliberadas:**
- Catálogos completos (LADAS, líneas, etc.) - se cachean del GET anterior
- Historial completo de pagos - demasiado volumen
- Datos de otros usuarios - cada sesión re-sincroniza

### Estrategia de Sincronización
- **Trigger Automático:** Cada 5-10 minutos (si hay conexión)
- **Trigger Manual:** Botón "Sincronizar ahora" en UI
- **Fallback:** Cache local antiguo si sincronización falla (con advertencia de timestamp)

### Manejo de Conflictos
**Escenario de Colisión:** Mismo agente, pago registrado offline + otro en servidor
- **Acción:** Guardar ambos, alertar usuario para resolución manual
- **Lógica:** Check de `agente_id + semana` → si existe, marcar como pendiente de revisión

### Alertas
- **Urgencia:** Banner discreto en barra de estado (no invasivo)
- **Contenido:** "X pagos pendientes de sincronizar" con badge contador
- **Acción:** Clic en banner → manual sync o fallback a background

---

## Arquitectura Propuesta

```
web/m/
├── index.html                    # UI: agregar control de sincronización
├── mobile.js                     # Orquestación
├── lib/
│   ├── localdb.js               # ⭐ NUEVA: IndexedDB wrapper
│   ├── syncmanager.js           # ⭐ NUEVA: Lógica de sincronización
│   ├── conflictresolver.js      # ⭐ NUEVA: Resolución de colisiones
│   └── offlinequeue.js          # ⭐ NUEVA: Cola de transacciones
└── mobile.css                    # Estilos

tests/
└── test_offline_sync.py          # ⭐ NUEVA: Tests de sincronización & conflictos
```

### Módulos Clave

#### 1. **LocalDb (localdb.js)**
```javascript
class LocalDb {
  - initDb()                      // Crear schema IndexedDB
  - getAgente(id)                // Buscar agente localmente
  - saveAgentes(data)            // Bulk insert agentes
  - savePagoLocal(pago)          // Guardar pago offline
  - getPendingPagos()            // Obtener pagos sin sincronizar
  - markAsSynced(pagoId)         // Marcar como sincronizado
  - getLastSyncTime()            // Timestamp de última sincronización
}
```

#### 2. **SyncManager (syncmanager.js)**
```javascript
class SyncManager {
  - startAutoSync(intervalMs)    // Inicia sincronización cada N ms
  - stopAutoSync()               // Detiene sync automático
  - syncNow()                    // Sincronización manual inmediata
  - pushPendingPagos()           // Envía pagos locales al servidor
  - pullLatestAgentes()          // Obtiene agentes frescos desde API
  - reconcilePagos()             // Detecta conflictos
}
```

#### 3. **ConflictResolver (conflictresolver.js)**
```javascript
class ConflictResolver {
  - detectCollision(pago)        // ¿Existe duplicado en servidor?
  - markForReview(pago)          // Marcar para revisión manual
  - getUserPrompt()              // Modal: "¿Cuál pago es correcto?"
  - resolveConflict(choice)      // Aplicar decisión del usuario
}
```

#### 4. **OfflineQueue (offlinequeue.js)**
```javascript
class OfflineQueue {
  - enqueue(pago)                // Agregar pago a cola
  - dequeue()                    // Obtener próximo pendiente
  - getPending()                 // Listado completo pendientes
  - Clear()                      // Limpiar después de sync exitoso
}
```

---

## Riesgos Identificados y Mitigaciones

| Riesgo | Severidad | Mitigación |
|--------|-----------|-----------|
| **Data Stale:** Cache desactualizado por >1 hora | ALTA | Marcar con timestamp; refrescar mín cada 10 min; alerta si >1h sin sync |
| **Duplicado de Pagos:** Usuario registra offline + servidor | ALTA | Detector de colisión (agente_id + semana) → prompt de resolución |
| **Storage Lleno:** IndexedDB quota excedida | MEDIA | Limpiar pagos sincronizados >30 días; monitorear cuota |
| **Sync Loop INFINITO:** Servidor rechaza pago, loop de reintentos | MEDIA | Max 3 reintentos; backoff exponencial; log de error |
| **Red Inestable:** Conectividad intermitente durante sync | MEDIA | Transacciones atómicas; rollback si falla; alertar estado |
| **Usuario ignora aviso:** No sincroniza en horas | BAJA | Banner persistente; contador de pendientes visible |

---

## Plan de Implementación (TDD)

### Fase 1: Tests & Schema (TDD)
- ✅ Escribir tests para LocalDb (CRUD, schema validation)
- ✅ Escribir tests para SyncManager (push/pull/reconciliation)
- ✅ Escribir tests para ConflictResolver (detección, resolución)
- ✅ Escribir tests E2E: offline → pago → sync → online ✓ verifica reconciliación

### Fase 2: Implementación (TDD Green)
- Implementar `localdb.js` (IndexedDB wrapper)
- Implementar `syncmanager.js` (orquestación)
- Implementar `conflictresolver.js` (colisiones)
- Implementar `offlinequeue.js` (persistencia de transacciones)

### Fase 3: Integración Móvil
- Modificar `mobile.js` para inicializar SyncManager
- Agregar eventos de conectividad (online/offline)
- Conectar pagosView al OfflineQueue (fallback)
- Agregar UI: banner de sincronización + estado

### Fase 4: Validación
- ✅ Todos los tests PASS (coverage >85%)
- ✅ Prueba manual: offline → pago → sync → verificar en servidor
- ✅ Prueba: colisión detectada + resolución usuario
- ✅ Prueba: storage quota no excedida

---

## Cambios a Archivos Existentes

| Archivo | Cambios | Líneas Aprox |
|---------|---------|-------------|
| `web/m/index.html` | Agregar control de sincronización (badge, btn manual) | +20 |
| `web/m/mobile.js` | Inicializar SyncManager; eventos online/offline | +100 |
| `web/m/mobile.css` | Estilos para banner sync + modal conflicto | +40 |
| `tests/test_api.py` | E2E test: offline sync workflow | +50 |

**Nuevos Archivos Creados:**
- `web/m/lib/localdb.js` (~200 líneas)
- `web/m/lib/syncmanager.js` (~250 líneas)
- `web/m/lib/conflictresolver.js` (~150 líneas)
- `web/m/lib/offlinequeue.js` (~100 líneas)
- `tests/test_offline_sync.py` (~200 líneas)

---

## Aceptación

- [ ] Diseño arquitectónico revisado y aprobado
- [ ] Tests escritos ANTES de implementación (TDD)
- [ ] Riesgos identificados y mitigaciones claras
- [ ] Estimación: ~8-10 horas de desarrollo
- [ ] Proceder a Fase 1: Escribir Tests

**Bloqueador ninguno. Proceder con implementación.**

---

**Próximo Checkpoint:** `CHECKPOINT_ARQUITECTURA_2026-03-26_OFFLINE_SYNC_CIERRE.md`
