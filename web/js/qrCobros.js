/**
 * qrCobros.js — QR y Cobros section helpers
 *
 * Provides:
 *   - qrSetTab(tab)       — tab switching in #qrSection
 *   - qrSyncContext()     — shared agent/week context bar → pre-fills all sub-forms + badge
 *   - qrToggleCamera()    — smart start/stop camera toggle for #qrScanSection
 */

'use strict';

// ---------------------------------------------------------------------------
// Tab switcher
// ---------------------------------------------------------------------------

const _QR_TABS = ['pago', 'reporte', 'comprobantes', 'exportar', 'config'];

function qrSetTab(tab) {
    _QR_TABS.forEach(t => {
        const cap     = t.charAt(0).toUpperCase() + t.slice(1);
        const panel   = document.getElementById('qrTab' + cap);
        const btn     = document.getElementById('qrTab' + cap + 'Btn');
        const active  = t === tab;
        if (panel) panel.style.display = active ? '' : 'none';
        if (btn)   btn.classList.toggle('active', active);
    });

    // Lazy-load data for the activated tab
    if (tab === 'reporte') {
        _qrLazyReporte();
    } else if (tab === 'comprobantes') {
        if (typeof cargarRecibosPersistidos === 'function') cargarRecibosPersistidos();
    }
}

function _qrLazyReporte() {
    const container = document.getElementById('reporteSemanalContainer');
    // Only reload if empty (not yet loaded this session)
    const isEmpty = container && container.innerHTML.trim() === '';
    if (isEmpty && typeof cargarReporteSemanal === 'function') {
        cargarReporteSemanal();
    }
    const opView = document.getElementById('agentesEstadoPagoContainer');
    if (opView && opView.innerHTML.trim() === '' && typeof cargarVistaAgentesPago === 'function') {
        cargarVistaAgentesPago();
    }
}

// ---------------------------------------------------------------------------
// Shared context bar
// ---------------------------------------------------------------------------

function qrSyncContext() {
    const agenteId = (document.getElementById('qrCtxAgenteId')?.value || '').trim();
    const semana   = document.getElementById('qrCtxSemana')?.value  || '';
    const voip     = (document.getElementById('qrCtxVoip')?.value   || '').trim();

    if (!agenteId) {
        alert('Ingresa el ID del agente en la barra de contexto.');
        return;
    }

    // --- Sync agent ID ---
    ['qrAgenteId', 'pagoAgenteId', 'deudaManualAgenteId'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = agenteId;
    });

    // --- Sync week ---
    if (semana) {
        ['qrSemana', 'pagoSemana', 'deudaManualSemana', 'reporteSemanaInput'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = semana;
        });
    }

    // --- Sync VoIP ---
    if (voip) {
        ['qrVoip', 'pagoVoip'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = voip;
        });
    }

    // --- Badge: loading state ---
    const badge = document.getElementById('qrCtxBadge');
    if (badge) {
        badge.textContent = '…';
        badge.style.background = '#8899aa';
        badge.style.color = '#fff';
    }

    // --- Trigger existing verificarAgenteQR to update the verification panel ---
    if (typeof verificarAgenteQR === 'function') {
        verificarAgenteQR();
    }

    // --- Update badge from payment summary ---
    _qrCtxUpdateBadge(agenteId, semana);
}

async function _qrCtxUpdateBadge(agenteId, semana) {
    const badge = document.getElementById('qrCtxBadge');
    if (!badge) return;
    try {
        const params = semana ? `?semana=${encodeURIComponent(semana)}` : '';
        const data   = await fetchJson(`${API_URL}/qr/pagos/resumen/${agenteId}${params}`, {
            headers: { Authorization: `Bearer ${authToken}` },
        });

        const pagado = data?.pagado === true || data?.estado === 'pagado';
        const deuda  = parseFloat(data?.deuda_acumulada ?? data?.deuda ?? 0);

        if (pagado && deuda <= 0) {
            badge.textContent   = '✓ Al corriente';
            badge.style.background = '#16966a';
        } else if (deuda > 0) {
            badge.textContent   = `⚠ Debe $${deuda.toFixed(0)}`;
            badge.style.background = '#d64545';
        } else {
            badge.textContent   = data?.estado || 'Sin deuda';
            badge.style.background = '#4a90d9';
        }
        badge.style.color = '#fff';
    } catch (_) {
        if (badge) {
            badge.textContent   = 'Sin datos';
            badge.style.background = '#8899aa';
        }
    }
}

// ---------------------------------------------------------------------------
// Camera toggle
// ---------------------------------------------------------------------------

let _qrCameraRunning = false;
let _qrSearchDebounceTimer = null;
let _qrLastSearchQuery = '';

function qrToggleCamera() {
    const btn = document.getElementById('qrCameraToggleBtn');
    if (_qrCameraRunning) {
        // Stop
        if (typeof detenerEscanerQR === 'function') detenerEscanerQR();
        _qrCameraRunning = false;
        if (btn) {
            btn.textContent = '📷 Iniciar Cámara';
            btn.classList.remove('scanning');
        }
    } else {
        // Start
        if (typeof iniciarEscanerQR === 'function') iniciarEscanerQR();
        _qrCameraRunning = true;
        if (btn) {
            btn.textContent = '⏹ Detener Cámara';
            btn.classList.add('scanning');
        }
    }
}

