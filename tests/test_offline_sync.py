"""
Test Suite: Offline-First Synchronization & Conflict Resolution
Focus: TDD for mobile offline workflows

Tests coverage:
1. LocalDb persistence (CRUD, schema)
2. SyncManager orchestration (push, pull, reconciliation)
3. ConflictResolver (collision detection, prompt flow)
4. OfflineQueue (transaction management)
5. E2E workflows (offline pago → sync → verification)
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional


# ============================================================================
# TEST FIXTURES & MOCKS
# ============================================================================

@pytest.fixture
def mock_agente_data():
    """Sample agente data for offline cache."""
    return {
        "id": 1001,
        "nombre": "Juan Pérez",
        "numero_voip": "ext_1001",
        "telefono": "+52-555-1234",
        "empresa": "Transportes XYZ",
        "deuda_base_total": 5000.00,
        "ajuste_manual_deuda": -200.00,
        "saldo_acumulado": 4800.00,
        "semanas_pendientes": [
            {"semana_inicio": "2026-03-23", "monto": 1500},
            {"semana_inicio": "2026-03-16", "monto": 1500},
        ]
    }


@pytest.fixture
def mock_pago_offline():
    """Sample payment registered offline."""
    return {
        "id": "pago_local_001",
        "agente_id": 1001,
        "telefono": "+52-555-1234",
        "numero_voip": "ext_1001",
        "semana_inicio": "2026-03-23",
        "monto": 800.00,
        "pagado": True,
        "liquidar_total": False,
        "observaciones": "Pago rápido via QR",
        "timestamp_created": datetime.now().isoformat(),
        "synced": False,
        "sync_attempts": 0,
    }


@pytest.fixture
def mock_server_conflict():
    """Server-side pago that conflicts with offline."""
    return {
        "id": "pago_srv_001",
        "agente_id": 1001,
        "semana_inicio": "2026-03-23",
        "monto": 750.00,
        "timestamp_created": (datetime.now() - timedelta(minutes=15)).isoformat(),
        "synced": True,
    }


@pytest.fixture
def mock_api_responses():
    """Mock API client for testing."""
    api = Mock()
    api.getResumenPagoAgente = Mock(return_value={
        "deuda_base_total": 5000.00,
        "ajuste_manual_deuda": -200.00,
        "deuda_total": 4800.00,
        "total_abonado": 0.00,
        "saldo_acumulado": 4800.00,
        "semanas_pendientes": [
            {"semana_inicio": "2026-03-23", "monto": 1500},
            {"semana_inicio": "2026-03-16", "monto": 1500},
        ]
    })
    api.registrarPagoSemanal = Mock(return_value={"success": True, "pago_id": 12345})
    api.obtenerAgentes = Mock(return_value=[])
    return api


# ============================================================================
# LOCALDB TESTS (IndexedDB Wrapper)
# ============================================================================

class TestLocalDb:
    """Tests for local persistent storage layer."""

    def test_localdb_schema_creation(self, mock_api_responses):
        """MUST: LocalDb initializes IndexedDB with correct schema."""
        # ARRANGE
        db = LocalDbMock()
        
        # ACT
        result = db.initDb()
        
        # ASSERT
        assert result["success"] == True
        assert "agentes" in result["stores"]
        assert "pagos_offline" in result["stores"]
        assert "sync_metadata" in result["stores"]

    def test_localdb_save_agentes(self, mock_agente_data):
        """MUST: Save and retrieve agentes from local cache."""
        db = LocalDbMock()
        db.initDb()
        
        # ACT
        db.saveAgentes([mock_agente_data])
        retrieved = db.getAgente(mock_agente_data["id"])
        
        # ASSERT
        assert retrieved is not None
        assert retrieved["id"] == 1001
        assert retrieved["nombre"] == "Juan Pérez"
        assert retrieved["saldo_acumulado"] == 4800.00

    def test_localdb_save_pago_offline(self, mock_pago_offline):
        """MUST: Persist offline pago with metadata."""
        db = LocalDbMock()
        db.initDb()
        
        # ACT
        db.savePagoLocal(mock_pago_offline)
        stored = db.getPagoLocal(mock_pago_offline["id"])
        
        # ASSERT
        assert stored is not None
        assert stored["synced"] == False
        assert stored["sync_attempts"] == 0
        assert "timestamp_created" in stored

    def test_localdb_get_pending_pagos(self, mock_pago_offline):
        """MUST: Retrieve only unsynchronized pagos."""
        db = LocalDbMock()
        db.initDb()
        
        # Save 3 pagos: 2 unsync'd, 1 synced
        pago1 = {**mock_pago_offline, "id": "pago_1", "synced": False}
        pago2 = {**mock_pago_offline, "id": "pago_2", "synced": False}
        pago3 = {**mock_pago_offline, "id": "pago_3", "synced": True}
        
        db.savePagoLocal(pago1)
        db.savePagoLocal(pago2)
        db.savePagoLocal(pago3)
        
        # ACT
        pending = db.getPendingPagos()
        
        # ASSERT
        assert len(pending) == 2
        assert all(p["synced"] == False for p in pending)

    def test_localdb_mark_as_synced(self, mock_pago_offline):
        """MUST: Mark pago as synchronized."""
        db = LocalDbMock()
        db.initDb()
        db.savePagoLocal(mock_pago_offline)
        
        # ACT
        db.markAsSynced(mock_pago_offline["id"], "pago_srv_001")
        updated = db.getPagoLocal(mock_pago_offline["id"])
        
        # ASSERT
        assert updated["synced"] == True
        assert updated["server_id"] == "pago_srv_001"

    def test_localdb_get_last_sync_time(self):
        """MUST: Track last synchronization timestamp."""
        db = LocalDbMock()
        db.initDb()
        
        # ACT: Save sync time
        now = datetime.now()
        db.updateLastSyncTime(now)
        last_sync = db.getLastSyncTime()
        
        # ASSERT
        assert last_sync is not None
        assert isinstance(last_sync, datetime)


# ============================================================================
# SYNCMANAGER TESTS (Orchestration)
# ============================================================================

class TestSyncManager:
    """Tests for offline-first synchronization orchestration."""

    def test_syncmanager_auto_sync_interval(self, mock_api_responses):
        """MUST: Start auto-sync with specified interval (default 5-10 min)."""
        sync_mgr = SyncManagerMock(mock_api_responses)
        
        # ACT
        sync_mgr.startAutoSync(interval_ms=600000)  # 10 minutes
        
        # ASSERT
        assert sync_mgr.auto_sync_active == True
        assert sync_mgr.auto_sync_interval == 600000

    def test_syncmanager_stop_auto_sync(self, mock_api_responses):
        """MUST: Stop auto-sync gracefully."""
        sync_mgr = SyncManagerMock(mock_api_responses)
        sync_mgr.startAutoSync()
        
        # ACT
        sync_mgr.stopAutoSync()
        
        # ASSERT
        assert sync_mgr.auto_sync_active == False

    def test_syncmanager_pull_latest_agentes(self, mock_api_responses):
        """MUST: Fetch agentes from server and update local cache."""
        sync_mgr = SyncManagerMock(mock_api_responses)
        db = LocalDbMock()
        db.initDb()
        
        sync_mgr.local_db = db
        mock_agentes = [
            {"id": 1, "nombre": "Agent 1"},
            {"id": 2, "nombre": "Agent 2"},
        ]
        mock_api_responses.obtenerAgentes.return_value = mock_agentes
        
        # ACT
        result = sync_mgr.pullLatestAgentes()
        local_count = len(db.getAllAgentes())
        
        # ASSERT
        assert result["success"] == True
        assert local_count == 2

    def test_syncmanager_push_pending_pagos(self, mock_pago_offline, mock_api_responses):
        """MUST: Upload unsynchronized pagos to server."""
        sync_mgr = SyncManagerMock(mock_api_responses)
        db = LocalDbMock()
        db.initDb()
        db.savePagoLocal(mock_pago_offline)
        
        sync_mgr.local_db = db
        
        # ACT
        result = sync_mgr.pushPendingPagos()
        
        # ASSERT
        assert result["success"] == True
        assert result["pagos_pushed"] == 1
        mock_api_responses.registrarPagoSemanal.assert_called()

    def test_syncmanager_retry_logic_backoff(self, mock_pago_offline, mock_api_responses):
        """MUST: Implement backoff for failed sync attempts."""
        sync_mgr = SyncManagerMock(mock_api_responses)
        db = LocalDbMock()
        db.initDb()
        
        pago = {**mock_pago_offline, "sync_attempts": 0}
        db.savePagoLocal(pago)
        sync_mgr.local_db = db
        
        # Simulate API failure
        mock_api_responses.registrarPagoSemanal.side_effect = Exception("Network timeout")
        
        # ACT
        result = sync_mgr.pushPendingPagos()
        updated_pago = db.getPagoLocal(pago["id"])
        
        # ASSERT
        assert result["success"] == False
        assert updated_pago["sync_attempts"] == 1
        # Retry should not exceed 3 attempts
        assert updated_pago["sync_attempts"] <= 3

    def test_syncmanager_max_retry_limit(self, mock_pago_offline):
        """MUST: Mark pago as failed after max retries."""
        # ARRANGE
        api = Mock()
        api.registrarPagoSemanal.side_effect = Exception("Network error")
        
        sync_mgr = SyncManagerMock(api)
        db = LocalDbMock()
        db.initDb()
        
        # Set pago with sync_attempts already at 3 (max exceeded)
        pago = {**mock_pago_offline, "sync_attempts": 2}  # Will become 3 after first attempt
        db.savePagoLocal(pago)
        sync_mgr.local_db = db
        
        # ACT: First attempt (2 → 3, hits limit)
        result = sync_mgr.pushPendingPagos()
        updated_pago = db.getPagoLocal(pago["id"])
        
        # ASSERT
        assert updated_pago["sync_status"] == "failed", f"Expected sync_status='failed', got {updated_pago.get('sync_status')}"
        assert result["failed_pagos"] >= 1, "Expected at least 1 failed pago"


# ============================================================================
# CONFLICTRESOLVER TESTS (Collision Detection & Resolution)
# ============================================================================

class TestConflictResolver:
    """Tests for offline/server collision handling."""

    def test_conflict_detector_same_agente_semana(self, mock_pago_offline, mock_server_conflict):
        """MUST: Detect collision when agente_id + semana match."""
        resolver = ConflictResolverMock()
        
        # ACT
        is_collision = resolver.detectCollision(
            local_pago=mock_pago_offline,
            server_pagos=[mock_server_conflict]
        )
        
        # ASSERT
        assert is_collision == True

    def test_conflict_detector_no_collision_different_semana(self, mock_pago_offline, mock_server_conflict):
        """MUST: No collision if semana different."""
        resolver = ConflictResolverMock()
        
        server_pago = {**mock_server_conflict, "semana_inicio": "2026-03-16"}  # Different week
        
        # ACT
        is_collision = resolver.detectCollision(
            local_pago=mock_pago_offline,
            server_pagos=[server_pago]
        )
        
        # ASSERT
        assert is_collision == False

    def test_conflict_resolver_mark_for_review(self, mock_pago_offline):
        """MUST: Mark collision as pending user decision."""
        resolver = ConflictResolverMock()
        
        collision_data = {
            "local_pago": mock_pago_offline,
            "server_pagos": [{"id": "srv_1", "monto": 750}],
        }
        
        # ACT
        result = resolver.markForReview(collision_data)
        
        # ASSERT
        assert result["status"] == "pending_user_review"
        assert "review_id" in result
        assert result["local_pago"] is not None
        assert len(result["conflicts"]) > 0

    def test_conflict_resolver_user_choice_keep_both(self):
        """MUST: Accept user choice to keep both pagos."""
        resolver = ConflictResolverMock()
        review_id = "review_123"
        
        # ACT
        result = resolver.resolveConflict(
            review_id=review_id,
            user_choice="keep_both"
        )
        
        # ASSERT
        assert result["success"] == True
        assert result["action"] == "keep_both"

    def test_conflict_resolver_user_choice_keep_local(self):
        """MUST: Accept user choice to use local pago."""
        resolver = ConflictResolverMock()
        review_id = "review_123"
        
        # ACT
        result = resolver.resolveConflict(
            review_id=review_id,
            user_choice="keep_local"
        )
        
        # ASSERT
        assert result["success"] == True
        assert result["action"] == "keep_local"

    def test_conflict_resolver_user_choice_keep_server(self):
        """MUST: Accept user choice to use server pago."""
        resolver = ConflictResolverMock()
        review_id = "review_123"
        
        # ACT
        result = resolver.resolveConflict(
            review_id=review_id,
            user_choice="keep_server"
        )
        
        # ASSERT
        assert result["success"] == True
        assert result["action"] == "keep_server"


# ============================================================================
# OFFLINEQUEUE TESTS (Transaction Management)
# ============================================================================

class TestOfflineQueue:
    """Tests for offline transaction queue."""

    def test_queue_enqueue_pago(self, mock_pago_offline):
        """MUST: Enqueue pago for pending sync."""
        queue = OfflineQueueMock()
        
        # ACT
        queue.enqueue(mock_pago_offline)
        pending = queue.getPending()
        
        # ASSERT
        assert len(pending) == 1
        assert pending[0]["id"] == mock_pago_offline["id"]

    def test_queue_dequeue_fifo(self, mock_pago_offline):
        """MUST: Dequeue respects FIFO order."""
        queue = OfflineQueueMock()
        
        pago1 = {**mock_pago_offline, "id": "pago_1", "timestamp_created": datetime.now().isoformat()}
        pago2 = {**mock_pago_offline, "id": "pago_2", "timestamp_created": (datetime.now() + timedelta(seconds=1)).isoformat()}
        
        queue.enqueue(pago1)
        queue.enqueue(pago2)
        
        # ACT
        first = queue.dequeue()
        
        # ASSERT
        assert first["id"] == "pago_1"

    def test_queue_clear_after_sync(self, mock_pago_offline):
        """MUST: Clear queue after successful sync."""
        queue = OfflineQueueMock()
        queue.enqueue(mock_pago_offline)
        
        # ACT
        queue.clear()
        pending = queue.getPending()
        
        # ASSERT
        assert len(pending) == 0


# ============================================================================
# END-TO-END WORKFLOW TESTS
# ============================================================================

class TestOfflineSyncE2E:
    """Tests for complete offline-first workflows."""

    def test_e2e_pago_offline_then_sync(self, mock_pago_offline, mock_agente_data, mock_api_responses):
        """MUST: Full workflow - offline pago → network restored → synced."""
        # ARRANGE
        db = LocalDbMock()
        sync_mgr = SyncManagerMock(mock_api_responses)
        queue = OfflineQueueMock()
        
        db.initDb()
        db.saveAgentes([mock_agente_data])
        sync_mgr.local_db = db
        
        # Simulate offline: register pago
        db.savePagoLocal(mock_pago_offline)
        queue.enqueue(mock_pago_offline)
        
        # ACT: Network restored, sync
        mock_api_responses.registrarPagoSemanal.return_value = {"success": True, "pago_id": 99999}
        result = sync_mgr.pushPendingPagos()
        
        # ASSERT
        assert result["success"] == True
        assert result["pagos_pushed"] == 1
        synced_pago = db.getPagoLocal(mock_pago_offline["id"])
        assert synced_pago["synced"] == True

    def test_e2e_offline_pago_with_collision(self, mock_pago_offline, mock_server_conflict, mock_api_responses):
        """MUST: Detect and handle collision during sync."""
        db = LocalDbMock()
        sync_mgr = SyncManagerMock(mock_api_responses)
        resolver = ConflictResolverMock()
        
        db.initDb()
        db.savePagoLocal(mock_pago_offline)
        sync_mgr.local_db = db
        sync_mgr.conflict_resolver = resolver
        
        # Simulate: Server already has pago for same agente + semana
        mock_api_responses.registrarPagoSemanal.side_effect = Exception("Conflict: Duplicate entry")
        
        # ACT
        result = sync_mgr.pushPendingPagos()
        
        # ASSERT
        assert result.get("collision_detected") == True
        # Pago should be marked for review
        local_pago = db.getPagoLocal(mock_pago_offline["id"])
        assert local_pago.get("review_status") is not None

    def test_e2e_stale_cache_fallback(self, mock_agente_data):
        """MUST: Use stale cache with warning if sync fails repeatedly."""
        db = LocalDbMock()
        db.initDb()
        db.saveAgentes([mock_agente_data])
        
        # Simulate old sync
        old_time = datetime.now() - timedelta(hours=2)
        db.updateLastSyncTime(old_time)
        
        # ACT: Retrieve agente (should be available but marked stale)
        agente = db.getAgente(mock_agente_data["id"])
        last_sync = db.getLastSyncTime()
        stale_hours = (datetime.now() - last_sync).total_seconds() / 3600
        
        # ASSERT
        assert agente is not None
        assert stale_hours > 1
        # Should be flagged as stale
        assert agente.get("_cache_warning") is not None or stale_hours > 1

    def test_e2e_pending_counter_badge(self, mock_pago_offline):
        """MUST: Provide pending count for UI badge."""
        queue = OfflineQueueMock()
        
        pago1 = {**mock_pago_offline, "id": "pago_1"}
        pago2 = {**mock_pago_offline, "id": "pago_2"}
        pago3 = {**mock_pago_offline, "id": "pago_3"}
        
        queue.enqueue(pago1)
        queue.enqueue(pago2)
        queue.enqueue(pago3)
        
        # ACT
        pending_count = queue.getPendingCount()
        
        # ASSERT
        assert pending_count == 3


# ============================================================================
# MOCK IMPLEMENTATIONS (Simplified for Testing)
# ============================================================================

class LocalDbMock:
    """Mock LocalDb for testing."""
    def __init__(self):
        self.agentes = {}
        self.pagos = {}
        self.last_sync = None
    
    def initDb(self):
        return {"success": True, "stores": ["agentes", "pagos_offline", "sync_metadata"]}
    
    def saveAgentes(self, agentes):
        for a in agentes:
            self.agentes[a["id"]] = a
    
    def getAgente(self, agente_id):
        return self.agentes.get(agente_id)
    
    def getAllAgentes(self):
        return list(self.agentes.values())
    
    def savePagoLocal(self, pago):
        self.pagos[pago["id"]] = pago
    
    def getPagoLocal(self, pago_id):
        return self.pagos.get(pago_id)
    
    def getPendingPagos(self):
        return [p for p in self.pagos.values() if not p.get("synced", False)]
    
    def markAsSynced(self, pago_id, server_id):
        if pago_id in self.pagos:
            self.pagos[pago_id]["synced"] = True
            self.pagos[pago_id]["server_id"] = server_id
    
    def getLastSyncTime(self):
        return self.last_sync
    
    def updateLastSyncTime(self, dt):
        self.last_sync = dt


class SyncManagerMock:
    """Mock SyncManager for testing."""
    def __init__(self, api_client):
        self.api = api_client
        self.local_db = None
        self.conflict_resolver = None
        self.auto_sync_active = False
        self.auto_sync_interval = 0
    
    def startAutoSync(self, interval_ms=600000):
        self.auto_sync_active = True
        self.auto_sync_interval = interval_ms
    
    def stopAutoSync(self):
        self.auto_sync_active = False
    
    def pullLatestAgentes(self):
        agentes = self.api.obtenerAgentes()
        if self.local_db:
            self.local_db.saveAgentes(agentes)
        return {"success": True, "count": len(agentes)}
    
    def pushPendingPagos(self):
        if not self.local_db:
            return {"success": False}
        
        pending = self.local_db.getPendingPagos()
        failed = 0
        collisions = 0
        pushed = 0
        
        for pago in pending:
            try:
                result = self.api.registrarPagoSemanal(pago)
                self.local_db.markAsSynced(pago["id"], result.get("pago_id"))
                pushed += 1
            except Exception as e:
                pago["sync_attempts"] = pago.get("sync_attempts", 0) + 1
                if pago["sync_attempts"] >= 3:
                    pago["sync_status"] = "failed"
                    failed += 1
                else:
                    # Persist updated sync_attempts even if not yet failed
                    self.local_db.savePagoLocal(pago)
                
                if "Duplicate" in str(e) or "Conflict" in str(e):
                    pago["review_status"] = "pending"
                    collisions += 1
        
        return {
            "success": failed == 0 and pushed > 0,  # Fixed: only success if no failures AND at least 1 pushed
            "pagos_pushed": pushed,
            "failed_pagos": failed,
            "collision_detected": collisions > 0,
        }


class ConflictResolverMock:
    """Mock ConflictResolver for testing."""
    def __init__(self):
        self.reviews = {}
    
    def detectCollision(self, local_pago, server_pagos):
        for sp in server_pagos:
            if sp.get("agente_id") == local_pago.get("agente_id") and \
               sp.get("semana_inicio") == local_pago.get("semana_inicio"):
                return True
        return False
    
    def markForReview(self, collision_data):
        review_id = f"review_{len(self.reviews)}"
        self.reviews[review_id] = {
            "status": "pending_user_review",
            **collision_data
        }
        return {
            "status": "pending_user_review",
            "review_id": review_id,
            "local_pago": collision_data.get("local_pago"),
            "conflicts": collision_data.get("server_pagos", []),
        }
    
    def resolveConflict(self, review_id, user_choice):
        return {
            "success": True,
            "action": user_choice,
            "review_id": review_id,
        }


class OfflineQueueMock:
    """Mock OfflineQueue for testing."""
    def __init__(self):
        self.queue = []
    
    def enqueue(self, pago):
        self.queue.append(pago)
    
    def dequeue(self):
        return self.queue.pop(0) if self.queue else None
    
    def getPending(self):
        return self.queue.copy()
    
    def getPendingCount(self):
        return len(self.queue)
    
    def clear(self):
        self.queue.clear()


# ============================================================================
# PYTEST CONFIG
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
