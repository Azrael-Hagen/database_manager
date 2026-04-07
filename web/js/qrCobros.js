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
    ['qrAgenteId', 'pagoAgenteId'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = agenteId;
    });
    // For the deuda manual search combo, use the helper if available; fall back to direct set
    if (typeof _setDeudaManualAgente === 'function') {
        _setDeudaManualAgente(agenteId);
    } else {
        const el = document.getElementById('deudaManualAgenteId');
        if (el) el.value = agenteId;
    }

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

        // La respuesta tiene shape: { status, agente, data: { saldo_acumulado, pagado_semana, ... } }
        const inner  = data?.data || {};
        const deuda  = parseFloat(inner.saldo_acumulado ?? 0);

        if (deuda > 0.009) {
            badge.textContent   = `Debe $${deuda.toFixed(0)}`;
            badge.style.background = '#d64545';
        } else {
            badge.textContent   = 'Al Corriente';
            badge.style.background = '#16966a';
        }
        badge.style.color = '#fff';
    } catch (_) {
        if (badge) {
            badge.textContent   = 'Sin información';
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
const _qrAgentSearchCache = new Map();

// ---------------------------------------------------------------------------
// Deuda Manual — agent search (by name / ID / phone)
// ---------------------------------------------------------------------------

let _dmSearchDebounceTimer = null;
let _dmLastSearchQuery = '';
const _dmAgentSearchCache = new Map();

/**
 * Busca agentes para el panel "Control Manual de Deuda".
 * Acepta nombre, alias, telefono, ID o FP.
 */
function deudaManualSearchAgente(query) {
    const dropdown = document.getElementById('deudaManualAgentDropdown');
    const hiddenId = document.getElementById('deudaManualAgenteId');
    if (!dropdown) return;

    // Limpiar ID oculto mientras escribe (se reasignará al seleccionar)
    if (hiddenId) hiddenId.value = '';

    const trimmed = (query || '').trim();
    if (trimmed.length === 0) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
        _dmLastSearchQuery = '';
        return;
    }

    if (_dmLastSearchQuery === trimmed) return;
    _dmLastSearchQuery = trimmed;

    if (_dmSearchDebounceTimer) clearTimeout(_dmSearchDebounceTimer);

    dropdown.innerHTML = '<div style="padding:8px 12px;color:#666;">Buscando…</div>';
    dropdown.style.display = 'block';

    _dmSearchDebounceTimer = setTimeout(async () => {
        try {
            const payload = await apiClient.getAgentesQR(trimmed);
            const agents = Array.isArray(payload?.data) ? payload.data : [];
            if (agents.length === 0) {
                dropdown.innerHTML = '<div style="padding:8px 12px;color:#999;">Sin resultados</div>';
                return;
            }
            const results = agents.slice(0, 8);
            _dmAgentSearchCache.clear();
            for (const ag of results) _dmAgentSearchCache.set(String(ag.id), ag);

            dropdown.innerHTML = results.map(ag => {
                const label = (ag.display_name || ag.alias || ag.nombre || `Agente ${ag.id}`)
                    .replace(/'/g, "\\'");
                const meta = [
                    ag.telefono ? '📞 ' + ag.telefono : '',
                    ag.alias    ? '🏷 '  + ag.alias    : '',
                    ag.numero_voip ? '☎ ' + ag.numero_voip : '',
                    ag.fp ? '🆔 FP: ' + ag.fp : '',
                    'ID: ' + ag.id,
                ].filter(Boolean).join('  ');
                return `<div class="qr-agent-result"
                    onclick="deudaManualSelectAgent(${ag.id}, '${label}')">
                    <strong>${label}</strong>
                    <div style="font-size:0.85em;color:#666;">${meta}</div>
                </div>`;
            }).join('');
        } catch (err) {
            console.error('Error buscando agente (deuda manual):', err);
            dropdown.innerHTML = '<div style="padding:8px 12px;color:#c33;">Error en búsqueda</div>';
        }
    }, 250);
}

/**
 * Selecciona un agente del dropdown de deuda manual.
 */
function deudaManualSelectAgent(agentId, displayName) {
    const searchInput = document.getElementById('deudaManualAgenteSearch');
    const hiddenId    = document.getElementById('deudaManualAgenteId');
    const dropdown    = document.getElementById('deudaManualAgentDropdown');
    const cached      = _dmAgentSearchCache.get(String(agentId));

    const name = cached
        ? (cached.display_name || cached.alias || cached.nombre || displayName || `ID: ${agentId}`)
        : (displayName || `ID: ${agentId}`);

    if (searchInput) searchInput.value = name;
    if (hiddenId)    hiddenId.value    = String(agentId);
    if (dropdown)  { dropdown.style.display = 'none'; dropdown.innerHTML = ''; }
    _dmLastSearchQuery = '';

    // Consultar deuda actual al seleccionar
    if (typeof consultarDeudaManualAgente === 'function') {
        consultarDeudaManualAgente(false);
    }
}

// Cerrar dropdown cuando se hace clic fuera
document.addEventListener('click', function (e) {
    const dropdown = document.getElementById('deudaManualAgentDropdown');
    const search   = document.getElementById('deudaManualAgenteSearch');
    if (dropdown && !dropdown.contains(e.target) && e.target !== search) {
        dropdown.style.display = 'none';
    }
});

async function qrToggleCamera() {
    const btn = document.getElementById('qrCameraToggleBtn');
    const runtimeRunning = typeof window.isQrScannerRunning === 'function'
        ? !!window.isQrScannerRunning()
        : _qrCameraRunning;
    _qrCameraRunning = runtimeRunning;

    if (_qrCameraRunning) {
        // Stop
        if (typeof detenerEscanerQR === 'function') await detenerEscanerQR();
        _qrCameraRunning = false;
        if (btn) {
            btn.textContent = '📷 Iniciar Cámara';
            btn.classList.remove('scanning');
        }
    } else {
        // Start
        if (typeof iniciarEscanerQR === 'function') await iniciarEscanerQR();
        const running = typeof window.isQrScannerRunning === 'function'
            ? !!window.isQrScannerRunning()
            : true;
        _qrCameraRunning = running;
        if (btn) {
            if (running) {
                btn.textContent = '⏹ Detener Cámara';
                btn.classList.add('scanning');
            } else {
                btn.textContent = '📷 Iniciar Cámara';
                btn.classList.remove('scanning');
            }
        }
    }
}

/**
 * Busca agentes por nombre, ID o FP con debounce
 */
function qrSearchAgente(query) {
    const dropdown = document.getElementById('qrAgentSearchDropdown');
    const searchInput = document.getElementById('qrCtxAgenteSearch');
    
    // Si está vacío, ocultar dropdown
    if (!query || query.trim().length === 0) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
        _qrLastSearchQuery = '';
        _qrAgentSearchCache.clear();
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
    
    _qrSearchDebounceTimer = setTimeout(async () => {
        try {
            const payload = await apiClient.getAgentesQR(query.trim());
            const agents = Array.isArray(payload?.data) ? payload.data : [];
            if (agents.length === 0) {
                dropdown.innerHTML = '<div style="padding:8px 12px; color:#999;">Sin resultados</div>';
                return;
            }

            // Mostrar primeros 8 resultados y cachear para selección
            const results = agents.slice(0, 8);
            _qrAgentSearchCache.clear();
            for (const agente of results) {
                _qrAgentSearchCache.set(String(agente.id), agente);
            }

            const html = results.map(agente => {
                const label = (agente.display_name || agente.alias || agente.nombre || `Agente ${agente.id}`)
                    .replace(/'/g, "\\'");
                return `
                <div class="qr-agent-result" 
                     onclick="qrSelectAgent('${agente.id}')">
                    <strong>${label}</strong>
                    <div style="font-size:0.85em; color:#666;">
                        ${agente.telefono ? '📞 ' + agente.telefono : ''}
                        ${agente.alias ? ' 🏷 ' + agente.alias : ''}
                        ${agente.numero_voip ? ' ☎ ' + agente.numero_voip : ''}
                        ${agente.fp ? ' 🆔 FP: ' + agente.fp : ''}
                        ID: ${agente.id}
                    </div>
                </div>
            `;
            }).join('');

            dropdown.innerHTML = html;
        } catch (err) {
            console.error('Error searching agents:', err);
            dropdown.innerHTML = '<div style="padding:8px 12px; color:#c33;">Error en búsqueda</div>';
        }
    }, 250); // Debounce 250ms
}

/**
 * Selecciona un agente del dropdown y carga su información
 */
function qrSelectAgent(agentId) {
    const searchInput = document.getElementById('qrCtxAgenteSearch');
    const idInput = document.getElementById('qrCtxAgenteId');
    const voipInput = document.getElementById('qrCtxVoip');
    const dropdown = document.getElementById('qrAgentSearchDropdown');
    const cached = _qrAgentSearchCache.get(String(agentId));
    const fallbackName = String(agentId);
    const selectedName = (cached?.display_name || cached?.alias || cached?.nombre || fallbackName);
    // VoIP: primero datos_adicionales, si vacío usar línea EXT_PBX asignada
    const extPbxLine = (cached?.lineas || []).find(l => l.tipo === 'EXT_PBX');
    const selectedVoip = (cached?.numero_voip || cached?.datos_adicionales?.numero_voip || extPbxLine?.numero || '').toString().trim();
    
    // Establecer valores
    idInput.value = agentId;
    searchInput.value = selectedName;
    if (voipInput) voipInput.value = selectedVoip;
    
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
        window.detenerEscanerQR = async function (...args) {
            const result = _origDetener.apply(this, args);
            await Promise.resolve(result);
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