/**
 * Busca agentes por nombre o ID con debounce
 */
function qrSearchAgente(query) {
    const dropdown = document.getElementById('qrAgentSearchDropdown');
    const searchInput = document.getElementById('qrCtxAgenteSearch');
    
    // Si está vacío, ocultar dropdown
    if (!query || query.trim().length === 0) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
        _qrLastSearchQuery = '';
        return;
    }
    
    // Si es solo un número, mostrar opción para cargar por ID
    if (/^\d+$/.test(query.trim())) {
        _qrLastSearchQuery = query.trim();
        const idNum = parseInt(query.trim(), 10);
        dropdown.innerHTML = `
            <div class="qr-agent-result" onclick="qrSelectAgent('${idNum}', '${idNum}')"
                style="padding:8px 12px; cursor:pointer; border-bottom:1px solid var(--border); font-weight:500;">
                ID: ${idNum}
            </div>
        `;
        dropdown.style.display = 'block';
        return;
    }
    
    // Si la búsqueda no cambió, no hacer nada
    if (_qrLastSearchQuery === query.trim()) {
        return;
    }
    
    _qrLastSearchQuery = query.trim();
    
    // Debounce: cancelar timer anterior si existe
    if (_qrSearchDebounceTimer) {
        clearTimeout(_qrSearchDebounceTimer);
    }
    
    // Mostrar loading
    dropdown.innerHTML = '<div style="padding:8px 12px; color:#666;">Buscando...</div>';
    dropdown.style.display = 'block';
    
    _qrSearchDebounceTimer = setTimeout(() => {
        // Llamar API
        fetch(`/api/qr/agentes?search=${encodeURIComponent(query.trim())}`, {
            method: 'GET',
            headers: {'Content-Type': 'application/json'}
        })
        .then(res => res.json())
        .then(data => {
            if (!data.agentes || data.agentes.length === 0) {
                dropdown.innerHTML = '<div style="padding:8px 12px; color:#999;">Sin resultados</div>';
                return;
            }
            
            // Mostrar primeros 8 resultados
            const results = data.agentes.slice(0, 8);
            const html = results.map(agente => `
                <div class="qr-agent-result" 
                     onclick="qrSelectAgent('${agente.id}', '${(agente.nombre || agente.id).replace(/'/g, "\\'")}')">
                    <strong>${agente.nombre || '—'}</strong>
                    <div style="font-size:0.85em; color:#666;">
                        ${agente.telefono ? '📞 ' + agente.telefono : ''} 
                        ${agente.alias ? '🏷 ' + agente.alias : ''} ID: ${agente.id}
                    </div>
                </div>
            `).join('');
            
            dropdown.innerHTML = html;
        })
        .catch(err => {
            console.error('Error searching agents:', err);
            dropdown.innerHTML = '<div style="padding:8px 12px; color:#c33;">Error en búsqueda</div>';
        });
    }, 250); // Debounce 250ms
}

/**
 * Selecciona un agente del dropdown y carga su información
 */
function qrSelectAgent(agentId, agentName) {
    const searchInput = document.getElementById('qrCtxAgenteSearch');
    const idInput = document.getElementById('qrCtxAgenteId');
    const dropdown = document.getElementById('qrAgentSearchDropdown');
    
    // Establecer valores
    idInput.value = agentId;
    searchInput.value = agentName;
    
    // Ocultar dropdown
    dropdown.style.display = 'none';
    dropdown.innerHTML = '';
    
    // Sincronizar context y cargar agente
    qrSyncContext();
}

// Reset toggle state if camera is stopped via other means (e.g., from scan summary)
document.addEventListener('DOMContentLoaded', () => {
    // Patch detenerEscanerQR to also reset the toggle button
    // We do this safely after all scripts have loaded
    const _origDetener = window.detenerEscanerQR;
    if (typeof _origDetener === 'function') {
        window.detenerEscanerQR = function (...args) {
            const result = _origDetener.apply(this, args);
            _qrCameraRunning = false;
            const btn = document.getElementById('qrCameraToggleBtn');
            if (btn) {
                btn.textContent = '📷 Iniciar Cámara';
                btn.classList.remove('scanning');
            }
            return result;
        };
    }
});

// ---------------------------------------------------------------------------
// Navigation helpers — ensure correct tab is active on programmatic nav
// ---------------------------------------------------------------------------

// When irAExportacionQRLotes() is called, also switch to export tab
const _origIrAExportacion = window.irAExportacionQRLotes;
// We use DOMContentLoaded to safely wrap after main.js loads
document.addEventListener('DOMContentLoaded', () => {
    const orig = window.irAExportacionQRLotes;
    if (typeof orig === 'function') {
        window.irAExportacionQRLotes = function (...args) {
            const result = orig.apply(this, args);
            setTimeout(() => qrSetTab('exportar'), 60);
            return result;
        };
    }

    // When abrirGestionPagoCompletaDesdeEscaneo() navigates to qr, show Pago tab
    const origGestion = window.abrirGestionPagoCompletaDesdeEscaneo;
    if (typeof origGestion === 'function') {
        window.abrirGestionPagoCompletaDesdeEscaneo = function (...args) {
            const result = origGestion.apply(this, args);
            setTimeout(() => qrSetTab('pago'), 60);
            return result;
        };
    }
});
