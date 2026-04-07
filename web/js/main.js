// === CONFIGURACIÓN GLOBAL ===
const API_URL = `${window.location.origin}/api`;
let authToken = null;
let currentUser = null;
let currentPage = 1;
let currentSearch = '';
let currentSection = 'dashboard';
let realtimeInterval = null;
let realtimeEnabled = true;
let realtimeMs = 20000;
let realtimePausedByVisibility = false;
let hiddenDatabases = JSON.parse(localStorage.getItem('hiddenDatabases') || '[]');
let showHiddenDatabases = false;
let currentImportDB = '';
let currentVerificationData = null;
let qrScannerInstance = null;
let qrAvailableCameras = [];
let qrCurrentCameraId = '';
const QR_SCAN_DUPLICATE_WINDOW_MS = 2500;
let qrLastDecodedText = '';
let qrLastDecodedAtMs = 0;
let qrDecodeInFlight = false;
let currentWeeklyReportRows = [];
let lastReceiptData = null;
let currentDatosDatabase = '';
let currentServerAccessUrl = '';
let currentServerAccessNoPortUrl = '';
let brandingManageEnabled = false;
let currentAgentManagementRows = [];
let currentEditingAgentId = null;
let gestionAgenteSearchTimer = null;
let gestionAgenteCacheKey = '';
let gestionAgenteCacheRows = [];
let gestionAgenteCacheAtMs = 0;
let currentBackupDir = '';
let pendingAltaAgentId = null;
let currentAltasAgents = [];
let currentAltasLineas = [];
let currentLineasGestionRows = [];
let currentLineaEditId = null;
let currentTableBrowserState = { database: '', table: '', orderBy: 'id', direction: 'desc', limit: 50 };
let currentUsuariosRows = [];
let altasTourActive = false;
let altasTourStepIndex = 0;
let altasTourBackdrop = null;
let altasTourPanel = null;
let altasTourCurrentElement = null;
let alertPollingPromise = null;
let lastAlertNotificationStamp = null;
let alertasCache = [];
let alertasCacheStampMs = 0;
let rolesCapabilitiesCache = [];
let sessionCloseInProgress = false;
let inactivityTimer = null;
let inactivityWarningTimer = null;
let inactivityHeartbeatInterval = null;

// Detectar si es mobile: viewport <= 768px O user agent móvil
const IS_MOBILE_DEVICE = () => {
    const ua = navigator.userAgent.toLowerCase();
    const isMobileUA = /(android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini)/i.test(ua);
    const isSmallViewport = window.innerWidth <= 768;
    return isMobileUA || isSmallViewport;
};

// Timeout: 4 horas en mobile, 30 min en desktop
// Mobile necesita más tiempo porque usuarios bloquean pantalla, cambian apps, etc.
const INACTIVITY_TIMEOUT_MS = (() => {
    const stored = localStorage.getItem('sessionInactivityMs');
    if (stored) return Number(stored);
    return IS_MOBILE_DEVICE() ? (4 * 60 * 60 * 1000) : (30 * 60 * 1000); // 4h mobile, 30m desktop
})();

// Segundos antes de expiración para mostrar aviso
const INACTIVITY_WARNING_BEFORE_CLOSE_MS = 5 * 60 * 1000; // 5 min antes del cierre

const INACTIVITY_EVENTS = ['click', 'keydown', 'mousedown', 'touchstart', 'scroll'];
const DEFAULT_AGENT_DATABASE = 'database_manager';
const BRANDING_DEFAULTS = {
    appName: 'Database Manager',
    subtitle: 'database_manager',
    logoPath: 'sources/logo.png'
};
const DB_OBJECT_CATALOG = {
    datos_importados: { logical: 'Agentes Operativos', purpose: 'Maestro de agentes usados en altas, cambios, pagos y QR.' },
    agentes: { logical: 'Agentes Legado', purpose: 'Tabla historica de compatibilidad para integraciones externas.' },
    extensions_pbx: { logical: 'Extensiones PBX Fuente', purpose: 'Inventario fuente de lineas sincronizadas desde PBX.' },
    lineas_telefonicas: { logical: 'Lineas Operativas', purpose: 'Inventario gestionado para asignaciones a agentes.' },
    agente_linea_asignaciones: { logical: 'Asignaciones Agente-Linea', purpose: 'Historial de asignaciones y liberaciones de lineas.' },
    pagos_semanales: { logical: 'Pagos Semanales', purpose: 'Registro de pagos y abonos por semana de cada agente.' },
    recibos_pago: { logical: 'Recibos de Pago', purpose: 'Comprobantes persistentes para reimpresion y auditoria.' },
    cat_estatus_agente: { logical: 'Catalogo Estatus Agente', purpose: 'Catalogo de estados operativos del agente.' },
    agente_eventos_operativos: { logical: 'Bitacora Operativa Agente', purpose: 'Traza eventos de flujo operativo por agente.' },
    ladas_catalogo: { logical: 'Catalogo de Ladas', purpose: 'Catalogo de ladas activas para filtros y asignacion.' },
    catalogo_ladas: { logical: 'Catalogo Ladas Especial', purpose: 'Tabla especial legado (registro_agentes) para ladas oficiales.' },
    usuarios: { logical: 'Usuarios del Sistema', purpose: 'Cuentas, roles y control de acceso.' },
    auditoria_acciones: { logical: 'Auditoria del Sistema', purpose: 'Registro de acciones por usuario y fecha.' },
    config_sistema: { logical: 'Configuracion del Sistema', purpose: 'Parametros globales como cuota semanal y alertas.' },
    alertas_pago: { logical: 'Alertas de Pago', purpose: 'Alertas por falta de pago semanal y su seguimiento.' },
    import_logs: { logical: 'Bitacora de Importaciones', purpose: 'Historial de importaciones y su resultado.' },
    vw_agentes_extensiones_pago_actual: { logical: 'Vista Agentes + Extensiones + Pago', purpose: 'Estado semanal por agente con linea y pago.' },
    vw_agentes_operacion_actual: { logical: 'Vista Operacion Actual', purpose: 'Consolidado operativo con estatus, linea y pago.' },
    vw_control_sync_agentes: { logical: 'Vista Control Sincronizacion', purpose: 'Controla alineacion entre base operativa y legado.' },
    vw_dm_agentes_operacion_actual: { logical: 'Vista Operacion (Espejo DM)', purpose: 'Espejo en registro_agentes para consulta amigable.' },
    vw_dm_control_sync_agentes: { logical: 'Vista Sync (Espejo DM)', purpose: 'Espejo en registro_agentes del control de sync.' },
    vw_dm_cat_estatus_agente: { logical: 'Catalogo Estatus (Espejo DM)', purpose: 'Espejo en registro_agentes del catalogo de estatus.' },
};

function getDbObjectInfo(name) {
    const key = String(name || '').trim();
    return DB_OBJECT_CATALOG[key] || null;
}

function formatDbObjectOption(name) {
    const info = getDbObjectInfo(name);
    return info ? `${info.logical} [${name}]` : name;
}

function renderDbObjectCell(name) {
    const info = getDbObjectInfo(name);
    if (!info) return escapeHtml(name);
    return `<div><strong>${escapeHtml(info.logical)}</strong><br><span class="hint">Fisico: ${escapeHtml(name)} | ${escapeHtml(info.purpose)}</span></div>`;
}

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '\uD83D\uDE48'; // 🙈
    } else {
        input.type = 'password';
        btn.innerHTML = '&#128065;'; // 👁
    }
}

function mondayISO(today = new Date()) {
    const d = new Date(today);
    const day = d.getDay();
    const diff = (day + 6) % 7;
    d.setDate(d.getDate() - diff);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

function todayISO(today = new Date()) {
    const d = new Date(today);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

function setDefaultWeeklyDates() {
    const week = mondayISO();
    ['qrSemana', 'qrScanSemana', 'pagoSemana', 'reporteSemanaInput', 'qrCtxSemana'].forEach(id => {
        const input = document.getElementById(id);
        if (input && !input.value) {
            input.value = week;
        }
    });

    const reportDate = document.getElementById('reporteCobroFechaInput');
    if (reportDate && !reportDate.value) {
        reportDate.value = todayISO();
    }
}

async function fetchJson(url, options = {}) {
    const finalOptions = {
        cache: 'no-store',
        ...options,
        headers: {
            ...(options.headers || {}),
        }
    };

    const response = await fetch(url, finalOptions);
    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const payload = await response.json();
            detail = payload.detail || payload.mensaje || detail;
        } catch (_) {
            // ignore JSON parse failures
        }

        const normalizedDetail = String(detail || '').toLowerCase();
        const mustCloseSession = response.status === 401 || (
            response.status === 403 && [
                'token inválido',
                'token invalido',
                'token expirado',
                'sesión expirada',
                'sesion expirada',
                'sesión inválida',
                'sesion invalida',
                'usuario inactivo',
                'not authenticated',
                'invalid token',
                'expired token',
            ].some(fragment => normalizedDetail.includes(fragment))
        );

        if (mustCloseSession && authToken) {
            forceSessionClose('token_invalid', {
                notify: true,
                reload: true,
                message: 'Tu sesión expiró o ya no es válida. Se recargará la página para volver a iniciar sesión.'
            });
        }

        throw new Error(detail);
    }

    if (response.status === 204) {
        return {};
    }

    return response.json();
}

function escapeHtml(value) {
    return window.AppUtils.escapeHtml(value);
}

function getErrorMessage(error, fallback = 'Error inesperado') {
    return window.AppUtils.getErrorMessage(error, fallback);
}

function ensureAppAlertRoot() {
    return window.AppUtils.ensureAppAlertRoot();
}

function showAppAlert(message, options = {}) {
    return window.AppUtils.showAppAlert(message, options);
}

function showAppConfirm(message, options = {}) {
    return window.AppUtils.showAppConfirm(message, options);
}

function showAppPrompt(message, options = {}) {
    return window.AppUtils.showAppPrompt(message, options);
}

function normalizeNullableInput(value) {
    const text = String(value ?? '').trim();
    if (!text) return null;
    if (text.toLowerCase() === 'null') return null;
    return text;
}

function getAgentDisplayName(agent, fallback = 'Agente') {
    const extras = getAgentExtras(agent);
    const alias = String(extras.alias || '').trim();
    const nombre = String(agent?.nombre || '').trim();
    if (alias) return alias;
    if (nombre) return nombre;
    if (agent?.id) return `Agente ${agent.id}`;
    return fallback;
}

function formatDateTimeSafe(value) {
    return window.AppUtils.formatDateTimeSafe(value);
}

function isCameraSecureContext() {
    const host = (window.location.hostname || '').toLowerCase();
    const isLocalHost = host === 'localhost' || host === '127.0.0.1' || host === '::1';
    return window.location.protocol === 'https:' || isLocalHost;
}

function renderCameraSecurityHint() {
    const hintEl = document.getElementById('cameraSecurityHint');
    if (!hintEl) return;
    if (isCameraSecureContext()) {
        hintEl.textContent = '';
        hintEl.title = '';
        return;
    }
    hintEl.textContent = 'Camara: HTTP detectado. Usa HTTPS o localhost para escaneo QR.';
    hintEl.title = 'Los navegadores bloquean camara en origenes HTTP no seguros';
}

function isNativePhantomScannerAvailable() {
    return !!(window.PhantomAndroid && typeof window.PhantomAndroid.startNativeQrScan === 'function');
}

function renderNativeQrControls() {
    const nativeButton = document.getElementById('nativeQrScanBtn');
    const nativeHint = document.getElementById('nativeQrScanHint');
    const available = isNativePhantomScannerAvailable();

    if (nativeButton) nativeButton.style.display = available ? '' : 'none';
    if (nativeHint) nativeHint.style.display = available ? 'block' : 'none';
}

function triggerNativeQrScan() {
    if (!isNativePhantomScannerAvailable()) {
        showAppAlert('El escaneo nativo solo está disponible dentro de la Phantom App instalada.', {
            title: 'Escaneo nativo no disponible',
            tone: 'warning',
        });
        return;
    }
    window.PhantomAndroid.startNativeQrScan();
}

async function consumePendingNativeQrScan() {
    const pendingCode = String(window.__phantomNativeLastScan || '').trim();
    if (!pendingCode) return;
    window.__phantomNativeLastScan = '';
    try {
        await manejarQRLeido(pendingCode);
    } catch (error) {
        console.error('Error procesando escaneo nativo pendiente:', error);
    }
}

window.addEventListener('phantom-native-qr-scan', (event) => {
    const decodedText = String(event?.detail?.code || '').trim();
    if (!decodedText) return;
    window.__phantomNativeLastScan = '';
    Promise.resolve(manejarQRLeido(decodedText)).catch((error) => {
        console.error('Error procesando escaneo nativo:', error);
    });
});

function updateScrollTopButton() {
    const btn = document.getElementById('scrollTopBtn');
    if (!btn) return;
    if (window.scrollY > 420) {
        btn.classList.add('visible');
    } else {
        btn.classList.remove('visible');
    }
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function getCurrentRole() {
    const role = String(currentUser?.rol || '').trim().toLowerCase();
    if (role === 'super_admin' || currentUser?.es_super_admin) return 'super_admin';
    if (role === 'admin' || currentUser?.es_admin) return 'admin';
    if (role === 'capture') return 'capture';
    return 'viewer';
}

function canCapture() {
    return getCurrentRole() === 'capture' || canAdmin();
}

function canAdmin() {
    return getCurrentRole() === 'admin' || canSuperAdmin();
}

function canSuperAdmin() {
    return getCurrentRole() === 'super_admin' || currentUser?.es_super_admin === true;
}

function isLimitedViewer() {
    return getCurrentRole() === 'viewer';
}

function isMobileViewport() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function canAccessSection(section) {
    const role = getCurrentRole();
    if (role === 'super_admin' || role === 'admin') return true;
    if (role === 'capture') {
        return ['dashboard', 'datos', 'importar', 'exportar', 'altasAgentes', 'lineas', 'estadoAgentes', 'alertas'].includes(section);
    }
    return ['miCuenta'].includes(section);
}

function applyRoleBasedUI() {
    const role = getCurrentRole();
    const roleLabel = role === 'super_admin' ? 'Super Admin'
        : role === 'admin' ? 'Administrador'
        : role === 'capture' ? 'Altas'
        : (currentUser?.es_temporal ? 'Consulta temporal' : 'Consulta limitada');
    const userNameEl = document.getElementById('userName');
    if (userNameEl) {
        userNameEl.textContent = `${currentUser?.username || 'Usuario'} · ${roleLabel}`;
    }

    const menuRules = {
        miCuenta: isLimitedViewer(),
        dashboard: !isLimitedViewer(),
        datos: !isLimitedViewer(),
        databases: canAdmin(),
        importar: canCapture(),
        exportar: canCapture(),
        altasAgentes: canCapture(),
        lineas: canCapture(),
        cambiosBajas: canAdmin(),
        qrScan: canAdmin(),
        qr: canAdmin(),
        usuarios: canAdmin(),
        auditoria: canAdmin(),
        papelera: canSuperAdmin(),
        estadoAgentes: canCapture(),
        alertas: !isLimitedViewer(),
        };
    Object.entries(menuRules).forEach(([section, visible]) => {
        const item = document.querySelector(`.menu-item[onclick*="'${section}'"]`);
        if (item) {
            item.style.display = visible ? '' : 'none';
        }
    });

    const purgeBtn = document.getElementById('purgeInactiveBtn');
    if (purgeBtn) purgeBtn.style.display = canSuperAdmin() ? '' : 'none';
    const maintenancePanel = document.getElementById('dbMaintenancePanel');
    if (maintenancePanel) maintenancePanel.style.display = canAdmin() ? 'block' : 'none';
    const deudaManualPanel = document.getElementById('deudaManualPanel');
    if (deudaManualPanel) deudaManualPanel.style.display = canAdmin() ? 'block' : 'none';
    const serverAccessWrap = document.getElementById('serverAccessWrap');
    if (serverAccessWrap) serverAccessWrap.style.display = isLimitedViewer() ? 'none' : '';
    const serverAccessHint = document.getElementById('serverAccessHint');
    if (serverAccessHint) serverAccessHint.style.display = isLimitedViewer() ? 'none' : '';
    const cameraSecurityHint = document.getElementById('cameraSecurityHint');
    if (cameraSecurityHint) cameraSecurityHint.style.display = isLimitedViewer() ? 'none' : '';
    // Papelera panel — only super_admin
    const papeleraSection = document.getElementById('papeleraSection');
    if (papeleraSection) papeleraSection.style.display = canSuperAdmin() ? '' : 'none';
    syncUsuarioRoleOptions();
}

function syncUsuarioRoleOptions() {
    const roleSelect = document.getElementById('usuarioRol');
    if (!roleSelect) return;

    const superAdminOption = roleSelect.querySelector('option[value="super_admin"]');
    if (!superAdminOption) return;

    const allowSuperAdmin = canSuperAdmin();
    superAdminOption.hidden = !allowSuperAdmin;
    superAdminOption.disabled = !allowSuperAdmin;

    if (!allowSuperAdmin && roleSelect.value === 'super_admin') {
        roleSelect.value = 'admin';
    }
}

async function cargarCapacidadesRoles(forceRefresh = false) {
    const container = document.getElementById('rolesCapabilitiesContainer');
    if (!container) return;

    if (!forceRefresh && rolesCapabilitiesCache.length > 0) {
        renderCapacidadesRoles(rolesCapabilitiesCache);
        return;
    }

    container.innerHTML = '<p class="hint">Cargando matriz de roles...</p>';
    try {
        const data = await fetchJson(`${API_URL}/usuarios/roles/capabilities`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        rolesCapabilitiesCache = Array.isArray(data?.items) ? data.items : [];
        renderCapacidadesRoles(rolesCapabilitiesCache);
    } catch (error) {
        container.innerHTML = `<p style="color:#b22222;">Error al cargar capacidades de roles: ${escapeHtml(error.message || 'Error desconocido')}</p>`;
    }
}

function renderCapacidadesRoles(items) {
    const container = document.getElementById('rolesCapabilitiesContainer');
    if (!container) return;
    if (!Array.isArray(items) || items.length === 0) {
        container.innerHTML = '<p class="hint">No hay capacidades registradas.</p>';
        return;
    }

    container.innerHTML = items.map(item => {
        const role = escapeHtml(item.role || 'N/A');
        const label = escapeHtml(item.label || item.role || 'Rol');
        const description = escapeHtml(item.description || '');
        const permissions = Array.isArray(item.permissions) ? item.permissions : [];
        const permsHtml = permissions.map(p => `<li>${escapeHtml(String(p))}</li>`).join('');
        return `
            <article class="role-card role-${role}">
                <div class="role-card-title">${label}</div>
                <p class="role-card-desc">${description}</p>
                <ul class="role-card-list">${permsHtml}</ul>
            </article>
        `;
    }).join('');
}

function getAltasTourStorageKey() {
    const user = (currentUser?.username || 'anon').trim().toLowerCase() || 'anon';
    return `altasTourSeen:${user}`;
}

function getAltasTourSteps() {
    return [
        {
            selector: '#ladaCodigoInput',
            title: 'Paso 1: Validar Ladas',
            body: 'Primero confirma que la lada exista. Si falta, crea/reactiva la lada con su código y opcionalmente su región.'
        },
        {
            selector: '#agenteNombreInput',
            title: 'Paso 2: Datos Básicos del Agente',
            body: 'Captura el nombre y, si aplica, alias/ubicación/FP/FC/Grupo. Esta alta ya no solicita teléfono en esta pantalla.'
        },
        {
            selector: '#agenteModoAsignacion',
            title: 'Paso 3: Modo de Asignación',
            body: 'Elige si el agente inicia sin línea, con asignación automática o manual. Para inserción, lo recomendado es automático o manual con línea válida.'
        },
        {
            selector: '#agenteLadaObjetivoSelect',
            title: 'Paso 4: Lada Preferida',
            body: 'Si quieres orientar la autoasignación, selecciona una lada preferida. Esto ayuda a tomar líneas del bloque correcto.'
        },
        {
            selector: '#agenteGenerarQrAlCrear',
            title: 'Paso 5: Crear Agente',
            body: 'Activa o desactiva la generación de QR al crear. Luego presiona Crear Agente para guardar el alta.'
        },
        {
            selector: 'form[onsubmit="sincronizarLineasPBX(event)"] button[type="submit"]',
            title: 'Paso 6: Sincronizar Líneas PBX',
            body: 'Usa este botón para refrescar inventario de líneas y ladas desde la fuente PBX real antes de asignar.'
        },
        {
            selector: '#lineaAsignarSelect',
            title: 'Paso 7: Asignar Línea',
            body: 'Selecciona línea y agente en los combos, después presiona Asignar Línea. Solo se muestran líneas del inventario gestionado.'
        },
    ];
}

function clearAltasTourHighlight() {
    if (altasTourCurrentElement) {
        altasTourCurrentElement.classList.remove('tour-highlight');
        altasTourCurrentElement = null;
    }
}

function closeAltasTour() {
    altasTourActive = false;
    clearAltasTourHighlight();
    if (altasTourBackdrop) {
        altasTourBackdrop.remove();
        altasTourBackdrop = null;
    }
    if (altasTourPanel) {
        altasTourPanel.remove();
        altasTourPanel = null;
    }
}

function renderAltasTourStep() {
    const steps = getAltasTourSteps();
    const step = steps[altasTourStepIndex];
    if (!step || !altasTourPanel) return;

    clearAltasTourHighlight();
    const target = document.querySelector(step.selector);
    if (target) {
        altasTourCurrentElement = target;
        target.classList.add('tour-highlight');
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const progressEl = altasTourPanel.querySelector('.tour-progress');
    const titleEl = altasTourPanel.querySelector('.tour-title');
    const bodyEl = altasTourPanel.querySelector('.tour-body');
    const prevBtn = altasTourPanel.querySelector('[data-tour="prev"]');
    const nextBtn = altasTourPanel.querySelector('[data-tour="next"]');

    if (titleEl) titleEl.textContent = step.title;
    if (bodyEl) bodyEl.textContent = step.body;
    if (progressEl) progressEl.textContent = `Paso ${altasTourStepIndex + 1} de ${steps.length}`;
    if (prevBtn) prevBtn.disabled = altasTourStepIndex === 0;
    if (nextBtn) nextBtn.textContent = altasTourStepIndex >= steps.length - 1 ? 'Finalizar' : 'Siguiente';
}

function startAltasTour(force = false) {
    if (!canCapture()) return;
    const alreadySeen = localStorage.getItem(getAltasTourStorageKey()) === '1';
    if (!force && alreadySeen) return;
    if (altasTourActive) return;

    altasTourActive = true;
    altasTourStepIndex = 0;

    altasTourBackdrop = document.createElement('div');
    altasTourBackdrop.className = 'tour-backdrop';
    document.body.appendChild(altasTourBackdrop);

    altasTourPanel = document.createElement('div');
    altasTourPanel.className = 'tour-panel';
    altasTourPanel.innerHTML = `
        <h3 class="tour-title"></h3>
        <div class="tour-progress"></div>
        <div class="tour-body"></div>
        <div class="tour-actions">
            <button type="button" class="btn btn-secondary" data-tour="prev">Anterior</button>
            <button type="button" class="btn" data-tour="next">Siguiente</button>
            <button type="button" class="btn btn-secondary" data-tour="close">Cerrar</button>
        </div>
    `;
    document.body.appendChild(altasTourPanel);

    altasTourPanel.querySelector('[data-tour="prev"]')?.addEventListener('click', () => {
        altasTourStepIndex = Math.max(0, altasTourStepIndex - 1);
        renderAltasTourStep();
    });

    altasTourPanel.querySelector('[data-tour="next"]')?.addEventListener('click', () => {
        const steps = getAltasTourSteps();
        if (altasTourStepIndex >= steps.length - 1) {
            localStorage.setItem(getAltasTourStorageKey(), '1');
            closeAltasTour();
            return;
        }
        altasTourStepIndex += 1;
        renderAltasTourStep();
    });

    altasTourPanel.querySelector('[data-tour="close"]')?.addEventListener('click', () => {
        localStorage.setItem(getAltasTourStorageKey(), '1');
        closeAltasTour();
    });

    renderAltasTourStep();
}

function iniciarGuiaAltas() {
    if (!canCapture()) {
        alert('La guía de altas está disponible para usuarios de inserción/captura o administradores.');
        return;
    }
    loadSection('altasAgentes');
    setTimeout(() => startAltasTour(true), 220);
}

function reiniciarGuiaAltas() {
    localStorage.removeItem(getAltasTourStorageKey());
    iniciarGuiaAltas();
}

function maybeAutoStartAltasTour() {
    if (!canCapture()) return;
    setTimeout(() => startAltasTour(false), 260);
}

function getDatosSortConfig() {
    return {
        orderBy: document.getElementById('datosOrderBy')?.value || 'fecha_creacion',
        direction: document.getElementById('datosOrderDir')?.value || 'desc',
    };
}

function formatRelativeAge(seconds) {
    const numeric = Number(seconds);
    if (!Number.isFinite(numeric) || numeric < 0) {
        return 'sin registro';
    }
    if (numeric < 60) {
        return 'hace menos de 1 min';
    }
    if (numeric < 3600) {
        return `hace ${Math.floor(numeric / 60)} min`;
    }
    if (numeric < 86400) {
        return `hace ${Math.floor(numeric / 3600)} h`;
    }
    return `hace ${Math.floor(numeric / 86400)} d`;
}

function renderActivityChart(series) {
    if (!Array.isArray(series) || !series.length) {
        return '<p class="hint">Sin actividad reciente.</p>';
    }

    const maxValue = Math.max(
        1,
        ...series.map(item => Math.max(
            Number(item.registros || 0),
            Number(item.qr || 0),
            Number(item.importaciones || 0)
        ))
    );

    return series.map(item => {
        const registros = Number(item.registros || 0);
        const qr = Number(item.qr || 0);
        const importaciones = Number(item.importaciones || 0);
        const fallidas = Number(item.fallidas || 0);
        const registrosHeight = Math.max(registros > 0 ? 18 : 6, Math.round((registros / maxValue) * 88));
        const qrHeight = Math.max(qr > 0 ? 18 : 6, Math.round((qr / maxValue) * 88));
        const importHeight = Math.max(importaciones > 0 ? 18 : 6, Math.round((importaciones / maxValue) * 88));
        const title = `${item.label}: registros ${registros}, QR ${qr}, importaciones ${importaciones}, fallidas ${fallidas}`;
        return `<div class="activity-day" title="${escapeHtml(title)}">
            <div class="activity-bars">
                <span class="activity-bar records" style="height:${registrosHeight}px"></span>
                <span class="activity-bar qr" style="height:${qrHeight}px"></span>
                <span class="activity-bar imports" style="height:${importHeight}px"></span>
            </div>
            <strong>${escapeHtml(item.label || '')}</strong>
            <span>R ${registros} · Q ${qr} · I ${importaciones}</span>
        </div>`;
    }).join('');
}

// === INICIALIZACIÓN ===
document.addEventListener('DOMContentLoaded', () => {
    const enabledSaved = localStorage.getItem('realtimeEnabled');
    const msSaved = localStorage.getItem('realtimeMs');
    if (enabledSaved !== null) {
        realtimeEnabled = enabledSaved === 'on';
    }
    if (msSaved) {
        realtimeMs = Number(msSaved);
    }

    const token = localStorage.getItem('authToken');
    if (token) {
        authToken = token;
        apiClient.setToken(token);
        currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
        validarSesionActiva();
    } else {
        showLogin();
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('app:session-invalid', (event) => {
        const reason = String(event?.detail?.reason || 'token_invalid');
        if (!authToken) return;
        forceSessionClose(reason, {
            notify: true,
            reload: true,
            message: 'La sesión dejó de ser válida. Se cerrará automáticamente y se recargará la página.'
        });
    });
    window.addEventListener('scroll', updateScrollTopButton, { passive: true });
    window.addEventListener('resize', () => {
        if (!isMobileViewport()) {
            toggleSidebar(false);
        }
    });
    updateScrollTopButton();
    setDefaultWeeklyDates();
    loadBrandingConfig();
    renderCameraSecurityHint();
    renderNativeQrControls();
    consumePendingNativeQrScan();
});

async function loadBrandingConfig() {
    let config = { ...BRANDING_DEFAULTS };
    try {
        const response = await fetch('sources/branding.json', { cache: 'no-store' });
        if (response.ok) {
            const remote = await response.json();
            config = {
                appName: String(remote.appName || BRANDING_DEFAULTS.appName),
                subtitle: String(remote.subtitle || BRANDING_DEFAULTS.subtitle),
                logoPath: String(remote.logoPath || BRANDING_DEFAULTS.logoPath)
            };
        }
    } catch (_) {
        // Optional file; keep defaults when missing.
    }

    const titleEl = document.getElementById('brandTitle');
    const subtitleEl = document.getElementById('brandSubtitle');
    const logoEl = document.getElementById('brandLogo');
    if (titleEl) titleEl.textContent = config.appName;
    if (subtitleEl) subtitleEl.textContent = config.subtitle;
    if (logoEl) applyLogoWithFallback(logoEl, config.logoPath);
    document.title = `${config.appName} - ${config.subtitle}`;
}

function applyBrandingConfig(config) {
    if (!config || typeof config !== 'object') return;
    const titleEl = document.getElementById('brandTitle');
    const subtitleEl = document.getElementById('brandSubtitle');
    const logoEl = document.getElementById('brandLogo');
    if (titleEl) titleEl.textContent = String(config.appName || BRANDING_DEFAULTS.appName);
    if (subtitleEl) subtitleEl.textContent = String(config.subtitle || BRANDING_DEFAULTS.subtitle);
    if (logoEl) applyLogoWithFallback(logoEl, String(config.logoPath || BRANDING_DEFAULTS.logoPath));
    document.title = `${String(config.appName || BRANDING_DEFAULTS.appName)} - ${String(config.subtitle || BRANDING_DEFAULTS.subtitle)}`;
}

function applyLogoWithFallback(logoEl, rawPath) {
    const candidates = [];

    if (rawPath) {
        candidates.push(String(rawPath));
        try {
            candidates.push(encodeURI(String(rawPath)));
        } catch (_) {}
        try {
            candidates.push(encodeURI(decodeURI(String(rawPath))));
        } catch (_) {}
    }

    candidates.push('sources/Logo Phantom Databas.png');
    candidates.push('sources/Logo%20Phantom%20Databas.png');
    candidates.push('sources/logo.png');

    const unique = [...new Set(candidates.filter(Boolean))];
    let idx = 0;

    const tryNext = () => {
        if (idx >= unique.length) {
            logoEl.style.display = 'none';
            return;
        }
        logoEl.style.display = 'block';
        logoEl.src = unique[idx++];
    };

    logoEl.onerror = tryNext;
    tryNext();
}

function handleVisibilityChange() {
    if (!authToken) return;

    const stamp = document.getElementById('lastUpdated');
    const live = document.getElementById('liveIndicator');

    if (document.hidden) {
        realtimePausedByVisibility = true;
        stopRealtimeUpdates();
        if (live) live.style.opacity = '0.3';
        if (stamp) stamp.textContent = 'Pausado: pestaña inactiva';
        return;
    }

    // Al volver a la pestaña, reanudar solo si el usuario no lo desactivó.
    if (realtimeEnabled) {
        realtimePausedByVisibility = false;
        startRealtimeUpdates();
    }
}

async function validarSesionActiva() {
    try {
        const user = await fetchJson(`${API_URL}/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        currentUser = user;
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        showApp();
    } catch (error) {
        console.warn('Sesión inválida o vencida:', error.message);
        logout();
    }
}

// === AUTENTICACIÓN ===
function showLogin() {
    const ids = ['loginSection', 'registerSection', 'miCuentaSection', 'dashboardSection', 'datosSection', 'databasesSection', 'importarSection', 'exportarSection', 'altasAgentesSection', 'lineasSection', 'cambiosBajasSection', 'qrSection', 'usuariosSection', 'auditoriaSection', 'estadoAgentesSection', 'alertasSection'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = id === 'loginSection' ? 'block' : 'none';
    });

    const nav = document.querySelector('.navbar');
    const sidebar = document.querySelector('.sidebar');
    const footer = document.querySelector('footer');
    if (nav) nav.style.display = 'none';
    if (sidebar) sidebar.style.display = 'none';
    if (footer) footer.style.display = 'none';
    toggleSidebar(false);
    stopRealtimeUpdates();
    stopInactivityTracking();
}

function showRegister() {
    document.getElementById('loginSection').style.display = 'none';
    document.getElementById('registerSection').style.display = 'block';
}

function showApp() {
    document.getElementById('loginSection').style.display = 'none';
    document.getElementById('registerSection').style.display = 'none';
    document.querySelector('.navbar').style.display = 'flex';
    document.querySelector('.sidebar').style.display = 'block';
    document.querySelector('footer').style.display = 'block';
    toggleSidebar(false);
    applyRoleBasedUI();
    if (!isLimitedViewer()) {
        loadServerVersionInfo();
        cargarAccesoServidorLocal();
        cargarPermisosBrandingAdmin();
        syncRealtimeControls();
        startRealtimeUpdates();
        refreshAlertBadgeAndNotify(false);
    } else {
        stopRealtimeUpdates();
    }
    loadSection(isLimitedViewer() ? 'miCuenta' : 'dashboard');
    startInactivityTracking();
    setTimeout(() => {
        applyQrDeepLinkIfPresent().catch((err) => console.warn('Deep link QR no aplicado:', err?.message || err));
    }, 120);
}

async function login(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    try {
        const data = await fetchJson(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        authToken = data.access_token;
        apiClient.setToken(authToken);
        currentUser = data.usuario;

        localStorage.setItem('authToken', authToken);
        localStorage.setItem('currentUser', JSON.stringify(currentUser));

        showApp();
        if (!isLimitedViewer()) {
            loadDashboardData();
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function registrar(e) {
    e.preventDefault();
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const fullName = document.getElementById('regFullName').value;
    const password = document.getElementById('regPassword').value;
    const mode = document.getElementById('regAccountMode')?.value || 'normal';

    try {
        await fetchJson(`${API_URL}/auth/${mode === 'temporal' ? 'registrar-temporal' : 'registrar'}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                email,
                nombre_completo: fullName,
                password,
                dias_vigencia: 10,
            })
        });

        alert(mode === 'temporal' ? 'Registro temporal exitoso. Ahora inicia sesión.' : 'Registro exitoso. Ahora inicia sesión.');
        document.getElementById('registerSection').style.display = 'none';
        document.getElementById('loginSection').style.display = 'block';
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    apiClient.clearToken();
    localStorage.removeItem('currentUser');
    currentServerAccessUrl = '';
    brandingManageEnabled = false;
    stopRealtimeUpdates();
    stopInactivityTracking();
    
    // Cerrar modal de aviso de inactividad si existe
    const warningModal = document.getElementById('inactivityWarningModal');
    if (warningModal) warningModal.remove();
    
    showLogin();
}

async function cargarResumenAutoservicio() {
    const container = document.getElementById('selfServiceSummaryContainer');
    const requestContainer = document.getElementById('selfServiceRequestContainer');
    if (!container) return;

    container.innerHTML = '<p class="hint">Cargando coincidencias reales de tu cuenta...</p>';
    if (requestContainer) requestContainer.innerHTML = '';

    try {
        const result = await apiClient.getSelfServiceResumen();
        const usuario = result?.usuario || {};
        const agentes = Array.isArray(result?.agentes) ? result.agentes : [];

        let html = `
            <div class="card" style="padding:14px;border:1px solid #d8e6f4;border-radius:12px;background:#f9fcff;">
                <strong>Usuario:</strong> ${escapeHtml(usuario.nombre_completo || usuario.username || 'Usuario')}<br>
                <strong>Email:</strong> ${escapeHtml(usuario.email || '-')}<br>
                <strong>Tipo de cuenta:</strong> ${usuario.es_temporal ? 'Temporal limitada' : 'Normal limitada'}
            </div>
        `;

        if (!agentes.length) {
            html += '<p class="hint" style="margin-top:10px;">No se encontró una coincidencia activa por email o nombre en la base. Si tu registro existe con otro dato, un administrador deberá vincularlo corrigiendo tu información.</p>';
        } else {
            html += '<table class="data-table" style="margin-top:10px;"><thead><tr><th>ID</th><th>Nombre</th><th>Email</th><th>Teléfono</th><th>VoIP</th><th>Deuda total</th><th>Saldo acumulado</th><th>Semanas pendientes</th></tr></thead><tbody>';
            agentes.forEach((agente) => {
                html += `
                    <tr>
                        <td>${agente.id}</td>
                        <td>${escapeHtml(agente.nombre || '-')}</td>
                        <td>${escapeHtml(agente.email || '-')}</td>
                        <td>${escapeHtml(agente.telefono || '-')}</td>
                        <td>${escapeHtml(agente.numero_voip || '-')}</td>
                        <td>$${Number(agente.deuda_total || 0).toFixed(2)} MXN</td>
                        <td>$${Number(agente.saldo_acumulado || 0).toFixed(2)} MXN</td>
                        <td>${Number(agente.semanas_pendientes || 0)}</td>
                    </tr>
                `;
            });
            html += '</tbody></table>';
        }

        container.innerHTML = html;

        if (requestContainer && usuario.es_temporal) {
            const requestState = String(usuario.solicitud_permiso_estado || 'none').toLowerCase();
            if (requestState === 'pending') {
                requestContainer.innerHTML = '<p class="hint">Ya existe una solicitud pendiente para convertir tu cuenta a usuario normal limitado.</p>';
            } else {
                requestContainer.innerHTML = `
                    <div class="card" style="padding:14px;border:1px solid #d8e6f4;border-radius:12px;background:#fff;">
                        <h3 style="margin-bottom:8px;">Solicitar Cuenta Normal Limitada</h3>
                        <p class="hint">Si ya no necesitas acceso temporal, puedes pedir que tu cuenta quede como usuario normal limitado conservando solo vista de autoservicio.</p>
                        <button type="button" class="btn" onclick="solicitarCuentaNormalLimitada()">Solicitar cambio</button>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<p style="color:#b00020;">No fue posible cargar tu consulta limitada: ${escapeHtml(error.message || 'Error desconocido')}</p>`;
    }
}

async function solicitarCuentaNormalLimitada() {
    if (!currentUser?.id) {
        alert('No se pudo identificar tu usuario actual.');
        return;
    }
    const motivo = await showAppPrompt('Describe brevemente por qué deseas conservar la cuenta como usuario normal limitado:', {
        title: 'Solicitar cuenta normal limitada',
        placeholder: 'Motivo opcional',
        acceptText: 'Solicitar',
    }) || '';
    try {
        await apiClient.solicitarPermisoTemporal(currentUser.id, { rol_solicitado: 'viewer', motivo });
        alert('Solicitud enviada. Un administrador deberá aprobarla.');
        await cargarResumenAutoservicio();
    } catch (error) {
        console.error('Error:', error);
        alert('Error enviando solicitud: ' + error.message);
    }
}

function startInactivityTracking() {
    stopInactivityTracking();
    
    // En mobile, usar heartbeat cada 2 minutos para mantener sesión activa
    // Sin esto, si pantalla se apaga, se cuenta como inactividad
    if (IS_MOBILE_DEVICE()) {
        inactivityHeartbeatInterval = setInterval(() => {
            if (authToken && !sessionCloseInProgress) {
                resetInactivityTimer();
            }
        }, 2 * 60 * 1000); // 2 minutos
    }
    
    // Eventos de usuario normales
    INACTIVITY_EVENTS.forEach((eventName) => {
        document.addEventListener(eventName, resetInactivityTimer, { passive: true });
    });
    
    // Ignorar cambios de visibilidad: si el usuario minimiza/bloquea pantalla
    // no cuenta como inactividad
    document.addEventListener('visibilitychange', onVisibilityChange, { passive: true });
    
    resetInactivityTimer();
}

function stopInactivityTracking() {
    if (inactivityTimer) {
        clearTimeout(inactivityTimer);
        inactivityTimer = null;
    }
    if (inactivityWarningTimer) {
        clearTimeout(inactivityWarningTimer);
        inactivityWarningTimer = null;
    }
    if (inactivityHeartbeatInterval) {
        clearInterval(inactivityHeartbeatInterval);
        inactivityHeartbeatInterval = null;
    }
    INACTIVITY_EVENTS.forEach((eventName) => {
        document.removeEventListener(eventName, resetInactivityTimer, { passive: true });
    });
    document.removeEventListener('visibilitychange', onVisibilityChange, { passive: true });
}

// Cuando el tab se oculta/muestra, resetear inactividad
// Esto evita logout al cambiar de app en mobile
function onVisibilityChange() {
    if (!document.hidden && authToken && !sessionCloseInProgress) {
        resetInactivityTimer();
    }
}

function resetInactivityTimer() {
    if (!authToken || sessionCloseInProgress) return;
    
    // Limpiar timers anteriores
    if (inactivityTimer) clearTimeout(inactivityTimer);
    if (inactivityWarningTimer) clearTimeout(inactivityWarningTimer);
    
    // Aviso 5 minutos antes de expirar
    inactivityWarningTimer = setTimeout(() => {
        if (!authToken || sessionCloseInProgress) return;
        showInactivityWarning();
    }, INACTIVITY_TIMEOUT_MS - INACTIVITY_WARNING_BEFORE_CLOSE_MS);
    
    // Cierre final
    inactivityTimer = setTimeout(() => {
        if (!authToken || sessionCloseInProgress) return;
        forceSessionClose('inactivity_timeout', {
            notify: true,
            reload: false,
            message: 'La sesión se cerró por inactividad prolongada.'
        });
    }, INACTIVITY_TIMEOUT_MS);
}

// Mostrar aviso de expiración con opción de extender
function showInactivityWarning() {
    const timeRemainingMin = INACTIVITY_WARNING_BEFORE_CLOSE_MS / 60 / 1000;
    
    // Crear modal de aviso
    const modal = document.createElement('div');
    modal.id = 'inactivityWarningModal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    
    modal.innerHTML = `
        <div style="
            background: white;
            padding: 30px;
            border-radius: 8px;
            max-width: 400px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            text-align: center;
        ">
            <h2 style="margin: 0 0 15px 0; color: #ff9800;">⏰ Sesión Expirando</h2>
            <p style="margin: 0 0 20px 0; color: #666;">
                Por inactividad, tu sesión cerrará en <strong>${Math.ceil(timeRemainingMin)} minutos</strong>.
            </p>
            <p style="margin: 0 0 25px 0; color: #999; font-size: 13px;">
                Haz clic en "Extender sesión" para continuar trabajando.
            </p>
            <div style="display: flex; gap: 10px; justify-content: center;">
                <button onclick="extendSession()" style="
                    padding: 10px 20px;
                    background: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: bold;
                ">
                    ✓ Extender sesión
                </button>
                <button onclick="closeInactivityWarning(true)" style="
                    padding: 10px 20px;
                    background: #999;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                ">
                    Cerrar sesión
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function closeInactivityWarning(forceClose = false) {
    const modal = document.getElementById('inactivityWarningModal');
    if (modal) modal.remove();
    
    if (forceClose) {
        forceSessionClose('inactivity_timeout', {
            notify: false,
            reload: false
        });
    }
}

// Extender la sesión: resetear timers
function extendSession() {
    closeInactivityWarning(false);
    resetInactivityTimer();
    
    // Feedback visual
    const msg = document.createElement('div');
    msg.textContent = '✓ Sesión extendida';
    msg.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #4CAF50;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        font-size: 13px;
        zIndex: 9999;
    `;
    document.body.appendChild(msg);
    setTimeout(() => msg.remove(), 2000);
}

function forceSessionClose(reason, { notify = true, reload = false, message = '' } = {}) {
    if (sessionCloseInProgress) return;
    sessionCloseInProgress = true;

    const finalMessage = message || (reason === 'inactivity_timeout'
        ? 'La sesión se cerró por inactividad.'
        : 'La sesión expiró o ya no es válida.');

    if (notify) {
        showAppAlert(finalMessage, { tone: 'warning', title: 'Sesión cerrada' });
    }

    logout();

    if (reload) {
        setTimeout(() => {
            window.location.reload();
        }, 250);
    }

    setTimeout(() => {
        sessionCloseInProgress = false;
    }, 1200);
}

async function cargarPermisosBrandingAdmin() {
    const wrapEl = document.getElementById('brandingAdminWrap');
    const inputEl = document.getElementById('brandingLogoInput');
    if (wrapEl) wrapEl.style.display = 'none';
    if (inputEl) inputEl.value = '';

    if (!currentUser?.es_admin) {
        brandingManageEnabled = false;
        return;
    }

    try {
        const res = await apiClient.getBrandingAdminStatus();
        brandingManageEnabled = Boolean(res.can_manage_logo);
        if (res.branding) {
            applyBrandingConfig(res.branding);
        }
        if (wrapEl && brandingManageEnabled) {
            wrapEl.style.display = 'inline-flex';
        }
    } catch (error) {
        console.warn('No se pudieron cargar permisos de branding:', error.message);
        brandingManageEnabled = false;
    }
}

function abrirSelectorLogo() {
    if (!brandingManageEnabled) {
        alert('Solo un administrador desde el servidor local puede cambiar el logo.');
        return;
    }
    const inputEl = document.getElementById('brandingLogoInput');
    if (inputEl) {
        inputEl.click();
    }
}

async function subirNuevoLogo(event) {
    const inputEl = event?.target;
    const btnEl = document.getElementById('changeLogoBtn');
    const file = inputEl?.files?.[0];
    if (!file) {
        return;
    }

    try {
        if (btnEl) {
            btnEl.disabled = true;
            btnEl.textContent = 'Subiendo...';
        }
        const res = await apiClient.uploadBrandingLogo(file);
        if (res.branding) {
            applyBrandingConfig(res.branding);
        } else {
            await loadBrandingConfig();
        }
        alert('Logo actualizado correctamente.');
    } catch (error) {
        alert('Error cambiando logo: ' + error.message);
    } finally {
        if (inputEl) inputEl.value = '';
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.textContent = 'Cambiar logo';
        }
    }
}

async function cargarAccesoServidorLocal() {
    const valueEl = document.getElementById('serverAccessValue');
    const wrapEl = document.getElementById('serverAccessWrap');
    const btnEl = document.getElementById('copyServerAccessBtn');
    const hintEl = document.getElementById('serverAccessHint');
    if (!valueEl || !wrapEl || !btnEl) {
        return;
    }

    valueEl.textContent = 'cargando...';
    if (hintEl) hintEl.textContent = '';
    btnEl.disabled = true;

    try {
        const res = await apiClient.getLocalNetworkInfo();
        const preferred = String(res.share_url_preferida || '').trim();
        const url = String(res.share_url || '').trim();
        const noPort = String(res.share_url_no_port || '').trim();
        const ip = String(res.ip_local || '').trim();
        currentServerAccessUrl = preferred || url;
        currentServerAccessNoPortUrl = noPort;
        valueEl.textContent = currentServerAccessUrl || ip || 'No disponible';
        wrapEl.title = ip ? `IP local: ${ip}` : 'Acceso local';
        if (hintEl) {
            if (noPort && noPort !== currentServerAccessUrl) {
                hintEl.textContent = `Alternativa: ${noPort}`;
            } else if (res.usa_puerto_por_defecto) {
                hintEl.textContent = 'Puerto por defecto detectado; se puede omitir.';
            } else {
                hintEl.textContent = '';
            }
        }
        btnEl.disabled = !(currentServerAccessUrl || ip);
    } catch (error) {
        console.warn('No se pudo obtener IP local:', error.message);
        currentServerAccessUrl = '';
        currentServerAccessNoPortUrl = '';
        valueEl.textContent = 'No disponible';
        wrapEl.title = 'No se pudo detectar IP local';
        if (hintEl) hintEl.textContent = '';
        btnEl.disabled = true;
    }
}

async function copiarAccesoServidor() {
    const valueEl = document.getElementById('serverAccessValue');
    const btnEl = document.getElementById('copyServerAccessBtn');
    const text = (currentServerAccessUrl || valueEl?.textContent || '').trim();
    if (!text || text.toLowerCase() === 'cargando...' || text.toLowerCase() === 'no disponible') {
        alert('Acceso local no disponible todavía.');
        return;
    }

    try {
        await copiarTextoPortapapeles(text);
        if (btnEl) {
            const original = btnEl.textContent;
            btnEl.textContent = 'Copiado';
            setTimeout(() => {
                btnEl.textContent = original || 'Copiar';
            }, 1200);
        }
    } catch (error) {
        alert('No se pudo copiar automáticamente. URL: ' + text);
    }
}

async function copiarTextoPortapapeles(text) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
    }
    const temp = document.createElement('textarea');
    temp.value = text;
    temp.style.position = 'fixed';
    temp.style.opacity = '0';
    document.body.appendChild(temp);
    temp.focus();
    temp.select();
    document.execCommand('copy');
    document.body.removeChild(temp);
}

async function copiarComandoAutostart(action, btnEl = null) {
    const actionValue = String(action || '').trim();
    if (!actionValue) return;

    const command = `.\\manage_autostart.bat ${actionValue}`;
    const hintEl = document.getElementById('autostartHint');
    try {
        await copiarTextoPortapapeles(command);
        if (hintEl) {
            hintEl.textContent = `Comando copiado: ${command}`;
        }
        if (btnEl) {
            const original = btnEl.textContent;
            btnEl.textContent = 'Copiado';
            setTimeout(() => {
                btnEl.textContent = original || 'Copiar';
            }, 1200);
        }
    } catch (error) {
        if (hintEl) {
            hintEl.textContent = `No se pudo copiar. Ejecuta manualmente: ${command}`;
        }
        alert(`No se pudo copiar el comando. Ejecuta manualmente:\n${command}`);
    }
}

function startRealtimeUpdates() {
    stopRealtimeUpdates();
    if (document.hidden) {
        realtimePausedByVisibility = true;
        const stamp = document.getElementById('lastUpdated');
        const live = document.getElementById('liveIndicator');
        if (live) live.style.opacity = '0.3';
        if (stamp) stamp.textContent = 'Pausado: pestaña inactiva';
        return;
    }

    if (!realtimeEnabled) {
        realtimePausedByVisibility = false;
        const live = document.getElementById('liveIndicator');
        const stamp = document.getElementById('lastUpdated');
        if (live) live.style.opacity = '0.3';
        if (stamp) stamp.textContent = 'Pausado: tiempo real desactivado';
        return;
    }

    realtimePausedByVisibility = false;
    const live = document.getElementById('liveIndicator');
    const stamp = document.getElementById('lastUpdated');
    if (live) live.style.opacity = '1';
    if (stamp) stamp.textContent = `Activo: ${Math.round(realtimeMs / 1000)}s`; 

    realtimeInterval = setInterval(async () => {
        if (!authToken) return;
        try {
            await refreshAlertBadgeAndNotify(false);
            if (currentSection === 'dashboard') {
                await loadDashboardData(false);
            }
            if (currentSection === 'auditoria') {
                await cargarAuditoriaInterna(false);
            }
            const stamp = document.getElementById('lastUpdated');
            if (stamp) {
                stamp.textContent = `Actualizado: ${new Date().toLocaleTimeString()}`;
            }
        } catch (error) {
            console.error('Error en actualización en tiempo real:', error);
        }
    }, realtimeMs);
}

function stopRealtimeUpdates() {
    if (realtimeInterval) {
        clearInterval(realtimeInterval);
        realtimeInterval = null;
    }
}

async function refreshAlertBadgeAndNotify(showPopup = false) {
    if (!authToken || alertPollingPromise) return;
    alertPollingPromise = (async () => {
        try {
            const data = await fetchJson(`${API_URL}/alertas/?solo_activas=true&limit=20`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            const items = Array.isArray(data?.items) ? data.items : [];
            const unread = items.filter(a => !a.leida);
            const badge = document.getElementById('alertasMenuBadge');
            if (badge) {
                badge.style.display = unread.length > 0 ? 'inline-block' : 'none';
                badge.textContent = unread.length > 99 ? '99+' : String(unread.length || '');
            }

            if (showPopup && unread.length > 0) {
                const newest = unread[0];
                const stamp = `${newest.id}:${newest.fecha_envio || ''}`;
                if (stamp !== lastAlertNotificationStamp) {
                    lastAlertNotificationStamp = stamp;
                    alert(`Nueva alerta del sistema: ${newest.titulo}\n\n${newest.mensaje}`);
                }
            }
        } catch (_) {
            // Ignore transient alert refresh failures.
        } finally {
            alertPollingPromise = null;
        }
    })();
    await alertPollingPromise;
}

function syncRealtimeControls() {
    const enabled = document.getElementById('realtimeEnabled');
    const interval = document.getElementById('realtimeInterval');
    if (enabled) {
        enabled.value = realtimeEnabled ? 'on' : 'off';
    }
    if (interval) {
        interval.value = String(realtimeMs);
    }
}

function aplicarConfigTiempoReal() {
    const enabled = document.getElementById('realtimeEnabled');
    const interval = document.getElementById('realtimeInterval');

    realtimeEnabled = (enabled?.value || 'on') === 'on';
    realtimeMs = Number(interval?.value || 20000);

    localStorage.setItem('realtimeEnabled', realtimeEnabled ? 'on' : 'off');
    localStorage.setItem('realtimeMs', String(realtimeMs));

    startRealtimeUpdates();

    // Refresco puntual al cambiar configuración en sección activa.
    if (!realtimePausedByVisibility && realtimeEnabled) {
        if (currentSection === 'dashboard') {
            loadDashboardData(false);
        }
        if (currentSection === 'auditoria') {
            cargarAuditoriaInterna(false);
        }
    }
}

// === NAVEGACIÓN ===
function loadSection(section, eventRef = null) {
    if (!canAccessSection(section)) {
        alert('Tu rol no tiene acceso a esta sección.');
        section = 'dashboard';
    }
    const previousSection = currentSection;
    currentSection = section;
    if (previousSection === 'qrScan' && section !== 'qrScan' && typeof detenerEscanerQR === 'function') {
        detenerEscanerQR().catch(() => {});
    }
    if (section !== 'altasAgentes' && altasTourActive) {
        closeAltasTour();
    }
    // Ocultar todas las secciones
    const _miCuentaEl = document.getElementById('miCuentaSection');
    if (_miCuentaEl) _miCuentaEl.style.display = 'none';
    document.getElementById('dashboardSection').style.display = 'none';
    document.getElementById('datosSection').style.display = 'none';
    document.getElementById('databasesSection').style.display = 'none';
    document.getElementById('importarSection').style.display = 'none';
    const _exportarEl = document.getElementById('exportarSection');
    if (_exportarEl) _exportarEl.style.display = 'none';
    document.getElementById('altasAgentesSection').style.display = 'none';
    const _lineasEl = document.getElementById('lineasSection');
    if (_lineasEl) _lineasEl.style.display = 'none';
    document.getElementById('cambiosBajasSection').style.display = 'none';
    document.getElementById('qrScanSection').style.display = 'none';
    document.getElementById('qrSection').style.display = 'none';
    document.getElementById('usuariosSection').style.display = 'none';
    document.getElementById('auditoriaSection').style.display = 'none';
    const _estadoAgentesEl = document.getElementById('estadoAgentesSection');
    if (_estadoAgentesEl) _estadoAgentesEl.style.display = 'none';
    const _alertasEl = document.getElementById('alertasSection');
    if (_alertasEl) _alertasEl.style.display = 'none';

    // Remover clase active
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));

    switch (section) {
        case 'miCuenta':
            document.getElementById('miCuentaSection').style.display = 'block';
            cargarResumenAutoservicio();
            break;
        case 'dashboard':
            document.getElementById('dashboardSection').style.display = 'block';
            loadDashboardData();
            break;
        case 'datos':
            document.getElementById('datosSection').style.display = 'block';
            cargarDatosDatabases();
            break;
        case 'databases':
            document.getElementById('databasesSection').style.display = 'block';
            cargarDatabases();
            break;
        case 'importar':
            document.getElementById('importarSection').style.display = 'block';
            break;
        case 'exportar':
            document.getElementById('exportarSection').style.display = 'block';
            exportCargarTablas();
            break;
        case 'altasAgentes':
            document.getElementById('altasAgentesSection').style.display = 'block';
            cargarLineasYAgentes();
            maybeAutoStartAltasTour();
            break;
        case 'lineas':
            document.getElementById('lineasSection').style.display = 'block';
            cargarLineasGestion();
            break;
        case 'cambiosBajas':
            document.getElementById('cambiosBajasSection').style.display = 'block';
            cargarAgentesGestion();
            break;
        case 'qrScan':
            document.getElementById('qrScanSection').style.display = 'block';
            setDefaultWeeklyDates();
            renderNativeQrControls();
            setTimeout(() => {
                cargarCamarasDisponibles(true).catch(() => {});
            }, 120);
            break;
        case 'qr':
            document.getElementById('qrSection').style.display = 'block';
            setDefaultWeeklyDates();
            if (typeof qrSetTab === 'function') qrSetTab('pago');
            cargarCuotaSemanal();
            cargarConfiguracionRespaldos();
            cargarRespaldos();
            break;
        case 'usuarios':
            document.getElementById('usuariosSection').style.display = 'block';
            cargarUsuarios();
            cargarCapacidadesRoles();
            break;
        case 'auditoria':
            document.getElementById('auditoriaSection').style.display = 'block';
            cargarAuditoria();
            break;
        case 'estadoAgentes':
            document.getElementById('estadoAgentesSection').style.display = 'block';
            cargarEstadoAgentes();
            break;
        case 'alertas':
            document.getElementById('alertasSection').style.display = 'block';
            cargarAlertas();
            break;
    }

    if (eventRef?.target) {
        eventRef.target.classList.add('active');
    } else {
        const active = document.querySelector(`.menu-item[onclick*="${section}"]`);
        if (active) {
            active.classList.add('active');
        }
    }

    if (isMobileViewport()) {
        toggleSidebar(false);
    }
}

function pickPreferredDatabase(databases) {
    if (!Array.isArray(databases) || !databases.length) {
        return '';
    }
    if (databases.includes(DEFAULT_AGENT_DATABASE)) {
        return DEFAULT_AGENT_DATABASE;
    }
    if (databases.includes('database_manager')) {
        return 'database_manager';
    }
    return databases[0];
}

function getStartupQueryParams() {
    try {
        return new URLSearchParams(window.location.search || '');
    } catch (_) {
        return new URLSearchParams('');
    }
}

async function applyQrDeepLinkIfPresent() {
    const params = getStartupQueryParams();
    const section = (params.get('section') || '').trim();
    const agenteId = Number(params.get('agente_id') || 0);
    const semana = (params.get('semana') || '').trim();
    const autoverify = ['1', 'true', 'yes'].includes((params.get('autoverify') || '').trim().toLowerCase());

    if (section !== 'qr' && !agenteId) {
        return;
    }

    if (section === 'qr' || agenteId > 0) {
        if (!canAdmin()) {
            return;
        }
        loadSection('qr');
    }

    if (agenteId > 0) {
        const qrInput = document.getElementById('qrAgenteId');
        const pagoInput = document.getElementById('pagoAgenteId');
        if (qrInput) qrInput.value = String(agenteId);
        if (pagoInput) pagoInput.value = String(agenteId);
    }
    if (semana) {
        const qrSemana = document.getElementById('qrSemana');
        const pagoSemana = document.getElementById('pagoSemana');
        if (qrSemana) qrSemana.value = semana;
        if (pagoSemana) pagoSemana.value = semana;
    }

    if (autoverify && agenteId > 0) {
        await verificarAgenteQR();
        await consultarResumenPagoActual(false);
    }
}

function isAgentDataTableContext(dbName, tableName) {
    return dbName === 'database_manager' && (
        tableName === 'agentes_operativos' ||
        tableName === 'datos_importados'
    );
}

// === DASHBOARD ===
async function loadDashboardData(showErrors = true) {
    try {
        const summary = await apiClient.getDashboardSummary();
        const totals = summary.totals || {};
        const db = summary.database || {};
        const alerts = Array.isArray(summary.alerts) ? summary.alerts : [];
        const onlineUsers = Array.isArray(summary.online_users) ? summary.online_users : [];
        const imports = Array.isArray(summary.recent_imports) ? summary.recent_imports : [];
        const recentAgents = Array.isArray(summary.recent_agents) ? summary.recent_agents : [];
        const activitySeries = Array.isArray(summary.activity_7_days) ? summary.activity_7_days : [];

        document.getElementById('totalRegistros').textContent = totals.registros ?? 0;
        document.getElementById('totalActivos').textContent = totals.registros_activos ?? 0;
        document.getElementById('totalImportaciones').textContent = totals.importaciones ?? 0;
        document.getElementById('totalQR').textContent = totals.qr_generados ?? 0;
        document.getElementById('totalUsuariosOnline').textContent = totals.usuarios_online ?? 0;
        document.getElementById('totalInactivos').textContent = totals.registros_inactivos ?? 0;
        document.getElementById('totalQrPendientes').textContent = totals.qr_pendientes ?? 0;
        document.getElementById('totalAlertasPago').textContent = totals.alertas_pago_pendientes ?? 0;
        document.getElementById('totalSinLinea').textContent = totals.sin_linea ?? 0;
        document.getElementById('totalLineasActivas').textContent = totals.lineas_activas ?? 0;
        document.getElementById('totalLineasAsignadas').textContent = totals.lineas_asignadas_activas ?? 0;

        // Badge del menú Sin Línea
        const sinLineaMenuBadge = document.getElementById('estadoAgentesMenuBadge');
        const sinLineaMenuLi = document.getElementById('menuEstadoAgentes');
        const sinLineaTotal = totals.sin_linea ?? 0;
        if (sinLineaMenuBadge) {
            sinLineaMenuBadge.style.display = sinLineaTotal > 0 ? 'inline-block' : 'none';
            sinLineaMenuBadge.textContent = sinLineaTotal > 0 ? sinLineaTotal : '!';
        }
        if (sinLineaMenuLi) {
            sinLineaMenuLi.style.fontWeight = sinLineaTotal > 0 ? 'bold' : '';
        }

        const alertSummary = document.getElementById('alertSummary');
        if (alertSummary) {
            alertSummary.textContent = alerts.length
                ? `${alerts.length} alertas operativas activas`
                : 'Sin alertas operativas abiertas';
        }

        const alertsList = document.getElementById('alertsList');
        if (alertsList) {
            if (!alerts.length) {
                alertsList.innerHTML = '<p class="hint">No hay alertas accionables en este momento.</p>';
            } else {
                alertsList.innerHTML = alerts.map(item => {
                    const targetSection = item.action_section ? String(item.action_section) : '';
                    const actionButton = targetSection
                        ? `<button type="button" class="btn btn-small btn-secondary" onclick="loadSection('${escapeHtml(targetSection)}')">Ir</button>`
                        : '';
                    return `<div class="dashboard-alert ${escapeHtml(item.level || 'info')}">
                        <div>
                            <strong>${escapeHtml(item.title || 'Alerta')}</strong>
                            <span>${escapeHtml(item.detail || '')}</span>
                        </div>
                        ${actionButton}
                    </div>`;
                }).join('');
            }
        }

        const onlineSummary = document.getElementById('usuariosOnlineResumen');
        if (onlineSummary) {
            onlineSummary.textContent = `${totals.usuarios_online ?? 0} conectados recientemente de ${totals.usuarios ?? 0} usuarios activos`;
        }

        const onlineList = document.getElementById('usuariosOnlineList');
        if (onlineList) {
            if (!onlineUsers.length) {
                onlineList.innerHTML = '<p class="hint">No hay sesiones recientes.</p>';
            } else {
                const html = onlineUsers.map(u => {
                    const role = u.es_admin ? 'admin' : 'usuario';
                    const recency = formatRelativeAge(u.seconds_since_last_session);
                    const status = u.is_online ? 'Online' : 'Reciente';
                    return `<div class="dashboard-item">
                        <strong>${escapeHtml(u.username || 'N/A')}</strong>
                        <span>${escapeHtml(role)} · ${escapeHtml(status)} · ${escapeHtml(recency)}</span>
                    </div>`;
                }).join('');
                onlineList.innerHTML = html;
            }
        }

        const importSummary = document.getElementById('importStatsResumen');
        if (importSummary) {
            importSummary.textContent = `OK: ${totals.importaciones_exitosas ?? 0} · Fallidas: ${totals.importaciones_fallidas ?? 0} · Pagos pendientes semana: ${totals.pagos_pendientes_semana ?? 0}`;
        }

        const importList = document.getElementById('importRecentList');
        if (importList) {
            if (!imports.length) {
                importList.innerHTML = '<p class="hint">Sin importaciones recientes.</p>';
            } else {
                importList.innerHTML = imports.map(i => `<div class="dashboard-item">
                    <strong>${escapeHtml(i.archivo_nombre || 'archivo')}</strong>
                    <span>${escapeHtml(i.estado || 'N/A')} · ${escapeHtml(i.tabla_destino || '-')} · +${i.registros_importados ?? 0} / -${i.registros_fallidos ?? 0}</span>
                </div>`).join('');
            }
        }

        const dbSummary = document.getElementById('dbResumen');
        if (dbSummary) {
            dbSummary.textContent = `BD activa: ${db.name || 'N/A'} · Fuente agentes: ${db.agent_source || 'N/A'}`;
        }

        const dbInfo = document.getElementById('dbInfoList');
        if (dbInfo) {
            dbInfo.innerHTML = `<div class="dashboard-item"><strong>Tablas</strong><span>${db.tables ?? 0}</span></div>
                <div class="dashboard-item"><strong>Vistas</strong><span>${db.views ?? 0}</span></div>
                <div class="dashboard-item"><strong>Líneas activas</strong><span>${totals.lineas_activas ?? 0} · asignadas ${totals.lineas_asignadas_activas ?? 0}</span></div>
                <div class="dashboard-item"><strong>Agentes activos</strong><span>${totals.registros_activos ?? 0} / ${totals.registros ?? 0}</span></div>
                <div class="dashboard-item"><strong>Generado</strong><span>${summary.generated_at ? new Date(summary.generated_at).toLocaleString() : '-'}</span></div>`;
        }

        const recentAgentsSummary = document.getElementById('recentAgentsSummary');
        if (recentAgentsSummary) {
            recentAgentsSummary.textContent = `${recentAgents.length} registros recientes desde ${db.agent_source || 'BD principal'}`;
        }

        const recentAgentsList = document.getElementById('recentAgentsList');
        if (recentAgentsList) {
            if (!recentAgents.length) {
                recentAgentsList.innerHTML = '<p class="hint">No hay altas recientes.</p>';
            } else {
                recentAgentsList.innerHTML = recentAgents.map(agent => {
                    const status = agent.es_activo ? 'Activo' : 'Inactivo';
                    const qr = agent.has_qr ? 'Con QR' : 'Sin QR';
                    const created = agent.fecha_creacion ? new Date(agent.fecha_creacion).toLocaleString() : 'Sin fecha';
                    const displayName = getAgentDisplayName(agent);
                    return `<div class="dashboard-item">
                        <strong>${escapeHtml(displayName)}</strong>
                        <span>ID ${agent.id ?? '-'} · ${escapeHtml(status)} · ${escapeHtml(qr)}</span>
                        <span>${escapeHtml(created)}</span>
                    </div>`;
                }).join('');
            }
        }

        const activitySummary = document.getElementById('activitySummary');
        if (activitySummary) {
            const totalSeriesRegistros = activitySeries.reduce((acc, item) => acc + Number(item.registros || 0), 0);
            const totalSeriesImports = activitySeries.reduce((acc, item) => acc + Number(item.importaciones || 0), 0);
            activitySummary.textContent = `Últimos 7 días: ${totalSeriesRegistros} registros nuevos y ${totalSeriesImports} importaciones ejecutadas`;
        }

        const activityChart = document.getElementById('activityChart');
        if (activityChart) {
            activityChart.innerHTML = renderActivityChart(activitySeries);
        }

        cargarInfoAppMovil();
    } catch (error) {
        if (showErrors) {
            console.error('Error:', error);
        }
    }
}

async function cargarInfoAppMovil() {
    const infoEl = document.getElementById('phantomAppInfo');
    const btnEl = document.getElementById('phantomAppDownloadBtn');
    if (!infoEl || !btnEl) return;
    try {
        const res = await fetch('/api/download/phantom-app/info');
        if (!res.ok) throw new Error('no disponible');
        const data = await res.json();
        if (data.disponible) {
            infoEl.textContent = `Disponible · ${data.tamanio_mb} MB`;
            btnEl.style.display = '';
        } else {
            infoEl.textContent = 'La app no está disponible en este servidor.';
            btnEl.style.display = 'none';
        }
    } catch (_) {
        infoEl.textContent = 'No se pudo verificar la disponibilidad.';
        btnEl.style.display = 'none';
    }
}

function irAExportacionQRLotes() {
    loadSection('qr');
    setTimeout(() => {
        const target = document.getElementById('qrExportCard') || document.getElementById('qrExportSectionTitle');
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        qrExportCargarAgentes();
    }, 120);
}

// === DATOS ===
async function cargarDatosDatabases() {
    try {
        const select = document.getElementById('datosDatabaseSelect');
        if (!select) return;

        const prev = select.value;
        const result = await apiClient.getDatabases();
        const dbs = result.data || [];

        let html = '<option value="">-- Base de datos --</option>';
        dbs.forEach(db => {
            html += `<option value="${db}">${db}</option>`;
        });
        select.innerHTML = html;

        const preferred = pickPreferredDatabase(dbs);
        if (prev && dbs.includes(prev)) {
            select.value = prev;
        } else if (preferred) {
            select.value = preferred;
        } else if (dbs.length) {
            select.value = dbs[0];
        }

        currentDatosDatabase = select.value;
        await cargarTablas();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando bases de datos: ' + error.message);
    }
}

async function cargarTablas() {
    try {
        const dbSelect = document.getElementById('datosDatabaseSelect');
        const tableSelect = document.getElementById('tablasSelect');
        if (!dbSelect || !tableSelect) return;

        const dbName = dbSelect.value;
        currentDatosDatabase = dbName;
        if (!dbName) {
            tableSelect.innerHTML = '<option value="">-- Selecciona tabla --</option>';
            mostrarDatos([]);
            return;
        }

        const prevTable = tableSelect.value;
        const tablesResult = await apiClient.getTables(dbName);
        const tables = tablesResult.data || [];

        let html = '<option value="">-- Selecciona tabla --</option>';
        tables.forEach(t => {
            html += `<option value="${t}">${escapeHtml(formatDbObjectOption(t))}</option>`;
        });
        tableSelect.innerHTML = html;

        if (prevTable && tables.includes(prevTable)) {
            tableSelect.value = prevTable;
        } else if (tables.includes('agentes_operativos')) {
            tableSelect.value = 'agentes_operativos';
        } else if (tables.includes('datos_importados')) {
            tableSelect.value = 'datos_importados';
        } else if (tables.length) {
            tableSelect.value = tables[0];
        }

        await cargarTodosLosDatos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando tablas: ' + error.message);
    }
}

async function cargarTodosLosDatos(allowRecovery = true) {
    try {
        const dbName = document.getElementById('datosDatabaseSelect')?.value || '';
        const tableName = document.getElementById('tablasSelect')?.value || '';
        if (!dbName || !tableName) {
            mostrarDatos([]);
            return;
        }

        const search = document.getElementById('searchInput').value.trim();
        const sort = getDatosSortConfig();
        const data = await apiClient.getTableData(dbName, tableName, 500, 0, sort.orderBy, sort.direction);
        let rows = data.data || [];
        // Filtrar inactivos si es tabla de agentes
        if (isAgentDataTableContext(dbName, tableName)) {
            rows = rows.filter(r => r.es_activo !== false);
        }
        if (search) {
            const s = search.toLowerCase();
            rows = rows.filter(row => Object.values(row).some(v => String(v ?? '').toLowerCase().includes(s)));
        }
        mostrarDatos(rows);
    } catch (error) {
        console.error('Error:', error);
        // Recuperacion automatica para tablas canonicas de agentes en migration legacy.
        if (allowRecovery && (document.getElementById('datosDatabaseSelect')?.value || '') === 'database_manager') {
            const tableSelect = document.getElementById('tablasSelect');
            const current = tableSelect?.value || '';
            const fallback = current === 'agentes_operativos' ? 'datos_importados' : (current === 'datos_importados' ? 'agentes_operativos' : '');
            if (fallback) {
                try {
                    const tablesResult = await apiClient.getTables('database_manager');
                    const tables = tablesResult.data || [];
                    if (tableSelect && tables.includes(fallback)) {
                        tableSelect.value = fallback;
                        await cargarTodosLosDatos(false);
                        return;
                    }
                } catch (_) {
                    // noop: keep original error message below
                }
            }
        }
        alert('Error al cargar todos los datos: ' + error.message);
    }
}

async function consultarUnDato() {
    const value = document.getElementById('singleSearchInput').value.trim();
    if (!value) {
        alert('Ingresa un ID o UUID.');
        return;
    }

    try {
        const dbName = document.getElementById('datosDatabaseSelect')?.value || '';
        const tableName = document.getElementById('tablasSelect')?.value || '';
        if (!dbName || !tableName) {
            alert('Selecciona base de datos y tabla.');
            return;
        }

        const where = /^\d+$/.test(value)
            ? `id = ${Number(value)}`
            : `uuid = '${value.replace(/'/g, "''")}'`;

        const sql = `SELECT * FROM \`${tableName}\` WHERE ${where} LIMIT 1`;
        const result = await apiClient.executeQuery(dbName, sql);
        const rows = result.data || [];
        if (!rows.length) {
            alert('No se encontró un registro exacto con ese valor en la tabla seleccionada.');
            return;
        }
        
        // Mostrar los datos
        mostrarDatos(rows);
        
        // Si es una tabla de agentes (datos_importados) y tiene QR, mostrarlo
        const registro = rows[0];
        if (isAgentDataTableContext(dbName, tableName) && registro.id && registro.qr_filename) {
            setTimeout(() => {
                mostrarQrParaAgente(registro.id, registro.nombre || 'Agente');
            }, 500);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('No se encontró el registro: ' + error.message);
    }
}

async function mostrarQrParaAgente(agenteId, agenteName) {
    /**
     * Muestra el QR de un agente consultado individualmente
     */
    try {
        const result = await apiClient.getQrAgente(agenteId);
        const data = result.data || {};
        
        // Crear modal para mostrar el QR con estilos unificados de la aplicacion
        const modal = document.createElement('div');
        modal.className = 'modal-overlay-qr';
        
        const content = document.createElement('div');
        content.className = 'modal-content-qr';
        
        content.innerHTML = `
            <button type="button" class="close-modal-qr" onclick="this.closest('.modal-overlay-qr').remove()">
                ✕
            </button>
            <h2>QR del Agente</h2>
            <p class="qr-modal-meta">
                <strong>${agenteName}</strong><br>
                <span>ID: ${agenteId}</span>
            </p>
            <div id="qr-preview-container" class="qr-modal-preview"></div>
            <div class="qr-modal-actions">
                <button type="button" class="btn btn-secondary" onclick="descargarQrAgente(${agenteId})">
                    📥 Descargar PNG
                </button>
                <button type="button" class="btn" onclick="copiarUrlQr('${String(data.public_url || '').replace(/'/g, "\\'")}')">
                    📋 Copiar URL
                </button>
            </div>
            <p class="qr-modal-link">
                ${data.public_url ? `<a href="${data.public_url}" target="_blank">Abrir en navegador ↗</a>` : 'URL no disponible'}
            </p>
        `;
        
        modal.appendChild(content);
        document.body.appendChild(modal);
        
        // Renderizar QR en el contenedor
        renderSimpleQR(data.public_url, 'qr-preview-container');
        
    } catch (error) {
        console.error('Error mostrando QR:', error);
        alert('No se pudo mostrar el QR: ' + error.message);
    }
}

async function buscarDatos() {
    const search = document.getElementById('searchInput').value;
    try {
        const dbName = document.getElementById('datosDatabaseSelect')?.value || '';
        const tableName = document.getElementById('tablasSelect')?.value || '';
        if (!dbName || !tableName) {
            mostrarDatos([]);
            return;
        }

        const sort = getDatosSortConfig();
        const data = await apiClient.getTableData(dbName, tableName, 500, 0, sort.orderBy, sort.direction);
        let rows = data.data || [];
        const term = (search || '').trim().toLowerCase();
        if (term) {
            rows = rows.filter(row => Object.values(row).some(v => String(v ?? '').toLowerCase().includes(term)));
        }
        mostrarDatos(rows);
    } catch (error) {
        console.error('Error:', error);
    }
}

function mostrarDatos(datos) {
    const container = document.getElementById('datosContainer');
    if (datos.length === 0) {
        container.innerHTML = '<p style="padding: 20px; text-align: center; color: #999;">No hay datos disponibles</p>';
        return;
    }

    const columnas = Object.keys(datos[0]).filter(col => col.toLowerCase() !== 'empresa');
    const dbName = document.getElementById('datosDatabaseSelect')?.value || '';
    const tableName = document.getElementById('tablasSelect')?.value || '';
    const editableContext = isAgentDataTableContext(dbName, tableName);
    const isAgentTable = isAgentDataTableContext(dbName, tableName) || tableName === 'registro_agentes';
    
    let html = '<table class="data-table"><thead><tr>';

    columnas.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '<th>Acciones</th></tr></thead><tbody>';

    datos.forEach(fila => {
        html += '<tr>';
        columnas.forEach(col => {
            const valor = fila[col] ?? '';
            // Resaltar si es texto importante
            const isName = col.toLowerCase() === 'nombre';
            const cellStyle = isName ? 'style="font-weight: 600; color: #0f4567;"' : '';
            html += `<td ${cellStyle}>${valor}</td>`;
        });
        
        // Indicador de QR y acciones
        let hasQr = fila.qr_filename !== null && fila.qr_filename !== undefined && fila.qr_filename !== '';
        let qrIndicator = hasQr ? '🔷' : '⭕';
        let qrTitle = hasQr ? 'QR disponible - Click para ver' : 'Sin QR';
        
        if (editableContext && Number.isFinite(Number(fila.id))) {
            let actionHtml = `<td style="display: flex; gap: 4px; flex-wrap: wrap;">`;
            if (canAdmin()) {
                actionHtml += `<button onclick="editarDato(${fila.id}, '${(fila.uuid || '').replace(/'/g, "\\'")}')" class="btn btn-small" title="Editar registro">✏️ Editar</button>`;
            }
            
            // Si es agente y tiene QR, mostrar botón para verlo
            if (isAgentTable) {
                const qrName = (String(fila.alias || '').trim() || String(fila.nombre || '').trim() || `Agente ${fila.id}`);
                actionHtml += `<button onclick="mostrarQrParaAgente(${fila.id}, '${qrName.replace(/'/g, "\\'")}'); return false;" class="btn btn-small btn-secondary" title="${qrTitle}"><span title="${qrTitle}">${qrIndicator}</span> QR</button>`;
            }
            
            if (canAdmin()) {
                actionHtml += `<button onclick="eliminarDato(${fila.id}, '${(fila.uuid || '').replace(/'/g, "\\'")}')" class="btn btn-small" title="Eliminar registro">🗑️</button>`;
                if (canSuperAdmin()) {
                    actionHtml += `<button onclick="eliminarDatoDefinitivo(${fila.id})" class="btn btn-small btn-danger" title="Eliminar definitivamente (super admin)">🔥</button>`;
                    actionHtml += `<button onclick="rollbackDato(${fila.id})" class="btn btn-small" title="Restaurar desde papelera">↩️</button>`;
                }
            }
            actionHtml += `</td></tr>`;
            html += actionHtml;
        } else {
            const roReason = (tableName === 'datos_importados' || tableName === 'agentes_operativos')
                ? 'Solo lectura en esta base. Para editar/eliminar usa database_manager.agentes_operativos.'
                : 'Solo lectura';
            html += `<td><span class="hint">${roReason}</span></td></tr>`;
        }
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

async function editarDato(id, uuid = '') {
    if (!canAdmin()) {
        alert('Solo administradores pueden editar registros existentes.');
        return;
    }
    const nuevoValor = await showAppPrompt('Ingresa el nuevo nombre del agente:', { title: 'Editar nombre del agente', placeholder: 'Nombre completo' });
    if (!nuevoValor) return;
    const esActivo = await showAppConfirm('¿Debe quedar ACTIVO este agente?', { title: 'Estado del agente', acceptText: 'Activo', cancelText: 'Inactivo', tone: 'info' });

    try {
        let targetId = id;
        try {
            const dato = await apiClient.getDato(id);
            targetId = dato?.id || id;
        } catch (_) {
            if (uuid) {
                const datoUuid = await apiClient.getDatoByUUID(uuid);
                targetId = datoUuid?.id || id;
            }
        }

        const response = await fetch(`${API_URL}/datos/${targetId}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nombre: nuevoValor, es_activo: esActivo })
        });

        if (response.ok) {
            buscarDatos();
            return;
        }
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || 'No se pudo actualizar el dato');
    } catch (error) {
        console.error('Error:', error);
        alert('Error al editar: ' + error.message);
    }
}

async function eliminarDatoDefinitivo(id) {
    if (!canSuperAdmin()) {
        alert('Solo super administradores pueden eliminar definitivamente.');
        return;
    }
    if (!(await showAppConfirm('Esto eliminará el registro y sus dependencias de forma PERMANENTE. Esta acción no se puede deshacer.', { title: '⚠️ Eliminar definitivamente', tone: 'error', acceptText: 'Sí, continuar' }))) return;
    const confirmacion = await showAppPrompt('Para confirmar la eliminación, escribe la palabra CONFIRMAR:', { title: 'Confirmar eliminación', placeholder: 'CONFIRMAR', tone: 'error', acceptText: 'Confirmar eliminación' });
    if (confirmacion !== 'CONFIRMAR') {
        if (confirmacion !== null) showAppAlert('Palabra incorrecta. Operación cancelada.', { tone: 'warning', title: 'Cancelado' });
        return;
    }
    try {
        await apiClient.hardDeleteDato(id);
        alert('✅ Registro eliminado definitivamente. Un backup fue guardado en la papelera.');
        cargarTodosLosDatos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error eliminando definitivamente: ' + error.message);
    }
}

async function purgarDatosInactivos() {
    if (!canSuperAdmin()) {
        alert('Solo super administradores pueden purgar registros.');
        return;
    }
    if (!(await showAppConfirm('Se eliminarán DEFINITIVAMENTE todos los registros inactivos. Esta acción no se puede deshacer.', { title: '⚠️ Purgar registros inactivos', tone: 'error', acceptText: 'Sí, purgar' }))) return;
    const confirmacion = await showAppPrompt('Para confirmar la purga, escribe la palabra CONFIRMAR:', { title: 'Confirmar purgado', placeholder: 'CONFIRMAR', tone: 'error', acceptText: 'Confirmar purgado' });
    if (confirmacion !== 'CONFIRMAR') {
        if (confirmacion !== null) showAppAlert('Palabra incorrecta. Operación cancelada.', { tone: 'warning', title: 'Cancelado' });
        return;
    }
    try {
        const result = await apiClient.purgeInactiveDatos();
        alert(result.mensaje || 'Purgado completado.');
        cargarTodosLosDatos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error purgando inactivos: ' + error.message);
    }
}

async function rollbackDato(id) {
    if (!canSuperAdmin()) {
        alert('Solo super administradores pueden restaurar registros.');
        return;
    }
    if (!(await showAppConfirm(`¿Restaurar el registro ID ${id} desde la papelera?`, { title: 'Restaurar registro', tone: 'info' }))) return;
    try {
        const result = await apiClient.rollbackDato(id);
        alert(result.mensaje || `Registro ${id} restaurado correctamente.`);
        cargarTodosLosDatos();
    } catch (error) {
        console.error('Error en rollback:', error);
        alert('Error al restaurar: ' + error.message);
    }
}

async function generarQrIndividual(agenteId) {
    return generarQrIndividualEnContexto(agenteId, {
        resultContainerId: 'qrVerificationResult',
        qrContainerId: 'qrContainer',
        navigateSection: 'qr',
        setQrForm: true,
    });
}

async function generarQrIndividualEnContexto(agenteId, options = {}) {
    const {
        resultContainerId = 'qrVerificationResult',
        qrContainerId = 'qrContainer',
        navigateSection = null,
        setQrForm = false,
    } = options;
    try {
        const result = await apiClient.getQrAgente(agenteId);
        const data = result.data || {};
        // Intentar generar QR con librería disponible
        if (typeof QRCode === 'undefined' || !QRCode) {
            generarQrDesdeApiExterna(data.public_url, qrContainerId);
        } else {
            renderSimpleQR(data.public_url, qrContainerId);
        }
        if (navigateSection) {
            loadSection(navigateSection);
        }
        if (setQrForm) {
            const qrAgenteInput = document.getElementById('qrAgenteId');
            if (qrAgenteInput) qrAgenteInput.value = agenteId;
        }
        const box = document.getElementById(resultContainerId);
        if (box) {
            const qrName = String(data.alias || data.nombre || `Agente ${agenteId}`);
            box.innerHTML = `
                <div class="card" style="padding:12px;border:1px solid #d8d8d8;border-radius:8px;">
                    <strong>QR individual generado para:</strong> ${escapeHtml(qrName)}<br>
                    <strong>Asignación:</strong> ${data.tiene_asignacion ? 'Con número asignado' : 'Sin número asignado'}<br>
                    <strong>Modo QR:</strong> ${data.es_qr_seguro ? 'Seguro por línea activa' : 'Fallback por UUID (sin línea)'}<br>
                    <strong>URL pública:</strong> <a href="${data.public_url}" target="_blank">Abrir verificación</a><br>
                    <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
                        <button type="button" class="btn btn-secondary" onclick="descargarQrAgente(${agenteId})">Descargar PNG</button>
                        <button type="button" class="btn" onclick="copiarUrlQr('${String(data.public_url || '').replace(/'/g, "\\'")}')">Copiar URL</button>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error generando QR individual: ' + error.message);
    }
}

async function copiarUrlQr(url) {
    const value = String(url || '').trim();
    if (!value) {
        alert('No hay URL de QR para copiar.');
        return;
    }
    try {
        await copiarTextoPortapapeles(value);
        const panel = document.getElementById('qrVerificationResult');
        if (panel) {
            panel.innerHTML = '<p class="hint" style="color:green;">URL copiada al portapapeles.</p>';
        }
    } catch (_) {
        alert('No se pudo copiar automáticamente. URL: ' + value);
    }
}

function previsualizarQrAlta(agenteId) {
    return generarQrIndividualEnContexto(agenteId, {
        resultContainerId: 'altaAgenteQrResult',
        qrContainerId: 'altaAgenteQrContainer',
        navigateSection: null,
        setQrForm: false,
    });
}

function previsualizarQrGestion(agenteId) {
    return generarQrIndividualEnContexto(agenteId, {
        resultContainerId: 'gestionAgenteQrResult',
        qrContainerId: 'gestionAgenteQrContainer',
        navigateSection: null,
        setQrForm: false,
    });
}

async function sincronizarLineasPBXDesdeGestion() {
    await sincronizarLineasPBX({ preventDefault: () => {} });
    await cargarLineasGestion();
}

function getActiveQrScannerId() {
    return currentSection === 'qrScan' ? 'qrScanScanner' : 'qrScanner';
}

function getActiveQrCameraSelectId() {
    return currentSection === 'qrScan' ? 'qrScanCameraSelect' : 'qrCameraSelect';
}

function getActiveQrManualInputId() {
    return currentSection === 'qrScan' ? 'qrScanCodigoManual' : 'codigoEscaneadoManual';
}

function getActiveQrWeek() {
    const primaryId = currentSection === 'qrScan' ? 'qrScanSemana' : 'qrSemana';
    const primary = document.getElementById(primaryId)?.value || '';
    if (primary) return primary;
    return document.getElementById('qrSemana')?.value || '';
}

function formatIsoDateLocal(isoDate) {
    if (!isoDate) return '-';
    const dt = new Date(`${isoDate}T00:00:00`);
    if (Number.isNaN(dt.getTime())) return isoDate;
    return dt.toLocaleDateString();
}

function getDueDateSaturday(weekIso) {
    if (!weekIso) return null;
    const monday = new Date(`${weekIso}T00:00:00`);
    if (Number.isNaN(monday.getTime())) return null;
    monday.setDate(monday.getDate() + 5);
    return monday;
}

function showQuickAbonoModal({ montoSugerido = 0, saldo = 0, cuota = 0 } = {}) {
    return new Promise((resolve) => {
        const suggested = Number(montoSugerido || 0);
        const saldoActual = Number(saldo || 0);
        const cuotaActual = Number(cuota || 0);

        const backdrop = document.createElement('div');
        backdrop.className = 'app-alert-backdrop visible';
        backdrop.innerHTML = `
            <div class="app-alert-modal info qr-abono-modal" role="alertdialog" aria-modal="true">
                <div class="app-alert-header">
                    <div class="app-alert-badge">Abono</div>
                    <button type="button" class="app-alert-close" aria-label="Cerrar">×</button>
                </div>
                <h3 class="app-alert-title">Registrar Abono Parcial</h3>
                <div class="app-alert-message"><p>Captura el monto del abono para esta semana.</p></div>
                <div class="qr-abono-kpis">
                    <div class="qr-abono-kpi"><span>Sugerido</span><strong>$${suggested.toFixed(2)} MXN</strong></div>
                    <div class="qr-abono-kpi"><span>Saldo actual</span><strong>$${saldoActual.toFixed(2)} MXN</strong></div>
                    <div class="qr-abono-kpi"><span>Cuota semana</span><strong>$${cuotaActual.toFixed(2)} MXN</strong></div>
                </div>
                <div class="app-prompt-input-wrap">
                    <label for="qrAbonoMontoInput" class="hint" style="display:block;margin-bottom:6px;">Monto a registrar</label>
                    <input id="qrAbonoMontoInput" type="number" class="app-prompt-input qr-abono-input"
                           placeholder="0.00" step="0.01" min="0" value="${suggested.toFixed(2)}" inputmode="decimal" autocomplete="off" />
                </div>
                <div class="qr-abono-feedback" id="qrAbonoFeedback"></div>
                <div class="qr-abono-presets">
                    <button type="button" class="btn btn-secondary" data-preset="cuota">Usar cuota</button>
                    <button type="button" class="btn btn-secondary" data-preset="saldo">Usar saldo</button>
                    <button type="button" class="btn btn-secondary" data-preset="sugerido">Sugerido</button>
                </div>
                <div class="app-alert-actions app-confirm-actions qr-abono-actions">
                    <button type="button" class="btn btn-secondary" data-result="cancel">Cancelar</button>
                    <button type="button" class="btn" data-result="accept">Registrar</button>
                </div>
            </div>
        `;
        document.body.appendChild(backdrop);

        const input = backdrop.querySelector('#qrAbonoMontoInput');
        const feedback = backdrop.querySelector('#qrAbonoFeedback');
        const acceptBtn = backdrop.querySelector('[data-result="accept"]');
        const EPS = 0.009;

        const validateAmount = () => {
            const raw = String(input?.value ?? '').trim();
            const amount = Number(raw);
            let error = '';

            if (!Number.isFinite(amount)) {
                error = 'Ingresa un monto válido.';
            } else if (amount <= 0) {
                error = 'El abono debe ser mayor a 0.';
            } else if (saldoActual > EPS && amount > (saldoActual + EPS)) {
                error = `El abono excede el saldo acumulado ($${saldoActual.toFixed(2)} MXN).`;
            }

            if (feedback) {
                if (error) {
                    feedback.textContent = error;
                    feedback.className = 'qr-abono-feedback error';
                } else {
                    feedback.textContent = 'Monto válido para registrar.';
                    feedback.className = 'qr-abono-feedback success';
                }
            }
            if (acceptBtn) {
                acceptBtn.disabled = Boolean(error);
            }

            return { amount, error };
        };

        const closeAndResolve = (value) => {
            document.removeEventListener('keydown', keyHandler);
            backdrop.remove();
            resolve(value);
        };

        const keyHandler = (e) => {
            if (e.key === 'Escape') closeAndResolve(null);
            if (e.key === 'Enter') {
                const result = validateAmount();
                if (!result.error) closeAndResolve(String(result.amount));
            }
        };

        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) closeAndResolve(null);
        });
        backdrop.querySelector('[data-result="cancel"]')?.addEventListener('click', () => closeAndResolve(null));
        backdrop.querySelector('[data-result="accept"]')?.addEventListener('click', () => {
            const result = validateAmount();
            if (!result.error) closeAndResolve(String(result.amount));
        });
        backdrop.querySelector('.app-alert-close')?.addEventListener('click', () => closeAndResolve(null));
        backdrop.querySelector('[data-preset="cuota"]')?.addEventListener('click', () => { if (input) input.value = cuotaActual.toFixed(2); validateAmount(); });
        backdrop.querySelector('[data-preset="saldo"]')?.addEventListener('click', () => { if (input) input.value = saldoActual.toFixed(2); validateAmount(); });
        backdrop.querySelector('[data-preset="sugerido"]')?.addEventListener('click', () => { if (input) input.value = suggested.toFixed(2); validateAmount(); });
        input?.addEventListener('input', validateAmount);

        document.addEventListener('keydown', keyHandler);
        input?.focus();
        input?.select();
        validateAmount();
    });
}

function renderEscaneoResumen(data) {
    const badge = document.getElementById('qrScanEstadoBadge');
    const content = document.getElementById('qrScanSummaryContent');
    if (!badge || !content) return;

    const a = data?.agente || {};
    const v = data?.verificacion || {};
    const deuda = Number(v.saldo_acumulado ?? 0);
    const tarifaLinea = Number(v.tarifa_linea_semanal ?? v.cuota_semanal ?? 0);
    const lineasActivas = Number(v.lineas_activas ?? (Array.isArray(a.lineas) ? a.lineas.length : 0));
    const cuota = Number(v.cuota_semanal ?? (tarifaLinea * lineasActivas));
    const deudaBase = Number(v.deuda_base_total ?? 0);
    const ajusteManual = Number(v.ajuste_manual_deuda ?? 0);
    const debe = deuda > 0.009 || !v.pagado;
    const debeTxt = debe ? `Debe $${deuda.toFixed(0)}` : 'Al Corriente';
    const dueDate = getDueDateSaturday(v.semana_inicio);
    const dueDateTxt = dueDate
        ? `${dueDate.toLocaleDateString()} (sábado)`
        : 'No disponible';
    const lineas = Array.isArray(a.lineas) ? a.lineas : [];
    const lineasTxt = lineas.length ? lineas.map(x => x.numero).join(', ') : 'Sin líneas';

    badge.textContent = debe ? 'Pendiente de Pago' : 'Al Corriente';
    badge.className = `payment-pill ${debe ? 'unpaid' : 'paid'}`;

    content.innerHTML = `
        <div class="qr-scan-kpis">
            <div><strong>Agente:</strong> ${escapeHtml(getAgentDisplayName(a, '-'))} (ID ${a.id || '-'})</div>
            <div><strong>Estado:</strong> ${escapeHtml(debeTxt)}</div>
            <div><strong>Límite sugerido:</strong> ${escapeHtml(dueDateTxt)}</div>
            <div><strong>Semana:</strong> ${escapeHtml(formatIsoDateLocal(v.semana_inicio || ''))}</div>
            <div><strong>Líneas:</strong> ${escapeHtml(lineasTxt)}</div>
            <div><strong>Teléfono:</strong> ${escapeHtml(a.telefono || '-')}</div>
        </div>
        <div class="qr-scan-kpis" style="margin-top:8px;">
            <div><strong>Tarifa por línea:</strong> $${tarifaLinea.toFixed(2)} MXN</div>
            <div><strong>Líneas activas:</strong> ${lineasActivas}</div>
            <div><strong>Cargo semanal actual:</strong> $${cuota.toFixed(2)} MXN</div>
            <div><strong>Monto semana:</strong> $${Number(v.monto ?? 0).toFixed(2)} MXN</div>
            <div><strong>Total abonado:</strong> $${Number(v.total_abonado ?? 0).toFixed(2)} MXN</div>
            <div><strong>Deuda base:</strong> $${deudaBase.toFixed(2)} MXN</div>
            <div><strong>Ajuste manual:</strong> $${ajusteManual.toFixed(2)} MXN</div>
            <div><strong>Saldo acumulado:</strong> $${deuda.toFixed(2)} MXN</div>
            <div><strong>Semanas pendientes:</strong> ${Number(v.semanas_pendientes ?? 0)}</div>
            <div><strong>Último pago:</strong> ${v.fecha_pago ? new Date(v.fecha_pago).toLocaleString() : 'Sin pago'}</div>
        </div>
    `;
}

async function registrarPagoDesdeEscaneo(mode = 'abono') {
    if (!currentVerificationData) {
        alert('Primero escanea y verifica un agente.');
        return;
    }

    const a = currentVerificationData.agente || {};
    const v = currentVerificationData.verificacion || {};
    const saldo = Number(v.saldo_acumulado ?? 0);
    const cuota = Number(v.cuota_semanal ?? 0);
    const semana = v.semana_inicio || getActiveQrWeek() || mondayISO();

    if (mode === 'liquidar' && saldo <= 0.009) {
        alert('El agente no tiene adeudo acumulado para liquidar.');
        return;
    }

    const montoSugerido = mode === 'liquidar'
        ? Math.max(saldo, 0)
        : (saldo > 0.009 ? Math.min(saldo, cuota || saldo) : (cuota || 0));

    let monto = montoSugerido;
    if (mode === 'abono') {
        const montoRaw = await showQuickAbonoModal({
            montoSugerido,
            saldo,
            cuota,
        });
        if (montoRaw === null) return;
        monto = Number(montoRaw);
    }

    if (monto <= 0) {
        alert('No hay monto válido para registrar pago.');
        return;
    }

    const payload = {
        agente_id: Number(a.id || 0),
        telefono: a.telefono || null,
        numero_voip: a.numero_voip || null,
        semana_inicio: semana,
        monto,
        pagado: mode === 'liquidar',
        liquidar_total: mode === 'liquidar',
        observaciones: mode === 'liquidar'
            ? 'Pago procesado desde escaneo QR (liquidación total).'
            : 'Pago procesado desde escaneo QR (abono semanal).',
    };

    if (!payload.agente_id) {
        alert('No se pudo identificar al agente escaneado.');
        return;
    }

    try {
        await apiClient.registrarPagoSemanal(payload);
        alert(mode === 'liquidar'
            ? 'Adeudo total liquidado correctamente.'
            : 'Abono semanal registrado correctamente.');

        document.getElementById('pagoAgenteId').value = payload.agente_id;
        document.getElementById('pagoTelefono').value = payload.telefono || '';
        document.getElementById('pagoVoip').value = payload.numero_voip || '';
        document.getElementById('pagoSemana').value = payload.semana_inicio;
        document.getElementById('pagoMonto').value = Number(payload.monto).toFixed(2);
        const liquidarEl = document.getElementById('pagoLiquidarTotal');
        if (liquidarEl) liquidarEl.checked = !!payload.liquidar_total;

        const refreshed = await apiClient.verificarAgenteQR(payload.agente_id, payload.telefono || '', payload.numero_voip || '', payload.semana_inicio);
        currentVerificationData = { agente: refreshed.agente || {}, verificacion: refreshed.verificacion || {} };
        renderEscaneoResumen(currentVerificationData);
        await consultarResumenPagoActual(false);
        cargarReporteSemanal();
        cargarRecibosPersistidos();
        if (currentSection !== 'qr') {
            loadSection('qr');
        }
    } catch (error) {
        console.error('Error procesando pago rápido desde escaneo:', error);
        alert('No se pudo procesar el pago: ' + error.message);
    }
}

function abrirGestionPagoCompletaDesdeEscaneo() {
    if (currentVerificationData) {
        const a = currentVerificationData.agente || {};
        const v = currentVerificationData.verificacion || {};
        document.getElementById('pagoAgenteId').value = a.id || '';
        document.getElementById('pagoTelefono').value = a.telefono || '';
        document.getElementById('pagoVoip').value = a.numero_voip || '';
        document.getElementById('pagoSemana').value = v.semana_inicio || mondayISO();
        document.getElementById('pagoMonto').value = Number(v.cuota_semanal || 0).toFixed(2);
    }
    loadSection('qr');
}

async function leerCodigoManual() {
    const input = document.getElementById(getActiveQrManualInputId());
    const value = (input?.value || '').trim();
    if (!value) {
        alert('Ingresa o pega un código para leer.');
        return;
    }
    await manejarQRLeido(value);
}

async function descargarQrAgente(agenteId) {
    try {
        const blob = await apiClient.downloadQrAgente(agenteId);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `agente_${agenteId}.png`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Error:', error);
        alert('Error descargando QR: ' + error.message);
    }
}

// ========= QR EXPORT BATCH — FUNCTIONS ===========

// In-memory agent list for the export tab
let _qrExportAgentes = [];
const QR_LABEL_EDITOR_STORAGE_KEY = 'qrLabelEditorSettings';

const QR_LABEL_PRESETS = {
    sheet: {
        estandar: {
            label: 'Estandar (36 QR por hoja carta)',
            settings: { rows: 9, columns: 4, qr_size: 68, border_gap: 0.4, pad_bottom: 2.0, draw_border: true },
            hint: 'Carta densa con buena legibilidad para operacion diaria.',
        },
        compacto: {
            label: 'Compacto (40 QR por hoja carta)',
            settings: { rows: 10, columns: 4, qr_size: 62, border_gap: 0.3, pad_bottom: 1.2, draw_border: true },
            hint: 'Maxima densidad en carta para lotes grandes.',
        },
    },
    labels: {
        estandar: {
            label: 'Estandar (44 etiquetas por carta)',
            settings: { rows: 11, qr_size: 50, border_gap: 0.8, pad_bottom: 1.5, draw_border: true },
            hint: 'Formato base de etiquetas compactas.',
        },
        compacto: {
            label: 'Compacto (48 etiquetas por carta)',
            settings: { rows: 12, qr_size: 46, border_gap: 0.6, pad_bottom: 1.2, draw_border: true },
            hint: 'Maximiza etiquetas por hoja para lotes grandes.',
        },
    },
    oficio: {
        estandar: {
            label: 'Estandar (40 QR por hoja oficio)',
            settings: { rows: 10, columns: 4, qr_size: 72, border_gap: 0.4, pad_bottom: 2.0, draw_border: true },
            hint: 'Oficio optimizado para minimizar espacio en blanco lateral.',
        },
        compacto: {
            label: 'Compacto (44 QR por hoja oficio)',
            settings: { rows: 11, columns: 4, qr_size: 66, border_gap: 0.3, pad_bottom: 1.2, draw_border: true },
            hint: 'Densidad alta en oficio conservando lectura de QR en campo.',
        },
    },
};

function qrLabelEditorGetLayoutPresets(layout) {
    return QR_LABEL_PRESETS[layout] || QR_LABEL_PRESETS.oficio;
}

function qrLabelEditorGetDefaultPresetKey(layout) {
    const presets = qrLabelEditorGetLayoutPresets(layout);
    return Object.keys(presets)[0] || 'estandar';
}

function qrLabelEditorGetPresetSettings(layout, presetKey) {
    const presets = qrLabelEditorGetLayoutPresets(layout);
    const resolvedKey = presets[presetKey] ? presetKey : qrLabelEditorGetDefaultPresetKey(layout);
    const preset = presets[resolvedKey];
    return { key: resolvedKey, ...(preset || { settings: {}, hint: '' }) };
}

function qrLabelEditorGetDefaults(layout) {
    return qrLabelEditorGetPresetSettings(layout, qrLabelEditorGetDefaultPresetKey(layout));
}

function qrLabelEditorCurrentLayout() {
    return document.getElementById('qrExportLayout')?.value || 'sheet';
}

function qrLabelEditorRenderPresetOptions(layout) {
    const sel = document.getElementById('qrLabelPreset');
    if (!sel) return;
    const presets = qrLabelEditorGetLayoutPresets(layout);
    const options = Object.entries(presets)
        .map(([key, cfg]) => `<option value="${key}">${cfg.label}</option>`)
        .join('');
    sel.innerHTML = options;
}

function qrLabelEditorUpdateHint(layout, presetKey) {
    const hintEl = document.getElementById('qrLabelPresetHint');
    if (!hintEl) return;
    const preset = qrLabelEditorGetPresetSettings(layout, presetKey);
    hintEl.textContent = preset.hint || '';
}

function qrLabelEditorRead() {
    const layout = qrLabelEditorCurrentLayout();
    const selectedPreset = document.getElementById('qrLabelPreset')?.value;
    return qrLabelEditorGetPresetSettings(layout, selectedPreset).settings || {};
}

function qrLabelEditorApply(profileOrLegacy) {
    const layout = qrLabelEditorCurrentLayout();
    const selectEl = document.getElementById('qrLabelPreset');
    if (!selectEl) return;

    const presets = qrLabelEditorGetLayoutPresets(layout);
    const defaultPreset = qrLabelEditorGetDefaultPresetKey(layout);
    let presetKey = defaultPreset;

    if (typeof profileOrLegacy === 'string' && presets[profileOrLegacy]) {
        presetKey = profileOrLegacy;
    } else if (profileOrLegacy && typeof profileOrLegacy === 'object') {
        if (typeof profileOrLegacy.profile === 'string' && presets[profileOrLegacy.profile]) {
            presetKey = profileOrLegacy.profile;
        }
    }

    selectEl.value = presetKey;
    qrLabelEditorUpdateHint(layout, presetKey);
}

function qrLabelEditorLoad() {
    const layout = qrLabelEditorCurrentLayout();
    qrLabelEditorRenderPresetOptions(layout);
    let parsed = {};
    try {
        parsed = JSON.parse(localStorage.getItem(QR_LABEL_EDITOR_STORAGE_KEY) || '{}') || {};
    } catch (_) {
        parsed = {};
    }
    const defaults = qrLabelEditorGetDefaults(layout);
    const stored = parsed[layout];
    const fallbackProfile = defaults.key || qrLabelEditorGetDefaultPresetKey(layout);
    const profileToApply = (stored && typeof stored.profile === 'string') ? stored.profile : fallbackProfile;
    qrLabelEditorApply(profileToApply);
}

function qrLabelEditorGuardar() {
    const layout = qrLabelEditorCurrentLayout();
    const selectedProfile = document.getElementById('qrLabelPreset')?.value || qrLabelEditorGetDefaultPresetKey(layout);
    let parsed = {};
    try {
        parsed = JSON.parse(localStorage.getItem(QR_LABEL_EDITOR_STORAGE_KEY) || '{}') || {};
    } catch (_) {
        parsed = {};
    }
    parsed[layout] = { profile: selectedProfile };
    localStorage.setItem(QR_LABEL_EDITOR_STORAGE_KEY, JSON.stringify(parsed));
    qrLabelEditorUpdateHint(layout, selectedProfile);
    showAppAlert('Perfil de densidad guardado.', { tone: 'success', title: 'Editor QR' });
}

function qrLabelEditorRestaurar() {
    const layout = qrLabelEditorCurrentLayout();
    const defaults = qrLabelEditorGetDefaults(layout);
    qrLabelEditorApply(defaults.key || qrLabelEditorGetDefaultPresetKey(layout));
    let parsed = {};
    try {
        parsed = JSON.parse(localStorage.getItem(QR_LABEL_EDITOR_STORAGE_KEY) || '{}') || {};
    } catch (_) {
        parsed = {};
    }
    delete parsed[layout];
    localStorage.setItem(QR_LABEL_EDITOR_STORAGE_KEY, JSON.stringify(parsed));
    showAppAlert('Ajustes restablecidos para este layout.', { tone: 'info', title: 'Editor QR' });
}

async function qrExportCargarAgentes() {
    const listEl = document.getElementById('qrExportListaAgentes');
    const resultEl = document.getElementById('qrExportResult');
    if (!listEl) return;
    listEl.innerHTML = '<p class="hint" style="padding:12px;">Cargando agentes...</p>';
    try {
        // Use estado=todos to get all agents with QR (printed and unprinted)
        const data = await apiClient.request('GET', '/qr/agentes/sin-imprimir?estado=todos&solo_activos=false');
        const raw = data.agentes || [];
        _qrExportAgentes = raw.map(a => ({
            id: a.id,
            nombre: a.nombre || '',
            alias: a.alias || '',
            telefono: a.telefono || '',
            estatus: a.estatus_codigo || 'ACTIVO',
            qr_impreso: !!a.qr_impreso,
        }));

        const total = _qrExportAgentes.length;
        const impresos = _qrExportAgentes.filter(a => a.qr_impreso).length;
        const pendientes = total - impresos;
        if (resultEl) {
            resultEl.innerHTML = `<p class="hint">Total: <strong>${total}</strong> agente(s) · Pendientes: <strong>${pendientes}</strong> · Impresos: <strong>${impresos}</strong></p>`;
        }

        qrExportRenderizarLista();
        await qrExportActualizarBannerSinImprimir();
    } catch (err) {
        if (listEl) listEl.innerHTML = `<p style="color:red;padding:12px;">Error cargando agentes: ${escapeHtml(err.message)}</p>`;
    }
}

function qrExportRenderizarLista() {
    const listEl = document.getElementById('qrExportListaAgentes');
    if (!listEl) return;

    const busqueda = (document.getElementById('qrExportBusqueda')?.value || '').trim().toLowerCase();
    const filtroEstado = document.getElementById('qrExportFiltroEstado')?.value || 'todos';

    let agentes = _qrExportAgentes;
    if (busqueda) {
        agentes = agentes.filter(a =>
            String(a.id).includes(busqueda) ||
            (a.nombre || '').toLowerCase().includes(busqueda) ||
            (a.alias || '').toLowerCase().includes(busqueda)
        );
    }
    if (filtroEstado === 'sin_imprimir') agentes = agentes.filter(a => !a.qr_impreso);
    if (filtroEstado === 'impresos') agentes = agentes.filter(a => a.qr_impreso);

    if (!agentes.length) {
        listEl.innerHTML = '<p class="hint" style="padding:12px;">No se encontraron agentes.</p>';
        _qrExportActualizarContador();
        return;
    }

    const rows = agentes.map(a => {
        const estadoBadge = a.qr_impreso
            ? '<span style="background:#d4edda;color:#155724;border-radius:4px;padding:1px 7px;font-size:11px;">✅ Impreso</span>'
            : '<span style="background:#fff3cd;color:#856404;border-radius:4px;padding:1px 7px;font-size:11px;">⚠ Pendiente</span>';
        const displayName = a.alias ? `${a.alias} (${a.nombre})` : a.nombre;
        return `<tr>
            <td style="width:32px;text-align:center;padding:6px 4px;">
                <input type="checkbox" class="qr-export-cb" data-id="${a.id}" onchange="_qrExportActualizarContador()">
            </td>
            <td style="padding:6px 8px;font-weight:600;color:#2c3e50;">${a.id}</td>
            <td style="padding:6px 8px;">${escapeHtml(displayName)}</td>
            <td style="padding:6px 8px;color:#555;">${escapeHtml(a.telefono)}</td>
            <td style="padding:6px 8px;">${estadoBadge}</td>
        </tr>`;
    }).join('');

    listEl.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
            <tr style="background:#f0f4f8;border-bottom:2px solid #d0dae8;">
                <th style="width:32px;"></th>
                <th style="text-align:left;padding:6px 8px;">ID</th>
                <th style="text-align:left;padding:6px 8px;">Nombre / Alias</th>
                <th style="text-align:left;padding:6px 8px;">Teléfono</th>
                <th style="text-align:left;padding:6px 8px;">Estado impresión</th>
            </tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>`;
    _qrExportActualizarContador();
}

function qrExportFiltrarLista() {
    qrExportRenderizarLista();
}

function qrExportFiltrarSinImprimir() {
    const sel = document.getElementById('qrExportFiltroEstado');
    if (sel) sel.value = 'sin_imprimir';
    qrExportRenderizarLista();
}

function qrExportToggleSeleccionTodos(checked) {
    document.querySelectorAll('.qr-export-cb').forEach(cb => { cb.checked = checked; });
    _qrExportActualizarContador();
}

function qrExportSeleccionarSinImprimir() {
    document.querySelectorAll('.qr-export-cb').forEach(cb => {
        const id = parseInt(cb.dataset.id, 10);
        const agente = _qrExportAgentes.find(a => a.id === id);
        cb.checked = agente ? !agente.qr_impreso : false;
    });
    _qrExportActualizarContador();
}

function _qrExportSeleccionados() {
    return Array.from(document.querySelectorAll('.qr-export-cb:checked')).map(cb => parseInt(cb.dataset.id, 10));
}

function _qrExportActualizarContador() {
    const count = _qrExportSeleccionados().length;
    const el = document.getElementById('qrExportContadorSeleccionados');
    if (el) el.textContent = count > 0 ? `${count} seleccionado(s)` : '';
    const selTodos = document.getElementById('qrExportSelTodos');
    if (selTodos) {
        const total = document.querySelectorAll('.qr-export-cb').length;
        selTodos.indeterminate = count > 0 && count < total;
        selTodos.checked = total > 0 && count === total;
    }
}

async function exportarQRLoteSeleccionados() {
    const ids = _qrExportSeleccionados();
    const result = document.getElementById('qrExportResult');
    const layout = document.getElementById('qrExportLayout')?.value || 'sheet';
    const marcarImpreso = document.getElementById('qrExportMarcarImpreso')?.checked !== false;
    const layoutOverrides = qrLabelEditorRead();

    if (!ids.length) {
        showAppAlert('Selecciona al menos un agente para exportar.', { tone: 'warning', title: 'Sin selección' });
        return;
    }
    if (result) result.innerHTML = '<p class="hint">Generando PDF...</p>';
    try {
        const idsCsv = ids.join(',');
        const blob = await apiClient.exportQrAgentesPdf({ idsCsv, layout, soloActivos: false, marcarImpreso, layoutOverrides });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `agentes_qr_${layout}.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        if (result) result.innerHTML = `<p style="color:green;">✅ PDF con ${ids.length} QR generado correctamente.${marcarImpreso ? ' Marcados como impresos.' : ''}</p>`;
        // Refresh list to reflect updated print status
        if (marcarImpreso) {
            ids.forEach(id => {
                const a = _qrExportAgentes.find(x => x.id === id);
                if (a) a.qr_impreso = true;
            });
            qrExportRenderizarLista();
            await qrExportActualizarBannerSinImprimir();
        }
    } catch (error) {
        console.error('Error:', error);
        if (result) result.innerHTML = `<p style="color:red;">Error exportando PDF: ${escapeHtml(error.message)}</p>`;
    }
}

// Legacy function — kept so any old calls still work
async function exportarQRLote() {
    return exportarQRLoteSeleccionados();
}

async function qrExportMarcarSeleccionados(impreso) {
    const ids = _qrExportSeleccionados();
    if (!ids.length) {
        showAppAlert('Selecciona al menos un agente.', { tone: 'warning', title: 'Sin selección' });
        return;
    }
    try {
        const data = await apiClient.marcarAgentesImpreso(ids, impreso);
        ids.forEach(id => {
            const a = _qrExportAgentes.find(x => x.id === id);
            if (a) a.qr_impreso = impreso;
        });
        qrExportRenderizarLista();
        await qrExportActualizarBannerSinImprimir();
        const result = document.getElementById('qrExportResult');
        if (result) result.innerHTML = `<p style="color:green;">${data.actualizados} agente(s) ${impreso ? 'marcados como impresos' : 'desmarcados'}.</p>`;
    } catch (err) {
        showAppAlert('Error actualizando estado: ' + err.message, { tone: 'error' });
    }
}

async function qrExportActualizarBannerSinImprimir() {
    const banner = document.getElementById('qrImpresoAlertaBanner');
    const texto = document.getElementById('qrImpresoAlertaTexto');
    if (!banner || !texto) return;
    const count = _qrExportAgentes.filter(a => !a.qr_impreso).length;
    if (count > 0) {
        texto.textContent = `Hay ${count} agente(s) con QR generado que aún no han sido impresos.`;
        banner.style.display = 'flex';
    } else {
        banner.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const layoutSel = document.getElementById('qrExportLayout');
    const presetSel = document.getElementById('qrLabelPreset');
    if (layoutSel) {
        layoutSel.addEventListener('change', () => qrLabelEditorLoad());
    }
    if (presetSel) {
        presetSel.addEventListener('change', () => {
            qrLabelEditorUpdateHint(qrLabelEditorCurrentLayout(), presetSel.value);
        });
    }
    if (layoutSel || presetSel) {
        qrLabelEditorLoad();
    }
});

async function verificarQRSinImprimir() {
    // Called on qr section load — show a nav-level badge if there are unprinted QRs
    if (!authToken) return;
    try {
        const data = await apiClient.getAgentesConQRSinImprimir(true);
        const count = data.total || 0;
        const badge = document.getElementById('qrSinImprimirBadge');
        if (badge) {
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (_) {}
}

async function loadServerVersionInfo() {
    const el = document.getElementById('serverVersionInfo');
    if (!el || !authToken) return;
    el.textContent = 'Consultando versión del servidor...';
    try {
        const payload = await apiClient.getServerVersion();
        const current = payload.current || {};
        el.textContent = `Versión ${current.version_string || current.version || '-'} · revisión ${current.revision || '-'} · ${current.codename || 'Producción'}`;
    } catch (_error) {
        el.textContent = 'Versión del servidor no visible fuera del servidor.';
    }
}

function _renderCameraSelector(cameras, preferredDeviceId = '') {
    qrAvailableCameras = Array.isArray(cameras) ? cameras : [];

    const isRearLabel = (label) => /back|rear|trasera|environment|world/i.test(String(label || ''));
    const isFrontLabel = (label) => /front|frontal|selfie|user/i.test(String(label || ''));

    // Ordenar para priorizar trasera: rear -> sin etiqueta (en mobile suelen venir vacías) -> frontal.
    const ordered = [...qrAvailableCameras].sort((a, b) => {
        const la = String(a?.label || '');
        const lb = String(b?.label || '');

        const rank = (label) => {
            if (isRearLabel(label)) return 0;
            if (isFrontLabel(label)) return 2;
            return IS_MOBILE_DEVICE() ? 1 : 0;
        };

        return rank(la) - rank(lb);
    });

    const rear = ordered.find(c => isRearLabel(c.label));
    const nonFront = ordered.find(c => !isFrontLabel(c.label));

    ['qrCameraSelect', 'qrScanCameraSelect'].forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;

        if (!ordered.length) {
            select.innerHTML = '<option value="">-- Sin cámaras detectadas --</option>';
            return;
        }

        select.innerHTML = ordered
            .map(c => `<option value="${c.deviceId}">${(c.label || c.deviceId).replace(/</g, '&lt;')}</option>`)
            .join('');

        const preferred = preferredDeviceId
            || qrCurrentCameraId
            || rear?.deviceId
            || nonFront?.deviceId
            || ordered[0].deviceId;
        select.value = ordered.some(c => c.deviceId === preferred) ? preferred : ordered[0].deviceId;
        qrCurrentCameraId = select.value;
    });

    if (!ordered.length) {
        qrCurrentCameraId = '';
    }
}

async function cargarCamarasDisponibles(silent = false) {
    if (typeof Html5Qrcode === 'undefined') {
        if (!silent) {
            showAppAlert('No se pudo iniciar el módulo de cámara porque la librería de escaneo no está cargada.', {
                title: 'Escáner no disponible',
                tone: 'error',
                detail: 'Recarga la página. Si el problema persiste, verifica que los recursos frontend del escáner estén accesibles.',
            });
        }
        return [];
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (!silent) {
            showAppAlert('El navegador no permite acceso a cámaras en este contexto.', {
                title: 'Cámara bloqueada por el navegador',
                tone: 'warning',
                detail: 'Usa HTTPS o localhost y revisa permisos del sitio en el navegador.',
            });
        }
        _renderCameraSelector([]);
        return [];
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        stream.getTracks().forEach(t => t.stop());
    } catch (_) {
        // Si no concede permisos, igual intentamos enumerar por si hay labels previos
    }

    let cameras = [];
    try {
        cameras = await Html5Qrcode.getCameras();
    } catch (_) {
        cameras = [];
    }
    _renderCameraSelector(cameras);
    if (!cameras.length && !silent) {
        showAppAlert('No se detectaron cámaras disponibles.', {
            title: 'Sin cámaras detectadas',
            tone: 'warning',
            detail: 'Conecta una cámara, cierra otras aplicaciones que la estén usando y vuelve a pulsar Actualizar Cámaras.',
        });
    }
    return cameras;
}

async function iniciarEscanerQRCamaraSeleccionada() {
    const select = document.getElementById(getActiveQrCameraSelectId());
    const deviceId = (select?.value || '').trim();
    if (!deviceId) {
        showAppAlert('Selecciona una cámara antes de iniciar el escáner.', {
            title: 'Falta seleccionar cámara',
            tone: 'warning',
            detail: 'Usa Actualizar Cámaras si el listado está vacío o desactualizado.',
        });
        return;
    }
    await detenerEscanerQR();
    const container = document.getElementById(getActiveQrScannerId());
    if (container) container.innerHTML = '';
    qrCurrentCameraId = deviceId;
    await iniciarEscanerQRManual();
}

async function iniciarEscanerQR() {
    if (typeof Html5Qrcode === 'undefined') {
        alert('Librería de escaneo no disponible.');
        return;
    }
    if (qrScannerInstance) {
        return;
    }

    const scannerContainerId = getActiveQrScannerId();
    const qrEl = document.getElementById(scannerContainerId);

    function mostrarErrorCamara(msg) {
        if (qrEl) {
            qrEl.innerHTML = `<div style="color:#c0392b;background:#fdecea;border:1px solid #f5c6cb;border-radius:6px;padding:14px;font-size:14px;line-height:1.6;">${msg}</div>`;
        } else {
            alert(msg.replace(/<[^>]+>/g, ''));
        }
    }

    // El acceso a la cámara requiere HTTPS o localhost.
    // En HTTP sobre un dominio personalizado el navegador bloquea navigator.mediaDevices.
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const origin = location.origin;
        mostrarErrorCamara(
            `<strong>⚠️ Cámara bloqueada por el navegador (HTTP inseguro)</strong><br><br>` +
            `El navegador solo permite acceder a la cámara desde conexiones <b>HTTPS</b> o <b>localhost</b>.<br><br>` +
            `<b>Opciones:</b><ul style="margin:6px 0 0 18px;">` +
            `<li>Configura HTTPS en el servidor (recomendado)</li>` +
            `<li>En Chrome/Edge: visita <code>chrome://flags/#unsafely-treat-insecure-origin-as-secure</code>, ` +
            `agrega <code>${origin}</code> y reinicia el navegador</li>` +
            `<li>Accede vía <code>localhost</code> si el servidor está en esta máquina</li></ul>`
        );
        return;
    }

    const formats = (typeof Html5QrcodeSupportedFormats !== 'undefined')
        ? [
            Html5QrcodeSupportedFormats.QR_CODE,
            Html5QrcodeSupportedFormats.CODE_128,
            Html5QrcodeSupportedFormats.CODE_39,
            Html5QrcodeSupportedFormats.EAN_13,
            Html5QrcodeSupportedFormats.EAN_8,
            Html5QrcodeSupportedFormats.UPC_A,
            Html5QrcodeSupportedFormats.UPC_E,
        ]
        : undefined;

    const scanConfig = {
        fps: 15,
        qrbox: (viewfinderWidth, viewfinderHeight) => {
            const minDim = Math.min(viewfinderWidth, viewfinderHeight);
            const boxSize = Math.max(200, Math.floor(minDim * 0.85));
            return { width: boxSize, height: boxSize };
        },
        formatsToSupport: formats,
        aspectRatio: 1.0,
    };

    const onScan = async (decodedText) => { await manejarQRLeido(decodedText); };
    const onError = () => {};

    function limpiarContenedor() {
        if (qrEl) qrEl.innerHTML = '';
    }

    async function tryStart(cameraIdOrConstraint) {
        limpiarContenedor();
        const scanner = new Html5Qrcode(scannerContainerId);
        await scanner.start(cameraIdOrConstraint, scanConfig, onScan, onError);
        return scanner;
    }

    // Paso 1: pedir permiso explícitamente antes de enumerar.
    // Esto muestra el diálogo de permiso del navegador.
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        stream.getTracks().forEach(t => t.stop()); // liberar inmediatamente
    } catch (err) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            mostrarErrorCamara(
                `<strong>🚫 Permiso de cámara denegado</strong><br><br>` +
                `Habilita el acceso a la cámara en la configuración del navegador ` +
                `(ícono 🔒 junto a la barra de dirección) y recarga la página.`
            );
            return;
        }
        if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            mostrarErrorCamara(`<strong>❌ No se encontró ninguna cámara</strong><br>Verifica que haya una cámara conectada y habilitada.`);
            return;
        }
        // Para otros errores seguimos intentando con Html5Qrcode
    }

    // Paso 2: enumerar cámaras (ahora que hay permiso, recibiremos labels reales)
    let cameras = [];
    try {
        cameras = await Html5Qrcode.getCameras();
    } catch (_) {}

    _renderCameraSelector(cameras);

    const isRearLabel = (label) => /back|rear|trasera|environment|world/i.test(String(label || ''));
    const isFrontLabel = (label) => /front|frontal|selfie|user/i.test(String(label || ''));
    const orderedCameras = [...cameras].sort((a, b) => {
        const rank = (label) => {
            if (isRearLabel(label)) return 0;
            if (isFrontLabel(label)) return 2;
            return IS_MOBILE_DEVICE() ? 1 : 0;
        };
        return rank(a?.label) - rank(b?.label);
    });

    const rearCamera = orderedCameras.find(c => isRearLabel(c.label));
    const nonFrontCamera = orderedCameras.find(c => !isFrontLabel(c.label));
    const candidateIds = [
        rearCamera?.deviceId,
        nonFrontCamera?.deviceId,
        ...orderedCameras.map(c => c.deviceId),
    ].filter(Boolean).filter((v, i, arr) => arr.indexOf(v) === i);

    // En móvil, probar primero `environment`; muchos equipos no etiquetan cámaras correctamente.
    const constraintPrimary = IS_MOBILE_DEVICE()
        ? [
            { facingMode: { exact: 'environment' } },
            { facingMode: { ideal: 'environment' } },
        ]
        : [];

    // Fallbacks universales.
    const constraintFallbacks = [
        { facingMode: { ideal: 'environment' } },
        { facingMode: 'user' },
        true,
    ];

    const attempts = [
        ...constraintPrimary.map(c => () => tryStart(c)),
        ...candidateIds.map(id => () => tryStart({ deviceId: { exact: id } })),
        ...constraintFallbacks.map(c => () => tryStart(c)),
    ];

    for (const attempt of attempts) {
        try {
            qrScannerInstance = await attempt();
            return; // éxito
        } catch (_) {
            limpiarContenedor();
        }
    }

    // Todos los intentos fallaron — mostrar selector manual si hay cámaras conocidas
    if (cameras.length > 0) {
        limpiarContenedor();
        const opts = cameras.map(c => `<option value="${c.deviceId}">${c.label || c.deviceId}</option>`).join('');
        if (qrEl) {
            qrEl.innerHTML =
                `<p style="color:#e74c3c;margin:0 0 8px;">No se pudo iniciar la cámara automáticamente.</p>` +
                `<label style="display:block;margin-bottom:6px;">Selecciona una cámara:` +
                `<select id="cameraSelector" style="margin-left:8px;">${opts}</select></label>` +
                `<button onclick="iniciarEscanerQRManual()">Usar esta cámara</button>`;
        }
    } else {
        mostrarErrorCamara(
            `<strong>❌ No se pudo acceder a la cámara</strong><br><br>` +
            `Posibles causas:<ul style="margin:6px 0 0 18px;">` +
            `<li>La página se sirve en <b>HTTP</b> (se requiere HTTPS)</li>` +
            `<li>Permiso de cámara no concedido en el navegador</li>` +
            `<li>Otra aplicación está usando la cámara</li></ul>`
        );
    }
}

async function iniciarEscanerQRManual() {
    const sel = document.getElementById('cameraSelector');
    const globalSel = document.getElementById(getActiveQrCameraSelectId());
    const deviceId = (globalSel?.value || sel?.value || '').trim();
    if (!deviceId) return;
    const scannerContainerId = getActiveQrScannerId();
    const el = document.getElementById(scannerContainerId);
    if (el) el.innerHTML = '';
    qrCurrentCameraId = deviceId;

    const formats = (typeof Html5QrcodeSupportedFormats !== 'undefined')
        ? [Html5QrcodeSupportedFormats.QR_CODE, Html5QrcodeSupportedFormats.CODE_128,
           Html5QrcodeSupportedFormats.CODE_39, Html5QrcodeSupportedFormats.EAN_13]
        : undefined;
    try {
        qrScannerInstance = new Html5Qrcode(scannerContainerId);
        await qrScannerInstance.start(
            { deviceId: { exact: deviceId } },
            {
                fps: 15,
                qrbox: (viewfinderWidth, viewfinderHeight) => {
                    const minDim = Math.min(viewfinderWidth, viewfinderHeight);
                    const boxSize = Math.max(200, Math.floor(minDim * 0.85));
                    return { width: boxSize, height: boxSize };
                },
                formatsToSupport: formats,
                aspectRatio: 1.0,
            },
            async (decodedText) => { await manejarQRLeido(decodedText); },
            () => {}
        );
    } catch (err) {
        qrScannerInstance = null;
        const selectedLabel = globalSel?.selectedOptions?.[0]?.textContent || sel?.selectedOptions?.[0]?.textContent || deviceId;
        const reason = getErrorMessage(err, 'El navegador rechazó el inicio de la cámara seleccionada.');
        showAppAlert(`No se pudo iniciar la cámara seleccionada: ${selectedLabel}.`, {
            title: 'No fue posible abrir la cámara',
            tone: 'error',
            detail: reason,
            html: `<p>No se pudo iniciar la cámara seleccionada <strong>${escapeHtml(selectedLabel)}</strong>.</p>
                <ul style="margin:10px 0 0 18px; color:#4a6785; line-height:1.7;">
                    <li>Verifica que ninguna otra aplicación esté usando la cámara.</li>
                    <li>Pulsa <strong>Actualizar Cámaras</strong> y vuelve a intentarlo.</li>
                    <li>Si el navegador pidió permiso, confirma que el sitio tiene acceso permitido.</li>
                </ul>`,
        });
    }
}

async function detenerEscanerQR() {
    if (!qrScannerInstance) return;
    try {
        await qrScannerInstance.stop();
        await qrScannerInstance.clear();
    } catch (_) {
        // ignore cleanup errors
    }
    qrScannerInstance = null;
    const btn = document.getElementById('qrCameraToggleBtn');
    if (btn) {
        btn.textContent = '📷 Iniciar Cámara';
        btn.classList.remove('scanning');
    }
}

function isQrScannerRunning() {
    return !!qrScannerInstance;
}

async function manejarQRLeido(decodedText) {
    const normalizedCode = String(decodedText || '').trim();
    if (!normalizedCode) return;

    const nowMs = Date.now();
    if (qrDecodeInFlight) return;
    if (normalizedCode === qrLastDecodedText && (nowMs - qrLastDecodedAtMs) < QR_SCAN_DUPLICATE_WINDOW_MS) {
        return;
    }

    qrDecodeInFlight = true;
    qrLastDecodedText = normalizedCode;
    qrLastDecodedAtMs = nowMs;

    // Detener inmediatamente para evitar lecturas múltiples del mismo código.
    await detenerEscanerQR();

    const week = getActiveQrWeek();

    try {
        const result = await apiClient.verificarCodigoEscaneado(normalizedCode, week);
        const agente = result.agente || {};
        const verificacion = result.verificacion || {};
        currentVerificationData = { agente, verificacion };

        const qrAgente = document.getElementById('qrAgenteId');
        const qrVoip = document.getElementById('qrVoip');
        const qrSemana = document.getElementById('qrSemana');
        if (qrAgente) qrAgente.value = agente.id || '';
        if (qrVoip) qrVoip.value = agente.numero_voip || '';
        if (qrSemana && !qrSemana.value && verificacion.semana_inicio) qrSemana.value = verificacion.semana_inicio;

        const pagoAgente = document.getElementById('pagoAgenteId');
        const pagoTelefono = document.getElementById('pagoTelefono');
        const pagoVoip = document.getElementById('pagoVoip');
        const pagoSemana = document.getElementById('pagoSemana');
        const pagoMonto = document.getElementById('pagoMonto');
        if (pagoAgente) pagoAgente.value = agente.id || '';
        if (pagoTelefono) pagoTelefono.value = agente.telefono || '';
        if (pagoVoip) pagoVoip.value = agente.numero_voip || '';
        if (pagoSemana && verificacion.semana_inicio) pagoSemana.value = verificacion.semana_inicio;
        if (pagoMonto) pagoMonto.value = Number(verificacion.cuota_semanal || 0).toFixed(2);

        if (currentSection === 'qrScan') {
            renderEscaneoResumen(currentVerificationData);
            await consultarResumenPagoActual(false);
        } else {
            await verificarAgenteQR();
        }
    } catch (error) {
        console.error('Error de escaneo:', error);
        alert('No se pudo validar el código escaneado: ' + error.message);
    } finally {
        qrDecodeInFlight = false;
    }
}

function renderLineasEstado(lineas) {
    const container = document.getElementById('lineasEstadoContainer');
    if (!container) return;
    if (!lineas || !lineas.length) {
        container.innerHTML = '<p>No hay líneas registradas.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr>';
    html += '<th>ID</th><th>Línea</th><th>Lada</th><th>Tipo</th><th>Categoría</th><th>Conexión</th><th>Último uso</th><th>Estado</th><th>Agente</th><th>Acciones</th>';
    html += '</tr></thead><tbody>';

    lineas.forEach(linea => {
        const safeLineaId = resolveLineaId(linea);
        const ocupada = !!linea.ocupada;
        const agente = linea.agente ? `${getAgentDisplayName(linea.agente)} (ID ${linea.agente.id})` : '-';
        const estado = ocupada ? '<span class="payment-pill unpaid">OCUPADA</span>' : '<span class="payment-pill paid">LIBRE</span>';
        const categoria = String(linea.categoria_linea || 'NO_DEFINIDA');
        const conexion = String(linea.estado_conexion || 'DESCONOCIDA');
        const ultimoUso = formatDisplayDateTime(linea.fecha_ultimo_uso);
        const actions = [];
        if (!safeLineaId) {
            actions.push('<span class="hint">ID inválido</span>');
        } else if (ocupada) {
            actions.push(`<button class="btn btn-small btn-danger" onclick="liberarLinea(${safeLineaId})">Liberar</button>`);
        } else {
            actions.push('<span class="hint">Disponible</span>');
        }
        if (safeLineaId) {
            actions.push(`<button class="btn btn-small btn-secondary" onclick="abrirGestionLinea(${safeLineaId})">Editar</button>`);
        }
        html += `<tr>
            <td>${safeLineaId ?? '-'}</td>
            <td>${linea.numero}</td>
            <td>${linea.lada || '-'}</td>
            <td>${linea.tipo || '-'}</td>
            <td>${escapeHtml(categoria)}</td>
            <td>${escapeHtml(conexion)}</td>
            <td>${escapeHtml(ultimoUso)}</td>
            <td>${estado}</td>
            <td>${agente}</td>
            <td>${actions.join(' ')}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function resolveLineaId(linea) {
    const raw = linea?.id ?? linea?.linea_id ?? linea?.linea?.id ?? null;
    const normalized = Number(raw);
    return Number.isInteger(normalized) && normalized > 0 ? normalized : null;
}

function toDateTimeLocalValue(value) {
    return window.AppUtils.toDateTimeLocalValue(value);
}

function formatDisplayDateTime(value) {
    return window.AppUtils.formatDisplayDateTime(value);
}

function abrirGestionLinea(lineaId) {
    currentLineaEditId = Number(lineaId) || null;
    loadSection('lineas');
}

function limpiarFormularioLineaGestion() {
    currentLineaEditId = null;
    const lineaId = document.getElementById('lineaGestionId');
    const numero = document.getElementById('lineaGestionNumero');
    const tipo = document.getElementById('lineaGestionTipo');
    const categoria = document.getElementById('lineaGestionCategoria');
    const conexion = document.getElementById('lineaGestionConexion');
    const descripcion = document.getElementById('lineaGestionDescripcion');
    const ultimoUso = document.getElementById('lineaGestionUltimoUso');
    const result = document.getElementById('lineaGestionResult');
    if (lineaId) lineaId.value = '';
    if (numero) numero.value = '';
    if (tipo) tipo.value = 'MANUAL';
    if (categoria) categoria.value = 'NO_DEFINIDA';
    if (conexion) conexion.value = 'DESCONOCIDA';
    if (descripcion) descripcion.value = '';
    if (ultimoUso) ultimoUso.value = '';
    if (result) result.innerHTML = '';
}

function renderLineasGestion(lineas) {
    const container = document.getElementById('lineasGestionContainer');
    if (!container) return;
    if (!Array.isArray(lineas) || !lineas.length) {
        container.innerHTML = '<p class="hint">No hay líneas para mostrar.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr>';
    html += '<th>ID</th><th>Número</th><th>Lada</th><th>Tipo</th><th>Categoría</th><th>Conexión</th><th>Último uso</th><th>Origen</th><th>Descripción</th><th>Estado</th><th>Agente</th><th>Acciones</th>';
    html += '</tr></thead><tbody>';

    lineas.forEach(linea => {
        const safeLineaId = resolveLineaId(linea);
        const ocupada = !!linea.ocupada;
        const agente = linea.agente ? `${getAgentDisplayName(linea.agente)} (ID ${linea.agente.id})` : '-';
        const estado = ocupada ? '<span class="payment-pill unpaid">OCUPADA</span>' : '<span class="payment-pill paid">LIBRE</span>';
        const origen = String(linea.origen || 'MANUAL').toUpperCase();
        const categoria = String(linea.categoria_linea || 'NO_DEFINIDA');
        const conexion = String(linea.estado_conexion || 'DESCONOCIDA');
        const ultimoUso = formatDisplayDateTime(linea.fecha_ultimo_uso);
        const actions = [];
        if (!safeLineaId) {
            actions.push('<span class="hint">ID inválido</span>');
        } else {
            actions.push(`<button type="button" class="btn btn-small" onclick="editarLineaGestion(${safeLineaId})">Editar</button>`);
            if (ocupada) {
                actions.push(`<button type="button" class="btn btn-small btn-danger" onclick="liberarLinea(${safeLineaId})">Liberar</button>`);
                if (linea.agente?.id) {
                    actions.push(`<button type="button" class="btn btn-small btn-secondary" onclick="mostrarQrParaAgente(${linea.agente.id}, '${String(getAgentDisplayName(linea.agente)).replace(/'/g, "\\'")}')">QR Agente</button>`);
                }
            } else {
                actions.push(`<button type="button" class="btn btn-small btn-secondary" onclick="desactivarLineaGestion(${safeLineaId})">Desactivar</button>`);
            }
        }

        html += `<tr>
            <td>${safeLineaId ?? '-'}</td>
            <td>${escapeHtml(linea.numero || '-')}</td>
            <td>${escapeHtml(linea.lada || '-')}</td>
            <td>${escapeHtml(linea.tipo || '-')}</td>
            <td>${escapeHtml(categoria)}</td>
            <td>${escapeHtml(conexion)}</td>
            <td>${escapeHtml(ultimoUso)}</td>
            <td>${escapeHtml(origen)}</td>
            <td>${escapeHtml(linea.descripcion || '-')}</td>
            <td>${estado}</td>
            <td>${escapeHtml(agente)}</td>
            <td>${actions.join(' ')}</td>
        </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function editarLineaGestion(lineaId) {
    const linea = currentLineasGestionRows.find(item => Number(item.id) === Number(lineaId));
    if (!linea) {
        alert('No se encontró la línea en el listado actual.');
        return;
    }
    currentLineaEditId = Number(linea.id);
    const lineaIdEl = document.getElementById('lineaGestionId');
    const numero = document.getElementById('lineaGestionNumero');
    const tipo = document.getElementById('lineaGestionTipo');
    const categoria = document.getElementById('lineaGestionCategoria');
    const conexion = document.getElementById('lineaGestionConexion');
    const descripcion = document.getElementById('lineaGestionDescripcion');
    const ultimoUso = document.getElementById('lineaGestionUltimoUso');
    if (lineaIdEl) lineaIdEl.value = String(linea.id);
    if (numero) numero.value = String(linea.numero || '');
    if (tipo) tipo.value = String(linea.tipo || 'MANUAL').toUpperCase();
    if (categoria) categoria.value = String(linea.categoria_linea || 'NO_DEFINIDA').toUpperCase();
    if (conexion) conexion.value = String(linea.estado_conexion || 'DESCONOCIDA').toUpperCase();
    if (descripcion) descripcion.value = String(linea.descripcion || '');
    if (ultimoUso) ultimoUso.value = toDateTimeLocalValue(linea.fecha_ultimo_uso);
    numero?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function guardarLineaGestion(e) {
    e.preventDefault();
    const lineaId = Number(document.getElementById('lineaGestionId')?.value || currentLineaEditId || 0);
    const numero = document.getElementById('lineaGestionNumero')?.value.trim();
    const tipo = document.getElementById('lineaGestionTipo')?.value || 'MANUAL';
    const categoria = document.getElementById('lineaGestionCategoria')?.value || 'NO_DEFINIDA';
    const conexion = document.getElementById('lineaGestionConexion')?.value || 'DESCONOCIDA';
    const descripcion = document.getElementById('lineaGestionDescripcion')?.value.trim() || '';
    const ultimoUso = document.getElementById('lineaGestionUltimoUso')?.value || '';
    const result = document.getElementById('lineaGestionResult');

    if (!numero) {
        alert('El número de línea es obligatorio.');
        return;
    }

    const payload = {
        numero,
        tipo,
        categoria_linea: categoria,
        estado_conexion: conexion,
        fecha_ultimo_uso: ultimoUso || null,
        descripcion,
        sincronizar: true,
    };

    try {
        if (lineaId > 0) {
            await apiClient.actualizarLinea(lineaId, payload);
            if (result) result.innerHTML = '<p style="color:green;">Línea actualizada correctamente.</p>';
        } else {
            await apiClient.crearLinea(payload);
            if (result) result.innerHTML = '<p style="color:green;">Línea creada/reactivada correctamente.</p>';
        }
        limpiarFormularioLineaGestion();
        await cargarLineasYAgentes();
        await cargarLineasGestion();
    } catch (error) {
        console.error('Error:', error);
        if (result) result.innerHTML = `<p style="color:red;">Error: ${escapeHtml(error.message)}</p>`;
        alert('Error guardando línea: ' + error.message);
    }
}

async function desactivarLineaGestion(lineaId) {
    if (!(await showAppConfirm('¿Desactivar esta línea?', { title: 'Desactivar línea', tone: 'warning' }))) return;
    try {
        await apiClient.desactivarLinea(lineaId);
        await cargarLineasYAgentes();
        await cargarLineasGestion();
    } catch (error) {
        console.error('Error:', error);
        alert('Error desactivando línea: ' + error.message);
    }
}

async function cargarLineasGestion() {
    const container = document.getElementById('lineasGestionContainer');
    if (!container) return;
    try {
        const search = (document.getElementById('lineasGestionSearch')?.value || '').trim();
        const lada = (document.getElementById('lineasGestionLada')?.value || '').trim();
        const estado = (document.getElementById('lineasGestionEstado')?.value || 'todas').trim() || 'todas';
        const [lineasRes, ladasRes] = await Promise.all([
            apiClient.getLineas(search, false, lada, estado),
            apiClient.getLadas(''),
        ]);
        const lineas = Array.isArray(lineasRes?.data) ? lineasRes.data : [];
        currentLineasGestionRows = lineas;
        renderLineasGestion(lineas);

        const ladas = Array.isArray(ladasRes?.data) ? ladasRes.data : [];
        const ladaSelect = document.getElementById('lineasGestionLada');
        if (ladaSelect) {
            const prev = ladaSelect.value;
            let html = '<option value="">-- Todas las ladas --</option>';
            ladas.forEach(l => {
                html += `<option value="${l.codigo}">${l.codigo}${l.nombre_region ? ` - ${l.nombre_region}` : ''}</option>`;
            });
            ladaSelect.innerHTML = html;
            if (prev && ladas.some(l => l.codigo === prev)) {
                ladaSelect.value = prev;
            }
        }

        if (currentLineaEditId) {
            editarLineaGestion(currentLineaEditId);
        }
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<p style="color:red;">Error cargando líneas: ${escapeHtml(error.message)}</p>`;
    }
}

function getAgentExtras(agent) {
    const extras = agent?.datos_adicionales;
    if (!extras || typeof extras !== 'object' || Array.isArray(extras)) {
        return {};
    }
    return extras;
}

function resetGestionAgentePanel() {
    currentEditingAgentId = null;
    const panel = document.getElementById('editarAgentePanel');
    if (panel) panel.style.display = 'none';
    const ids = [
        'editarAgenteId',
        'editarAgenteNombre',
        'editarAgenteAlias',
        'editarAgenteUbicacion',
        'editarAgenteTelefono',
        'editarAgenteFp',
        'editarAgenteFc',
        'editarAgenteGrupo',
        'editarAgenteVoip',
    ];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
}

function buildAgentIdentityLabel(agent) {
    const extras = getAgentExtras(agent);
    const nombre = String(agent?.nombre || '').trim();
    const alias = String(extras.alias || '').trim();
    const telefono = String(agent?.telefono || '').trim();
    const parts = [];

    if (alias && alias.toLowerCase() !== nombre.toLowerCase()) parts.push(`Alias: ${alias}`);
    if (telefono) parts.push(`Tel: ${telefono}`);
    parts.push(`ID ${agent.id}`);

    return parts.join(' | ');
}

function dedupeAgentesPorNombreAlias(agentes) {
    const map = new Map();
    (agentes || []).forEach(agent => {
        const extras = getAgentExtras(agent);
        const key = `${String(agent?.nombre || '').trim().toLowerCase()}|${String(extras.alias || '').trim().toLowerCase()}`;
        const current = map.get(key);
        if (!current) {
            map.set(key, agent);
            return;
        }

        const currentLines = Array.isArray(current.lineas) ? current.lineas.length : 0;
        const nextLines = Array.isArray(agent.lineas) ? agent.lineas.length : 0;
        if (nextLines > currentLines) {
            map.set(key, agent);
            return;
        }

        if (nextLines === currentLines) {
            const currentScore = Number(Boolean(current.telefono)) + Number(Boolean(getAgentExtras(current).numero_voip));
            const nextScore = Number(Boolean(agent.telefono)) + Number(Boolean(extras.numero_voip));
            if (nextScore > currentScore || (nextScore === currentScore && Number(agent.id) < Number(current.id))) {
                map.set(key, agent);
            }
        }
    });
    return Array.from(map.values());
}

function irAAsignacionLineaAgente(agenteId) {
    pendingAltaAgentId = Number(agenteId) || null;
    loadSection('altasAgentes');
}

function renderGestionAgentes(agentes) {
    const container = document.getElementById('gestionAgentesContainer');
    if (!container) return;
    if (!agentes.length) {
        container.innerHTML = '<p>No hay agentes activos que coincidan con la búsqueda.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr>';
    html += '<th>ID</th><th>Alias (Principal)</th><th>Teléfono</th><th>Líneas</th><th>Ladas</th><th>Acciones</th>';
    html += '</tr></thead><tbody>';

    agentes.forEach(agent => {
        const extras = getAgentExtras(agent);
        const displayName = getAgentDisplayName(agent);
        const lines = Array.isArray(agent.lineas) ? agent.lineas : [];
        const lineText = lines.length ? lines.map(line => `${line.numero} (${line.tipo || 'N/A'})`).join(', ') : 'Sin líneas';
        const ladas = Array.isArray(agent.ladas_preferidas) && agent.ladas_preferidas.length ? agent.ladas_preferidas.join(', ') : '-';
        const identityLabel = buildAgentIdentityLabel(agent);
        html += `<tr>
            <td>${agent.id}</td>
            <td><strong>${escapeHtml(displayName || 'SIN_ALIAS')}</strong><br><span class="hint">${escapeHtml(identityLabel)}</span></td>
            <td>${agent.telefono || '-'}</td>
            <td>${lineText}</td>
            <td>${ladas}</td>
            <td>
                <button onclick="editarAgenteGestion(${agent.id})" class="btn btn-small">Editar</button>
                <button onclick="mostrarQrParaAgente(${agent.id}, '${String(displayName || 'Agente').replace(/'/g, "\\'")}')" class="btn btn-small btn-secondary">QR</button>
                <button onclick="irAAsignacionLineaAgente(${agent.id})" class="btn btn-small btn-secondary" title="Asignar o cambiar línea">📞 Línea</button>
                <button onclick="liberarLineasAgente(${agent.id})" class="btn btn-small btn-secondary">Liberar líneas</button>
                <button onclick="darBajaAgente(${agent.id})" class="btn btn-small btn-danger">Baja</button>
            </td>
        </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function programarBusquedaAgentesGestion() {
    if (gestionAgenteSearchTimer) clearTimeout(gestionAgenteSearchTimer);
    gestionAgenteSearchTimer = setTimeout(() => {
        cargarAgentesGestion(false);
    }, 280);
}

async function cargarAgentesGestion(showErrors = true, forceRefresh = false) {
    try {
        const search = document.getElementById('gestionAgenteSearch')?.value.trim() || '';
        const cacheKey = search.toLowerCase();
        const now = Date.now();
        if (!forceRefresh && cacheKey === gestionAgenteCacheKey && (now - gestionAgenteCacheAtMs) < 8000) {
            currentAgentManagementRows = dedupeAgentesPorNombreAlias(gestionAgenteCacheRows);
            renderGestionAgentes(currentAgentManagementRows);
            return;
        }

        const res = await apiClient.getAgentesQR(search, 300);
        const filtered = (res.data || []).filter(a => a.es_activo !== false);
        gestionAgenteCacheKey = cacheKey;
        gestionAgenteCacheRows = filtered;
        gestionAgenteCacheAtMs = now;
        currentAgentManagementRows = dedupeAgentesPorNombreAlias(filtered);
        renderGestionAgentes(currentAgentManagementRows);
    } catch (error) {
        console.error('Error:', error);
        currentAgentManagementRows = [];
        renderGestionAgentes([]);
        if (showErrors) {
            alert('Error cargando agentes: ' + error.message);
        }
    }
}

async function editarAgenteGestion(agenteId) {
    const agent = currentAgentManagementRows.find(item => Number(item.id) === Number(agenteId));
    if (!agent) {
        alert('No se encontró el agente en la lista actual.');
        return;
    }

    const extras = getAgentExtras(agent);
    currentEditingAgentId = Number(agenteId);
    document.getElementById('editarAgenteId').value = String(agenteId);
    document.getElementById('editarAgenteNombre').value = agent.nombre || '';
    document.getElementById('editarAgenteAlias').value = extras.alias || '';
    document.getElementById('editarAgenteUbicacion').value = extras.ubicacion || '';
    document.getElementById('editarAgenteTelefono').value = agent.telefono || '';
    document.getElementById('editarAgenteFp').value = extras.fp || '';
    document.getElementById('editarAgenteFc').value = extras.fc || '';
    document.getElementById('editarAgenteGrupo').value = extras.grupo || '';
    document.getElementById('editarAgenteVoip').value = extras.numero_voip || '';
    const panel = document.getElementById('editarAgentePanel');
    if (panel) {
        panel.style.display = 'block';
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function cancelarEdicionAgente() {
    resetGestionAgentePanel();
}

async function guardarCambiosAgente(e) {
    e.preventDefault();
    const agenteId = Number(document.getElementById('editarAgenteId')?.value || currentEditingAgentId || 0);
    if (!agenteId) {
        alert('No hay un agente seleccionado para editar.');
        return;
    }

    const agent = currentAgentManagementRows.find(item => Number(item.id) === agenteId) || {};
    const extras = getAgentExtras(agent);
    const payload = {
        nombre: normalizeNullableInput(document.getElementById('editarAgenteNombre')?.value),
        telefono: normalizeNullableInput(document.getElementById('editarAgenteTelefono')?.value),
        datos_adicionales: {
            ...extras,
            alias: normalizeNullableInput(document.getElementById('editarAgenteAlias')?.value),
            ubicacion: normalizeNullableInput(document.getElementById('editarAgenteUbicacion')?.value),
            fp: normalizeNullableInput(document.getElementById('editarAgenteFp')?.value),
            fc: normalizeNullableInput(document.getElementById('editarAgenteFc')?.value),
            grupo: normalizeNullableInput(document.getElementById('editarAgenteGrupo')?.value),
            numero_voip: normalizeNullableInput(document.getElementById('editarAgenteVoip')?.value),
        }
    };

    if (!payload.nombre && !payload.datos_adicionales.alias) {
        alert('Captura nombre o alias para identificar al agente.');
        return;
    }

    payload.datos_adicionales = Object.fromEntries(Object.entries(payload.datos_adicionales).filter(([, value]) => value !== null && value !== ''));

    try {
        await apiClient.actualizarDato(agenteId, payload);
        alert('Agente actualizado correctamente.');
        resetGestionAgentePanel();
        await cargarAgentesGestion(false, true);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error guardando cambios: ' + error.message);
    }
}

async function liberarLineasAgente(agenteId) {
    const agent = currentAgentManagementRows.find(item => Number(item.id) === Number(agenteId));
    const lines = Array.isArray(agent?.lineas) ? agent.lineas : [];
    const agentLabel = getAgentDisplayName(agent || { id: agenteId }, `ID ${agenteId}`);
    if (!lines.length) {
        alert('Este agente no tiene líneas asignadas.');
        return;
    }
    if (!(await showAppConfirm(`¿Liberar ${lines.length} línea(s) del agente ${agentLabel}?`, { title: 'Liberar líneas', tone: 'warning' }))) return;

    try {
        const normalizeLineId = (line) => {
            const raw = line?.id ?? line?.linea_id ?? line?.linea?.id ?? null;
            const n = Number(raw);
            return Number.isInteger(n) && n > 0 ? n : null;
        };

        for (const line of lines) {
            const lineId = normalizeLineId(line);
            if (!lineId) {
                const lineLabel = String(line?.numero || line?.linea?.numero || 'sin_numero');
                throw new Error(`Validación fallida: no se encontró ID válido para la línea ${lineLabel}`);
            }
            await apiClient.liberarLinea(lineId, agenteId);
        }
        alert('Líneas liberadas correctamente.');
        await cargarAgentesGestion(false, true);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error liberando líneas: ' + error.message);
    }
}

async function darBajaAgente(agenteId) {
    const agent = currentAgentManagementRows.find(item => Number(item.id) === Number(agenteId));
    const label = getAgentDisplayName(agent || { id: agenteId }, `ID ${agenteId}`);
    if (!(await showAppConfirm(`¿Dar de baja al agente ${label}?`, { title: 'Baja de agente', tone: 'warning', acceptText: 'Dar de baja' }))) return;
    if ((agent?.lineas || []).length && !(await showAppConfirm('El agente tiene líneas asignadas. La baja no las libera automáticamente.', { title: '¿Continuar con la baja?', tone: 'warning', acceptText: 'Continuar' }))) return;

    try {
        await apiClient.eliminarDato(agenteId);
        alert('Agente dado de baja correctamente.');
        if (currentEditingAgentId === Number(agenteId)) {
            resetGestionAgentePanel();
        }
        await cargarAgentesGestion(false, true);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error dando de baja al agente: ' + error.message);
    }
}

async function abrirControlManualDeudaDesdePago() {
    if (!canAdmin()) {
        showAppAlert('Solo administradores pueden ajustar saldo manualmente.', { tone: 'warning', title: 'Acceso restringido' });
        return;
    }

    const agenteId = Number(
        document.getElementById('pagoAgenteId')?.value ||
        document.getElementById('qrAgenteId')?.value ||
        document.getElementById('qrCtxAgenteId')?.value ||
        0
    );
    const semana =
        document.getElementById('pagoSemana')?.value ||
        document.getElementById('qrSemana')?.value ||
        document.getElementById('qrCtxSemana')?.value ||
        mondayISO();

    if (typeof qrSetTab === 'function') qrSetTab('config');

    const semanaInput = document.getElementById('deudaManualSemana');
    if (agenteId > 0) _setDeudaManualAgente(agenteId);
    if (semanaInput) semanaInput.value = String(semana);

    const panel = document.getElementById('deudaManualPanel');
    if (panel) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    if (agenteId > 0) {
        await consultarDeudaManualAgente(false);
    } else {
        showAppAlert('Captura primero un ID de agente en Pago o Estado para precargar el ajuste.', { tone: 'info', title: 'Ajuste manual de deuda' });
    }
}

async function cargarLineasYAgentes() {
    try {
        const lada = (document.getElementById('lineasLadaFilter')?.value || '').trim();
        const estado = (document.getElementById('lineasEstadoFiltro')?.value || 'todas').trim() || 'todas';
        const [lineasRes, agentesRes] = await Promise.all([
            apiClient.getLineas('', false, lada, estado),
            apiClient.getAgentesQR('')
        ]);

        const lineas = lineasRes.data || [];
        const agentes = dedupeAgentesPorNombreAlias((agentesRes.data || []).filter(a => a.es_activo !== false));
        currentAltasAgents = agentes;
        currentAltasLineas = lineas;
        const ladas = (await apiClient.getLadas('')).data || [];

        const ladaSelect = document.getElementById('lineasLadaFilter');
        if (ladaSelect) {
            const prev = ladaSelect.value;
            let html = '<option value="">-- Filtrar líneas por lada --</option>';
            ladas.forEach(l => {
                html += `<option value="${l.codigo}">${l.codigo}${l.nombre_region ? ` - ${l.nombre_region}` : ''}</option>`;
            });
            ladaSelect.innerHTML = html;
            if (prev && ladas.some(l => l.codigo === prev)) {
                ladaSelect.value = prev;
            }
        }

        const agenteLadaSelect = document.getElementById('agenteLadaObjetivoSelect');
        if (agenteLadaSelect) {
            const prev = agenteLadaSelect.value;
            let html = '<option value="">-- Lada preferida (opcional) --</option>';
            ladas.forEach(l => {
                html += `<option value="${l.codigo}">${l.codigo}${l.nombre_region ? ` - ${l.nombre_region}` : ''}</option>`;
            });
            agenteLadaSelect.innerHTML = html;
            if (prev && ladas.some(l => l.codigo === prev)) {
                agenteLadaSelect.value = prev;
            }
        }

        const lineaSelect = document.getElementById('lineaAsignarSelect');
        if (lineaSelect) {
            let html = '<option value="">-- Línea --</option>';
            lineas.forEach(l => {
                html += `<option value="${l.id}">${l.numero} [${l.lada || 'sin lada'}] (${l.tipo || 'N/A'}) ${l.ocupada ? '[OCUPADA]' : '[LIBRE]'}</option>`;
            });
            lineaSelect.innerHTML = html;
        }

        const lineaManualSelect = document.getElementById('agenteLineaManualSelect');
        if (lineaManualSelect) {
            let html = '<option value="">-- Línea manual existente --</option>';
            lineas.forEach(l => {
                html += `<option value="${l.id}">${l.numero} [${l.lada || 'sin lada'}] ${l.ocupada ? '(ocupada)' : '(libre)'}</option>`;
            });
            lineaManualSelect.innerHTML = html;
        }

        const agenteSelect = document.getElementById('agenteAsignarSelect');
        if (agenteSelect) {
            let html = '<option value="">-- Agente --</option>';
            agentes.forEach(a => {
                html += `<option value="${a.id}">${escapeHtml(getAgentDisplayName(a))} | ${escapeHtml(buildAgentIdentityLabel(a))}</option>`;
            });
            agenteSelect.innerHTML = html;
            if (pendingAltaAgentId) {
                agenteSelect.value = String(pendingAltaAgentId);
                pendingAltaAgentId = null;
                agenteSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        renderLineasEstado(lineas);
        if (currentSection === 'lineas') {
            renderLineasGestion(lineas);
        }
        cambiarModoAsignacionAgente();
        sincronizarCamposLineaAsignar();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando agentes y líneas: ' + error.message);
    }
}

function cambiarModoAsignacionAgente() {
    const modo = document.getElementById('agenteModoAsignacion')?.value || 'ninguna';
    const selectManual = document.getElementById('agenteLineaManualSelect');
    const inputManual = document.getElementById('agenteLineaManualInput');
    const categoriaManual = document.getElementById('agenteLineaCategoriaSelect');
    const conexionManual = document.getElementById('agenteLineaConexionSelect');
    if (!selectManual || !inputManual || !categoriaManual || !conexionManual) return;

    const showManual = modo === 'manual';
    selectManual.style.display = showManual ? 'inline-block' : 'none';
    inputManual.style.display = showManual ? 'inline-block' : 'none';
    categoriaManual.style.display = showManual ? 'inline-block' : 'none';
    conexionManual.style.display = showManual ? 'inline-block' : 'none';
    if (!showManual) {
        categoriaManual.value = 'NO_DEFINIDA';
        conexionManual.value = 'DESCONOCIDA';
    }
}

function sincronizarCamposLineaAsignar() {
    const lineaId = Number(document.getElementById('lineaAsignarSelect')?.value || 0);
    const categoriaSelect = document.getElementById('lineaAsignarCategoria');
    const conexionSelect = document.getElementById('lineaAsignarConexion');
    if (!categoriaSelect || !conexionSelect) return;
    if (!lineaId) {
        categoriaSelect.value = '';
        conexionSelect.value = '';
        return;
    }

    const linea = (currentAltasLineas || []).find(item => Number(item.id) === lineaId);
    categoriaSelect.value = String(linea?.categoria_linea || '').toUpperCase();
    conexionSelect.value = String(linea?.estado_conexion || '').toUpperCase();
}

function resolveAltasAgent(agenteId) {
    return currentAltasAgents.find(item => Number(item.id) === Number(agenteId)) || null;
}

async function solicitarConfiguracionPrimerCobro(agente, contexto = 'asignar') {
    const agenteNombre = String(agente?.nombre || `ID ${agente?.id || ''}`).trim();
    const intro = contexto === 'alta'
        ? `El agente ${agenteNombre} tendrá su primera línea. Configura el inicio de cobro o cargo inicial.`
        : `Primera línea para ${agenteNombre}. Configura el inicio de cobro o cargo inicial.`;
    const choice = await showAppPrompt('¿Qué configurar?\n1 = Semana de inicio  2 = Cargo inicial  3 = Ambos  (deja vacío para omitir)', {
        title: intro,
        placeholder: '1',
        defaultValue: '1',
    });
    if (choice === null) return null;

    const mode = String(choice || '').trim();
    const billing = { cobroDesdeSemana: null, cargoInicial: 0 };
    const askWeek = mode === '1' || mode === '3';
    const askInitial = mode === '2' || mode === '3';

    if (askWeek) {
        const suggestedWeek = mondayISO();
        const weekRaw = await showAppPrompt('Semana de inicio de cobro (AAAA-MM-DD):', {
            title: 'Semana de inicio',
            placeholder: suggestedWeek,
            defaultValue: suggestedWeek,
            detail: 'Deja el valor actual para usar la semana corriente.',
        });
        if (weekRaw === null) return null;
        const week = String(weekRaw || '').trim() || suggestedWeek;
        if (!/^\d{4}-\d{2}-\d{2}$/.test(week) || Number.isNaN(new Date(`${week}T00:00:00`).getTime())) {
            showAppAlert('Formato de semana inválido. Usa AAAA-MM-DD.', { tone: 'error', title: 'Formato incorrecto' });
            return null;
        }
        billing.cobroDesdeSemana = week;
    }

    if (askInitial) {
        const amountRaw = await showAppPrompt('Cargo inicial (MXN):', {
            title: 'Cargo inicial',
            placeholder: '0',
            defaultValue: '0',
            type: 'number',
            detail: 'Ejemplo: 300 o 450.50',
        });
        if (amountRaw === null) return null;
        const parsed = Number(String(amountRaw).replace(',', '.'));
        if (!Number.isFinite(parsed) || parsed < 0) {
            showAppAlert('Cargo inicial inválido.', { tone: 'error', title: 'Valor incorrecto' });
            return null;
        }
        billing.cargoInicial = parsed;
    }

    return billing;
}

async function crearLadaCatalogo(e) {
    e.preventDefault();
    const codigo = document.getElementById('ladaCodigoInput')?.value.trim();
    const nombreRegion = document.getElementById('ladaRegionInput')?.value.trim() || '';
    if (!codigo) {
        alert('Ingresa una lada válida.');
        return;
    }

    try {
        await apiClient.crearLada({ codigo, nombre_region: nombreRegion });
        alert('Lada creada/reactivada correctamente.');
        document.getElementById('ladaCodigoInput').value = '';
        document.getElementById('ladaRegionInput').value = '';
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error guardando lada: ' + error.message);
    }
}

async function crearAgenteManual(e) {
    e.preventDefault();
    const modo = document.getElementById('agenteModoAsignacion')?.value || 'ninguna';
    const payload = {
        nombre: normalizeNullableInput(document.getElementById('agenteNombreInput')?.value),
        alias: normalizeNullableInput(document.getElementById('agenteAliasInput')?.value),
        ubicacion: normalizeNullableInput(document.getElementById('agenteUbicacionInput')?.value),
        fp: normalizeNullableInput(document.getElementById('agenteFpInput')?.value),
        fc: normalizeNullableInput(document.getElementById('agenteFcInput')?.value),
        grupo: normalizeNullableInput(document.getElementById('agenteGrupoInput')?.value),
        modo_asignacion: modo,
        lada_objetivo: normalizeNullableInput(document.getElementById('agenteLadaObjetivoSelect')?.value)
    };

    if (!payload.nombre && !payload.alias) {
        alert('Captura nombre o alias para crear el agente.');
        return;
    }

    if (modo === 'manual') {
        payload.linea_id = Number(document.getElementById('agenteLineaManualSelect')?.value || 0) || null;
        payload.numero_linea_manual = normalizeNullableInput(document.getElementById('agenteLineaManualInput')?.value);
        payload.categoria_linea = document.getElementById('agenteLineaCategoriaSelect')?.value || 'NO_DEFINIDA';
        payload.estado_conexion = document.getElementById('agenteLineaConexionSelect')?.value || 'DESCONOCIDA';
        if (!payload.linea_id && !payload.numero_linea_manual) {
            alert('Para modo manual selecciona una línea o escribe un número nuevo.');
            return;
        }
    }

    if (modo === 'manual' || modo === 'auto') {
        const billing = await solicitarConfiguracionPrimerCobro(payload, 'alta');
        if (billing === null) {
            alert('Alta cancelada para no guardar una asignación inicial sin validar cobro.');
            return;
        }
        payload.cobro_desde_semana = billing.cobroDesdeSemana;
        payload.cargo_inicial = billing.cargoInicial;
    }

    try {
        const result = await apiClient.crearAgenteManual(payload);
        const data = result.data || {};
        document.getElementById('qrAgenteId').value = data.agente_id || '';
        const qrVoipInput = document.getElementById('qrVoip');
        if (qrVoipInput) qrVoipInput.value = '';
        const asignacion = data.asignacion || {};
        const lineaText = asignacion.asignada ? `Línea ${asignacion.linea_numero} asignada.` : 'Sin asignación inicial.';
        alert(`Agente creado (ID ${data.agente_id}). ${lineaText}`);

        [
            'agenteNombreInput',
            'agenteAliasInput',
            'agenteUbicacionInput',
            'agenteFpInput',
            'agenteFcInput',
            'agenteGrupoInput',
            'agenteLineaManualInput'
        ].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        document.getElementById('agenteModoAsignacion').value = 'ninguna';
        document.getElementById('agenteLadaObjetivoSelect').value = '';
        document.getElementById('agenteLineaManualSelect').value = '';
        document.getElementById('agenteLineaCategoriaSelect').value = 'NO_DEFINIDA';
        document.getElementById('agenteLineaConexionSelect').value = 'DESCONOCIDA';
        cambiarModoAsignacionAgente();

        await cargarLineasYAgentes();
        await cargarAgentesGestion(false);
        if (document.getElementById('agenteGenerarQrAlCrear')?.checked && data.agente_id) {
            await previsualizarQrAlta(data.agente_id);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creando agente manual: ' + error.message);
    }
}

async function sincronizarLineasPBX(e) {
    e.preventDefault();
    try {
        const response = await apiClient.syncLineas();
        const data = response.data || {};
        alert(`Sincronización completada. Fuente: ${data.source || 0}, nuevas: ${data.created || 0}, actualizadas: ${data.updated || 0}, bajas: ${data.deactivated || 0}, ladas nuevas: ${data.ladas_created || 0}.`);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error sincronizando líneas PBX: ' + error.message);
    }
}

async function asignarLineaAgente(e) {
    e.preventDefault();
    const lineaId = Number(document.getElementById('lineaAsignarSelect')?.value || 0);
    const agenteId = Number(document.getElementById('agenteAsignarSelect')?.value || 0);
    if (!lineaId || !agenteId) {
        alert('Selecciona línea y agente.');
        return;
    }

    try {
        const categoriaLinea = String(document.getElementById('lineaAsignarCategoria')?.value || '').trim().toUpperCase();
        const estadoConexion = String(document.getElementById('lineaAsignarConexion')?.value || '').trim().toUpperCase();
        const patchLinea = {};
        if (categoriaLinea) patchLinea.categoria_linea = categoriaLinea;
        if (estadoConexion) patchLinea.estado_conexion = estadoConexion;
        if (Object.keys(patchLinea).length > 0) {
            await apiClient.actualizarLinea(lineaId, patchLinea);
        }

        const agente = resolveAltasAgent(agenteId);
        const lineasActuales = Array.isArray(agente?.lineas) ? agente.lineas.length : 0;
        let billing = { cobroDesdeSemana: null, cargoInicial: 0 };
        if (lineasActuales === 0) {
            const configured = await solicitarConfiguracionPrimerCobro(agente || { id: agenteId }, 'asignar');
            if (configured === null) {
                alert('Asignación cancelada.');
                return;
            }
            billing = configured;
        }

        await apiClient.asignarLinea(lineaId, agenteId, billing);
        alert('Línea asignada correctamente.');
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error asignando línea: ' + error.message);
    }
}

async function liberarLinea(lineaId) {
    const normalized = Number(lineaId);
    if (!Number.isInteger(normalized) || normalized <= 0) {
        alert('Validación fallida: línea inválida para liberar.');
        return;
    }
    if (!(await showAppConfirm('¿Liberar esta línea?', { title: 'Liberar línea', tone: 'warning' }))) return;
    try {
        await apiClient.liberarLinea(normalized);
        alert('Línea liberada.');
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error liberando línea: ' + error.message);
    }
}

async function eliminarDato(id, uuid = '') {
    if (!(await showAppConfirm(`¿Eliminar el registro ID ${id}? Esta acción lo marcará como inactivo.`, { title: 'Eliminar registro', tone: 'warning', acceptText: 'Eliminar' }))) return;
    const confirmacion = await showAppPrompt('Para confirmar, escribe la palabra CONFIRMAR:', { title: 'Confirmar eliminación', placeholder: 'CONFIRMAR', tone: 'warning', acceptText: 'Confirmar' });
    if (confirmacion !== 'CONFIRMAR') {
        if (confirmacion !== null) showAppAlert('Palabra incorrecta. Operación cancelada.', { tone: 'warning', title: 'Cancelado' });
        return;
    }

    try {
        try {
            await apiClient.eliminarDato(id);
        } catch (error) {
            const detail = String(error?.message || '').toLowerCase();
            if (!uuid || !detail.includes('no encontrado')) {
                throw error;
            }
            const datoUuid = await apiClient.getDatoByUUID(uuid);
            await apiClient.eliminarDato(datoUuid.id);
        }
        alert('✅ Dato eliminado. Se generó un backup en la papelera.');
        buscarDatos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al eliminar: ' + error.message);
    }
}

function cambiarTabla() {
    cargarTodosLosDatos();
}

// === IMPORTACIÓN ===
async function importarArchivo(e) {
    e.preventDefault();
    const file = document.getElementById('archivoInput').files[0];
    const tipoArchivo = document.getElementById('tipoArchivo').value;
    const tablaDestino = document.getElementById('tablaDestino').value.trim();
    const delimitador = document.getElementById('delimitador').value;

    if (!file) {
        alert('Selecciona un archivo');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('tabla', tablaDestino || 'datos_importados');
    formData.append('delimitador', delimitador);

    try {
        document.getElementById('importProgress').style.display = 'block';
        document.getElementById('progressFill').style.width = '0%';

        const data = await fetchJson(`${API_URL}/import/${tipoArchivo}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body: formData
        });

        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress > 95) progress = 95;
            document.getElementById('progressFill').style.width = progress + '%';
        }, 500);

        let completed = false;
        while (!completed) {
            const status = await fetchJson(
                `${API_URL}/import/estado/${data.importacion_id}`,
                { headers: { 'Authorization': `Bearer ${authToken}` } }
            );

            const estado = status?.data?.estado;
            if (estado === 'SUCCESS' || estado === 'FAILED' || estado === 'PARTIAL') {
                clearInterval(interval);
                document.getElementById('progressFill').style.width = '100%';
                alert(`Importación ${estado}: ${status?.data?.registros_importados || 0} importados, ${status?.data?.registros_fallidos || 0} fallidos`);
                completed = true;
                document.getElementById('importProgress').style.display = 'none';
                document.getElementById('archivoInput').value = '';
            } else {
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        cargarTablas();
    } catch (error) {
        alert('Error: ' + error.message);
        document.getElementById('importProgress').style.display = 'none';
    }
}

function cambiarTipo() {
    const tipo = document.getElementById('tipoArchivo').value;
    const delimitador = document.getElementById('delimitador');

    if (tipo === 'csv') {
        delimitador.value = ',';
    } else if (tipo === 'txt' || tipo === 'dat') {
        delimitador.value = '|';
    }
}

// === QR ===
async function generarQR(e) {
    e.preventDefault();
    const contenido = document.getElementById('contenidoQR').value;

    if (!contenido) {
        alert('Ingresa contenido para el QR');
        return;
    }

    try {
        // Verificar que QRCode esté disponible
        if (typeof QRCode === 'undefined') {
            alert('Error: Librería QRCode no disponible. Recarga la página.');
            return;
        }
        
        // Usar librería QRCode.js (se debe agregar en HTML)
        const container = document.getElementById('qrContainer');
        container.innerHTML = '';
        
        const qr = new QRCode(container, {
            text: contenido,
            width: 200,
            height: 200,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: 'H'  // Changed from QRCode.CorrectLevel.H
        });

        const canvas = container.querySelector('canvas');
        if (canvas) {
            const link = document.createElement('a');
            link.href = canvas.toDataURL('image/png');
            link.download = 'qr_' + Date.now() + '.png';
            link.click();
        }

        alert('QR generado y descargado');
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function mostrarQR(data) {
    alert('QR Data: ' + data);
}

function renderSimpleQR(text, containerId = 'qrContainer') {
    const container = document.getElementById(containerId);
    if (!container) {
        console.warn(`Container with ID ${containerId} not found`);
        return;
    }
    container.innerHTML = '';
    
    // Verificar que QRCode esté disponible
    if (typeof QRCode === 'undefined') {
        console.warn('QRCode library not loaded, using external API');
        generarQrDesdeApiExterna(text, containerId);
        return;
    }
    
    try {
        // QRCode global from qrcode.js loaded in index.html
        new QRCode(container, {
            text,
            width: 220,
            height: 220,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: 'H'  // Changed from QRCode.CorrectLevel.H
        });
    } catch (e) {
        console.error('Error rendering QR with QRCode.js:', e);
        // Fallback a API externa si hay error
        container.innerHTML = '';
        generarQrDesdeApiExterna(text, containerId);
    }
}

function generarQrDesdeApiExterna(text, containerId = 'qrContainer') {
    const container = document.getElementById(containerId);
    if (!container) {
        console.warn(`Container with ID ${containerId} not found`);
        return;
    }
    container.innerHTML = '';
    
    try {
        // Usar QR Server API como fallback
        const encodedText = encodeURIComponent(text);
        const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodedText}`;
        
        const img = document.createElement('img');
        img.src = qrUrl;
        img.alt = 'QR Code';
        img.style.cssText = 'max-width: 220px; height: auto; border: 1px solid #ccc; border-radius: 4px; padding: 8px; background: #fff;';
        
        img.onerror = function() {
            container.innerHTML = '<p style="color: red; padding: 12px; background: #ffe6e6; border-radius: 4px;">Error cargando QR. Intenta más tarde.</p>';
            console.error('Error loading QR from external API');
        };
        
        img.onload = function() {
            console.log('QR loaded successfully from external API');
        };
        
        container.appendChild(img);
    } catch (e) {
        console.error('Error in generarQrDesdeApiExterna:', e);
        container.innerHTML = '<p style="color: red; padding: 12px; background: #ffe6e6; border-radius: 4px;">Error generando QR: ' + e.message + '</p>';
    }
}

function prepararPagoDesdeVerificacion(agente, verificacion) {
    document.getElementById('pagoAgenteId').value = agente.id || '';
    document.getElementById('pagoTelefono').value = agente.telefono || '';
    document.getElementById('pagoVoip').value = agente.numero_voip || '';
    document.getElementById('pagoSemana').value = verificacion.semana_inicio || mondayISO();
    document.getElementById('pagoMonto').value = Number(verificacion.cuota_semanal || verificacion.saldo_acumulado || verificacion.monto || 300);
    document.getElementById('pagoPagado').checked = true;
    const liquidarEl = document.getElementById('pagoLiquidarTotal');
    if (liquidarEl) liquidarEl.checked = false;
    const obsEl = document.getElementById('pagoObservaciones');
    if (obsEl) obsEl.value = '';
    document.getElementById('pagoAgenteId').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function prepararPagoActualVerificado() {
    if (!currentVerificationData) {
        alert('Primero verifica un agente.');
        return;
    }
    prepararPagoDesdeVerificacion(currentVerificationData.agente, currentVerificationData.verificacion);
}

async function verificarAgenteQR() {
    const agenteId = document.getElementById('qrAgenteId').value;
    if (!agenteId) {
        alert('Ingresa ID del agente.');
        return;
    }

    const voip = document.getElementById('qrVoip').value.trim();
    const semana = document.getElementById('qrSemana').value;

    try {
        const result = await apiClient.verificarAgenteQR(agenteId, '', voip, semana);
        const v = result.verificacion || {};
        const a = result.agente || {};
        const box = document.getElementById('qrVerificationResult');
        currentVerificationData = { agente: a, verificacion: v };
        const paidClass = v.pagado ? 'payment-status paid' : 'payment-status unpaid';
        const paidText = v.pagado ? 'Al Corriente' : 'Pendiente de Pago';
        const lineas = Array.isArray(a.lineas) ? a.lineas : [];
        const lineasTxt = lineas.length
            ? lineas.map(x => `${x.numero} (${x.tipo || 'N/A'})`).join(', ')
            : 'Sin líneas asignadas';
        const actionButton = v.pagado
            ? ''
            : `<button type="button" class="btn" onclick="prepararPagoActualVerificado()">Registrar pago ahora</button>`;

        box.innerHTML = `
            <div class="card ${paidClass}" style="padding:12px;border-radius:8px;">
                <strong>Agente:</strong> ${a.nombre || '-'} (ID ${a.id || '-'})<br>
                <strong>Teléfono:</strong> ${a.telefono || '-'}<br>
                <strong>VoIP:</strong> ${a.numero_voip || '-'}<br>
                <strong>Asignación válida:</strong> ${v.asignacion_valida ? 'SI' : 'NO'}<br>
                <strong>Líneas:</strong> ${lineasTxt}<br>
                <strong>Estado:</strong> <span class="payment-pill ${v.pagado ? 'paid' : 'unpaid'}">${paidText}</span><br>
                <strong>Cuota:</strong> $${Number(v.cuota_semanal ?? 0).toFixed(2)} MXN<br>
                <strong>Monto:</strong> $${Number(v.monto ?? 0).toFixed(2)} MXN<br>
                <strong>Abonado acumulado:</strong> $${Number(v.total_abonado ?? 0).toFixed(2)} MXN<br>
                <strong>Saldo acumulado:</strong> $${Number(v.saldo_acumulado ?? 0).toFixed(2)} MXN<br>
                <strong>Semanas pendientes:</strong> ${Number(v.semanas_pendientes ?? 0)}<br>
                <strong>Fecha pago:</strong> ${v.fecha_pago ? new Date(v.fecha_pago).toLocaleString() : 'Sin pago registrado'}<br>
                <div style="margin-top:12px">${actionButton}</div>
            </div>
        `;
    } catch (error) {
        console.error('Error:', error);
        alert('Error verificando agente: ' + error.message);
    }
}

async function registrarPagoSemanal(e) {
    e.preventDefault();
    const liquidarTotal = !!document.getElementById('pagoLiquidarTotal')?.checked;
    const payload = {
        agente_id: Number(document.getElementById('pagoAgenteId').value),
        telefono: document.getElementById('pagoTelefono').value.trim() || null,
        numero_voip: document.getElementById('pagoVoip').value.trim() || null,
        semana_inicio: document.getElementById('pagoSemana').value,
        monto: Number(document.getElementById('pagoMonto').value || 0),
        pagado: document.getElementById('pagoPagado').checked,
        liquidar_total: liquidarTotal,
        observaciones: document.getElementById('pagoObservaciones')?.value?.trim() || null
    };

    try {
        const pago = await apiClient.registrarPagoSemanal(payload);
        const recibo = pago.recibo || {};
        const estadoPago = (pago.pagado === true)
            ? 'Al Corriente'
            : (Number(pago.abono_registrado ?? payload.monto ?? 0) > 0 ? 'Abonado' : 'Pendiente de Pago');
        lastReceiptData = {
            agente_id: payload.agente_id,
            nombre: currentVerificationData?.agente?.nombre || `Agente ${payload.agente_id}`,
            telefono: payload.telefono,
            numero_voip: payload.numero_voip,
            linea_numero: recibo.linea_numero || null,
            semana_inicio: payload.semana_inicio,
            monto: Number(pago.monto ?? payload.monto ?? 0),
            fecha_pago: pago.fecha_pago || new Date().toISOString(),
            estado: estadoPago,
            pago_id: pago.id || null,
            pagado: !!pago.pagado,
            abono_registrado: Number(pago.abono_registrado ?? payload.monto ?? 0),
            saldo_acumulado: Number(pago.saldo_acumulado ?? 0),
            recibo_token: recibo.token || null,
            expira_en: recibo.expira_en || null,
        };
        renderReciboPago(lastReceiptData);
        alert('Pago semanal guardado correctamente.');
        _setDeudaManualAgente(payload.agente_id || '', lastReceiptData?.nombre || '');
        if (document.getElementById('qrAgenteId').value === String(payload.agente_id)) {
            await verificarAgenteQR();
        }
        await consultarResumenPagoActual(false);
        cargarReporteSemanal();
        cargarRecibosPersistidos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error guardando pago: ' + error.message);
    }
}

function renderReciboPago(data) {
    const container = document.getElementById('reciboPagoContainer');
    if (!container || !data) return;
    container.innerHTML = `
        <div class="card" style="padding:16px;border:1px solid #d8d8d8;border-radius:10px;max-width:720px;">
            <h4 style="margin-bottom:10px;">Comprobante de Pago</h4>
            <p><strong>Agente:</strong> ${data.nombre || ''}</p>
            <p><strong>ID:</strong> ${data.agente_id || ''}</p>
            <p><strong>Teléfono:</strong> ${data.telefono || '-'}</p>
            <p><strong>VoIP:</strong> ${data.numero_voip || '-'}</p>
            <p><strong>Línea:</strong> ${data.linea_numero || '-'}</p>
            <p><strong>Semana:</strong> ${data.semana_inicio || '-'}</p>
            <p><strong>Monto:</strong> $${Number(data.monto || 0).toFixed(2)} MXN</p>
            <p><strong>Abono aplicado:</strong> $${Number(data.abono_registrado || 0).toFixed(2)} MXN</p>
            <p><strong>Saldo acumulado:</strong> $${Number(data.saldo_acumulado || 0).toFixed(2)} MXN</p>
            <p><strong>Fecha de pago:</strong> ${data.fecha_pago ? new Date(data.fecha_pago).toLocaleString() : '-'}</p>
            <p><strong>Estado:</strong> ${data.estado || 'Al Corriente'}</p>
            <p><strong>Token recibo:</strong> ${data.recibo_token || '-'}</p>
            <p><strong>Vence:</strong> ${data.expira_en ? new Date(data.expira_en).toLocaleString() : '-'}</p>
            <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button type="button" class="btn" onclick="imprimirReciboPago()">Imprimir Comprobante</button>
                ${data.recibo_token ? `<button type="button" class="btn btn-secondary" onclick="reimprimirReciboPorToken('${data.recibo_token}')">Recargar desde servidor</button>` : ''}
            </div>
        </div>
    `;
}

async function consultarResumenPagoActual(showAlerts = true) {
    const agenteId = Number(document.getElementById('pagoAgenteId')?.value || 0);
    const semana = document.getElementById('pagoSemana')?.value || '';
    const container = document.getElementById('resumenPagoAgenteContainer');
    if (!container) return;
    if (!agenteId) {
        container.innerHTML = '<p>Ingresa un ID de agente para consultar su resumen.</p>';
        return;
    }
    try {
        const res = await apiClient.getResumenPagoAgente(agenteId, semana);
        const data = res.data || {};
        const deudaBase = Number(data.deuda_base_total || 0);
        const ajusteManual = Number(data.ajuste_manual_deuda || 0);
        container.innerHTML = `
            <div class="card" style="padding:12px;border-radius:8px;">
                <strong>Semana:</strong> ${data.semana_inicio || '-'}<br>
                <strong>Tarifa por línea:</strong> $${Number(data.tarifa_linea_semanal || 0).toFixed(2)} MXN<br>
                <strong>Líneas activas:</strong> ${Number(data.lineas_activas || 0)}<br>
                <strong>Cargo semanal actual:</strong> $${Number(data.cuota_semanal || 0).toFixed(2)} MXN<br>
                <strong>Deuda base (sin ajuste):</strong> $${deudaBase.toFixed(2)} MXN<br>
                <strong>Ajuste manual aplicado:</strong> $${ajusteManual.toFixed(2)} MXN<br>
                <strong>Deuda total:</strong> $${Number(data.deuda_total || 0).toFixed(2)} MXN<br>
                <strong>Total abonado:</strong> $${Number(data.total_abonado || 0).toFixed(2)} MXN<br>
                <strong>Saldo acumulado:</strong> $${Number(data.saldo_acumulado || 0).toFixed(2)} MXN<br>
                <strong>Semanas pendientes:</strong> ${Number(data.semanas_pendientes || 0)}
            </div>
        `;

        const deudaManualSemana = document.getElementById('deudaManualSemana');
        _setDeudaManualAgente(agenteId);
        if (deudaManualSemana && data.semana_inicio) deudaManualSemana.value = String(data.semana_inicio);
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<p style="color:#b00020;">No fue posible obtener el resumen de pagos.</p>';
        if (showAlerts) alert('Error consultando resumen de pagos: ' + error.message);
    }
}

/**
 * Sets both the hidden ID field and the visible search display for the
 * "Control Manual de Deuda" agent picker.
 * @param {number|string} id      — numeric agent ID
 * @param {string}        [name]  — display name; defaults to "ID: {id}"
 */
function _setDeudaManualAgente(id, name) {
    const hiddenId = document.getElementById('deudaManualAgenteId');
    const searchEl = document.getElementById('deudaManualAgenteSearch');
    const displayName = name || `ID: ${id}`;
    if (hiddenId) hiddenId.value = String(id || '');
    if (searchEl) searchEl.value = displayName;
}

function renderDeudaManualResultado(data, label = 'Consulta') {
    const el = document.getElementById('deudaManualResult');
    if (!el) return;
    const deudaBase = Number(data?.deuda_base_total || 0);
    const ajuste = Number(data?.ajuste_manual_deuda || 0);
    const deudaTotal = Number(data?.deuda_total || 0);
    const abonado = Number(data?.total_abonado || 0);
    const saldo = Number(data?.saldo_acumulado || 0);
    el.innerHTML = `
        <div class="card" style="padding:12px;border-radius:8px;">
            <strong>${escapeHtml(label)}:</strong><br>
            <strong>Semana:</strong> ${escapeHtml(String(data?.semana_inicio || '-'))}<br>
            <strong>Deuda base:</strong> $${deudaBase.toFixed(2)} MXN<br>
            <strong>Ajuste manual:</strong> $${ajuste.toFixed(2)} MXN<br>
            <strong>Deuda total:</strong> $${deudaTotal.toFixed(2)} MXN<br>
            <strong>Total abonado:</strong> $${abonado.toFixed(2)} MXN<br>
            <strong>Saldo acumulado:</strong> $${saldo.toFixed(2)} MXN
        </div>
    `;
}

async function consultarDeudaManualAgente(showAlerts = true) {
    const agenteId = Number(document.getElementById('deudaManualAgenteId')?.value || 0);
    const semana = document.getElementById('deudaManualSemana')?.value || '';
    if (!agenteId) {
        if (showAlerts) alert('Ingresa el ID del agente para consultar deuda manual.');
        return;
    }
    try {
        const res = await apiClient.getDeudaManualAgente(agenteId, semana);
        renderDeudaManualResultado(res.data || {}, `Agente ${res.agente?.nombre || agenteId}`);
    } catch (error) {
        console.error('Error:', error);
        if (showAlerts) alert('Error consultando deuda manual: ' + error.message);
    }
}

async function aplicarDeudaManualAgente() {
    const agenteId = Number(document.getElementById('deudaManualAgenteId')?.value || 0);
    const semana = document.getElementById('deudaManualSemana')?.value || '';
    const modo = String(document.getElementById('deudaManualModo')?.value || 'saldo_objetivo');
    const montoRaw = document.getElementById('deudaManualMonto')?.value || '';
    const monto = Number(montoRaw);

    if (!agenteId) {
        alert('Ingresa el ID del agente para aplicar ajuste manual.');
        return;
    }
    if (!Number.isFinite(monto)) {
        alert('Ingresa un monto válido para aplicar ajuste manual.');
        return;
    }
    if (modo === 'saldo_objetivo' && monto < 0) {
        alert('El saldo objetivo no puede ser negativo.');
        return;
    }

    try {
        const payload = { modo, monto };
        if (semana) payload.semana = semana;
        const res = await apiClient.setDeudaManualAgente(agenteId, payload);
        renderDeudaManualResultado(res.data || {}, 'Ajuste aplicado');
        alert('Ajuste manual de deuda guardado correctamente.');

        const pagoAgente = document.getElementById('pagoAgenteId');
        if (pagoAgente && Number(pagoAgente.value || 0) === agenteId) {
            await consultarResumenPagoActual(false);
        }
        if (document.getElementById('qrAgenteId')?.value === String(agenteId)) {
            await verificarAgenteQR();
        }
        await cargarReporteSemanal();
    } catch (error) {
        console.error('Error:', error);
        alert('Error aplicando ajuste manual de deuda: ' + error.message);
    }
}

async function limpiarDeudaManualAgente() {
    const agenteId = Number(document.getElementById('deudaManualAgenteId')?.value || 0);
    const semana = document.getElementById('deudaManualSemana')?.value || '';
    if (!agenteId) {
        alert('Ingresa el ID del agente para limpiar ajuste manual.');
        return;
    }
    if (!(await showAppConfirm('¿Quitar ajuste manual de deuda para este agente (monto = 0)?', { title: 'Limpiar ajuste', tone: 'warning' }))) return;
    try {
        const payload = { modo: 'ajuste', monto: 0 };
        if (semana) payload.semana = semana;
        const res = await apiClient.setDeudaManualAgente(agenteId, payload);
        renderDeudaManualResultado(res.data || {}, 'Ajuste limpiado');
        alert('Ajuste manual limpiado.');
        const pagoAgente = document.getElementById('pagoAgenteId');
        if (pagoAgente && Number(pagoAgente.value || 0) === agenteId) {
            await consultarResumenPagoActual(false);
        }
        await cargarReporteSemanal();
    } catch (error) {
        console.error('Error:', error);
        alert('Error limpiando ajuste manual: ' + error.message);
    }
}

async function reimprimirReciboPorToken(token) {
    try {
        const res = await apiClient.getReciboPago(token);
        const data = res.data || {};
        lastReceiptData = {
            agente_id: data.agente_id,
            nombre: data.agente_nombre || `Agente ${data.agente_id || ''}`,
            telefono: data.telefono || '',
            numero_voip: data.numero_voip || '',
            linea_numero: data.linea_numero || null,
            semana_inicio: data.semana_inicio,
            monto: Number(data.monto || 0),
            abono_registrado: Number(data.abono_aplicado ?? data.monto ?? 0),
            saldo_acumulado: Number(data.saldo_acumulado ?? 0),
            deuda_total: Number(data.deuda_total ?? 0),
            total_abonado: Number(data.total_abonado ?? 0),
            fecha_pago: data.fecha_pago,
            estado: data.estado_pago || (data.pagado ? 'Al Corriente' : (Number(data.monto || 0) > 0 ? 'Abonado' : 'Pendiente de Pago')),
            pago_id: data.pago_id || null,
            pagado: !!data.pagado,
            recibo_token: data.token || token,
            expira_en: data.expira_en,
        };
        renderReciboPago(lastReceiptData);
        imprimirReciboPago();
        cargarRecibosPersistidos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando recibo: ' + error.message);
    }
}

async function _pedirCamposVisiblesRecibo(defaultFields) {
    const defaultCsv = defaultFields.join(',');
    const raw = await showAppPrompt(
        'Campos visibles del recibo (separados por coma).\nOpciones: agente,id,telefono,voip,linea,semana,monto,abono,saldo,deuda,total_abonado,fecha,estado,token,vence',
        { title: 'Configurar recibo', placeholder: defaultCsv }
    );
    if (raw === null) return null;
    const csv = String(raw || '').trim() || defaultCsv;
    const chosen = new Set(csv.split(',').map((x) => x.trim().toLowerCase()).filter(Boolean));
    return chosen.size ? chosen : new Set(defaultFields);
}

async function _compararDatosRecibo(data) {
    const payload = { ...data };
    const agenteId = Number(payload.agente_id || 0);
    const semana = String(payload.semana_inicio || '').trim();
    if (!agenteId || !semana) return payload;

    try {
        const res = await apiClient.getResumenPagoAgente(agenteId, semana);
        const d = res?.data || {};
        payload.saldo_acumulado = Number(d.saldo_acumulado ?? payload.saldo_acumulado ?? 0);
        payload.deuda_total = Number(d.deuda_total ?? payload.deuda_total ?? 0);
        payload.total_abonado = Number(d.total_abonado ?? payload.total_abonado ?? 0);
        if (!Number.isFinite(Number(payload.abono_registrado))) {
            payload.abono_registrado = Number(payload.monto || 0);
        }
    } catch (_) {
        // Si no hay resumen disponible, se imprime con datos del recibo persistido.
    }
    return payload;
}

async function imprimirReciboPago() {
    if (!lastReceiptData) {
        alert('No hay comprobante para imprimir.');
        return;
    }

    const enriched = await _compararDatosRecibo(lastReceiptData);
    const visible = await _pedirCamposVisiblesRecibo([
        'agente', 'id', 'telefono', 'voip', 'linea', 'semana', 'monto', 'abono', 'saldo', 'deuda', 'total_abonado', 'fecha', 'estado', 'token', 'vence'
    ]);
    if (!visible) return;

    const line = (key, label, value) => visible.has(key) ? `<p><strong>${label}:</strong> ${value}</p>` : '';
    const receiptHtml = `
        <html>
        <head>
            <title>Comprobante de Pago</title>
            <style>
                body { font-family: Segoe UI, Arial, sans-serif; padding: 24px; color: #182230; }
                .receipt { border: 1px solid #d8d8d8; border-radius: 10px; padding: 20px; max-width: 700px; }
                h1 { margin-top: 0; color: #094955; }
                p { margin: 8px 0; }
            </style>
        </head>
        <body>
            <div class="receipt">
                <h1>Comprobante de Pago</h1>
                ${line('agente', 'Agente', enriched.nombre || '')}
                ${line('id', 'ID', enriched.agente_id || '')}
                ${line('telefono', 'Teléfono', enriched.telefono || '-')}
                ${line('voip', 'VoIP', enriched.numero_voip || '-')}
                ${line('linea', 'Línea', enriched.linea_numero || '-')}
                ${line('semana', 'Semana', enriched.semana_inicio || '-')}
                ${line('monto', 'Monto', `$${Number(enriched.monto || 0).toFixed(2)} MXN`)}
                ${line('abono', 'Abono aplicado', `$${Number(enriched.abono_registrado || 0).toFixed(2)} MXN`)}
                ${line('saldo', 'Saldo acumulado', `$${Number(enriched.saldo_acumulado || 0).toFixed(2)} MXN`)}
                ${line('deuda', 'Deuda total', `$${Number(enriched.deuda_total || 0).toFixed(2)} MXN`)}
                ${line('total_abonado', 'Total abonado', `$${Number(enriched.total_abonado || 0).toFixed(2)} MXN`)}
                ${line('fecha', 'Fecha de pago', enriched.fecha_pago ? new Date(enriched.fecha_pago).toLocaleString() : '-')}
                ${line('estado', 'Estado', enriched.estado || 'Al Corriente')}
                ${line('token', 'Token', enriched.recibo_token || '-')}
                ${line('vence', 'Vence', enriched.expira_en ? new Date(enriched.expira_en).toLocaleString() : '-')}
            </div>
        </body>
        </html>
    `;
    const w = window.open('', '_blank', 'width=900,height=700');
    if (!w) {
        alert('No se pudo abrir la ventana de impresión.');
        return;
    }
    w.document.open();
    w.document.write(receiptHtml);
    w.document.close();
    w.focus();
    w.print();
}

async function imprimirRecibosSeleccionados() {
    const checks = Array.from(document.querySelectorAll('.recibo-select-item:checked'));
    if (!checks.length) {
        alert('Selecciona al menos un recibo para imprimir.');
        return;
    }

    const rows = checks
        .map((c) => {
            try {
                return JSON.parse(decodeURIComponent(c.dataset.recibo || ''));
            } catch (_) {
                return null;
            }
        })
        .filter(Boolean);

    if (!rows.length) {
        alert('No fue posible preparar los recibos seleccionados.');
        return;
    }

    const visible = await _pedirCamposVisiblesRecibo([
        'agente', 'id', 'linea', 'semana', 'monto', 'abono', 'saldo', 'deuda', 'total_abonado', 'fecha', 'estado', 'token'
    ]);
    if (!visible) return;

    const porHoja = Number(document.getElementById('recibosPorHojaSelect')?.value || 3);
    const perPage = [2, 3, 4].includes(porHoja) ? porHoja : 3;
    const columns = perPage >= 4 ? 2 : 1;
    const minCardHeight = perPage === 2 ? '122mm' : (perPage === 3 ? '82mm' : '58mm');

    const cards = rows.map((r) => {
        const estado = r.pagado ? 'Al Corriente' : (Number(r.monto || 0) > 0 ? 'Abonado' : 'Pendiente de Pago');
        const line = (key, label, value) => visible.has(key) ? `<p><strong>${label}:</strong> ${value}</p>` : '';
        return `
            <article class="recibo-card">
                <h3>Comprobante de Pago</h3>
                ${line('agente', 'Agente', `${escapeHtml(r.agente_nombre || '-')} (ID ${escapeHtml(String(r.agente_id || '-'))})`)}
                ${line('id', 'ID', escapeHtml(String(r.agente_id || '-')))}
                ${line('linea', 'Línea', escapeHtml(r.linea_numero || '-'))}
                ${line('semana', 'Semana', escapeHtml(r.semana_inicio || '-'))}
                ${line('monto', 'Monto', `$${Number(r.monto || 0).toFixed(2)} MXN`)}
                ${line('abono', 'Abono aplicado', `$${Number(r.abono_aplicado ?? r.monto ?? 0).toFixed(2)} MXN`)}
                ${line('saldo', 'Saldo acumulado', `$${Number(r.saldo_acumulado ?? 0).toFixed(2)} MXN`)}
                ${line('deuda', 'Deuda total', `$${Number(r.deuda_total ?? 0).toFixed(2)} MXN`)}
                ${line('total_abonado', 'Total abonado', `$${Number(r.total_abonado ?? 0).toFixed(2)} MXN`)}
                ${line('estado', 'Estado', estado)}
                ${line('fecha', 'Fecha pago', r.fecha_pago ? new Date(r.fecha_pago).toLocaleString() : '-')}
                ${line('token', 'Token', escapeHtml(r.token || '-'))}
            </article>
        `;
    });

    const pages = [];
    for (let i = 0; i < cards.length; i += perPage) {
        const chunk = cards.slice(i, i + perPage).join('');
        pages.push(`<section class="print-page"><section class="grid">${chunk}</section></section>`);
    }

    const printHtml = `
        <html>
        <head>
            <title>Recibos de Pago</title>
            <style>
                @page { size: letter; margin: 10mm; }
                body { font-family: Segoe UI, Arial, sans-serif; margin: 0; }
                .print-page { page-break-after: always; }
                .print-page:last-child { page-break-after: auto; }
                .grid { display: grid; grid-template-columns: repeat(${columns}, 1fr); gap: 8mm; }
                .recibo-card { border: 1px solid #cfd8e3; border-radius: 8px; padding: 8mm; break-inside: avoid; min-height: ${minCardHeight}; }
                .recibo-card h3 { margin: 0 0 8px 0; color: #0c4f84; font-size: 14pt; }
                .recibo-card p { margin: 4px 0; font-size: 10pt; }
            </style>
        </head>
        <body>
            ${pages.join('')}
        </body>
        </html>
    `;

    const w = window.open('', '_blank', 'width=1000,height=760');
    if (!w) {
        alert('No se pudo abrir la ventana de impresión.');
        return;
    }
    w.document.open();
    w.document.write(printHtml);
    w.document.close();
    w.focus();
    w.print();
}

async function editarPagoDesdeRecibo(pagoId, montoActual = 0) {
    if (!canAdmin()) {
        alert('Solo administradores pueden editar pagos.');
        return;
    }
    const montoRaw = await showAppPrompt(
        `Monto actual: $${Number(montoActual || 0).toFixed(2)} MXN\nNuevo monto del pago:`,
        { title: 'Editar pago', placeholder: String(Number(montoActual || 0).toFixed(2)), type: 'number' }
    );
    if (montoRaw === null) return;
    const monto = Number(montoRaw);
    if (!Number.isFinite(monto) || monto < 0) {
        alert('Monto inválido.');
        return;
    }

    const observaciones = await showAppPrompt('Observaciones (opcional):', { title: 'Editar recibo/pago', placeholder: 'Opcional' }) || null;
    try {
        const res = await apiClient.editarPagoSemanalAdmin(pagoId, { monto, observaciones });
        const data = res?.data || {};
        const recibo = data.recibo || {};
        if (recibo.token) {
            await reimprimirReciboPorToken(recibo.token);
        } else {
            await cargarRecibosPersistidos();
        }
        alert('Pago y recibo actualizados correctamente.');
    } catch (error) {
        console.error('Error:', error);
        alert('No fue posible editar el recibo/pago: ' + error.message);
    }
}

async function revertirPagoDesdeRecibo(pagoId, agenteId = 0) {
    if (!canAdmin()) {
        alert('Solo administradores pueden revertir pagos.');
        return;
    }

    const confirmar = window.confirm('Esta acción revertirá el pago y lo dejará en $0.00 para esa semana. ¿Deseas continuar?');
    if (!confirmar) return;

    const motivo = await showAppPrompt('Motivo de reversa (opcional):', {
        title: 'Revertir pago',
        placeholder: 'Ej: pago de prueba, captura errónea'
    });
    if (motivo === null) return;

    try {
        const res = await apiClient.revertirPagoSemanalAdmin(pagoId, { motivo: (motivo || '').trim() });
        const data = res?.data || {};
        const recibo = data.recibo || {};
        alert(`Pago revertido correctamente. Monto revertido: $${Number(data.monto_revertido || 0).toFixed(2)} MXN`);
        await cargarReporteSemanal();
        await cargarRecibosPersistidos();
        if (recibo.token) {
            await reimprimirReciboPorToken(recibo.token);
        }
        if (Number(document.getElementById('pagoAgenteId')?.value || 0) === Number(agenteId || 0)) {
            await consultarResumenPagoActual(false);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('No fue posible revertir el pago: ' + error.message);
    }
}

function generarReciboDesdeReporte(index) {
    const row = currentWeeklyReportRows[index];
    if (!row) return;
    lastReceiptData = {
        agente_id: row.agente_id,
        nombre: row.nombre,
        telefono: row.telefono,
        numero_voip: row.numero_voip || '',
        linea_numero: row.extension_numero || null,
        semana_inicio: document.getElementById('reporteSemanaInput')?.value || mondayISO(),
        monto: row.monto_pagado || row.cuota || 0,
        fecha_pago: row.fecha_pago,
        estado: row.pagado ? 'PAGADO' : 'PENDIENTE'
    };
    renderReciboPago(lastReceiptData);
}

async function cargarCuotaSemanal() {
    try {
        const res = await apiClient.getCuotaSemanal();
        const cuota = Number(res.cuota_semanal || 300);
        const input = document.getElementById('cuotaSemanalInput');
        if (input) {
            input.value = cuota;
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function guardarCuotaSemanal(e) {
    e.preventDefault();
    const input = document.getElementById('cuotaSemanalInput');
    const cuota = Number(input.value);
    if (!Number.isFinite(cuota) || cuota <= 0) {
        alert('Ingresa una cuota válida mayor a 0.');
        return;
    }

    try {
        await apiClient.updateCuotaSemanal(cuota);
        alert('Cuota semanal actualizada.');
        cargarReporteSemanal();
    } catch (error) {
        console.error('Error:', error);
        alert('Error actualizando cuota: ' + error.message);
    }
}

async function cargarReporteSemanal() {
    const semana = document.getElementById('reporteSemanaInput')?.value || '';
    const agente = document.getElementById('reporteAgenteInput')?.value.trim() || '';
    try {
        const reporte = await apiClient.getReporteSemanal(semana, agente);
        const resumen = document.getElementById('reporteSemanalResumen');
        const container = document.getElementById('reporteSemanalContainer');
        const tarifa = Number(reporte.cuota_semanal || 300).toFixed(2);
        const tot = reporte.totales || { agentes: 0, pagados: 0, pendientes: 0 };

        const saldoGlobal = Number(tot.saldo_global || 0);
        const claseSaldo = saldoGlobal > 0.009 ? 'color:#b00020;' : 'color:#0b6b2f;';
        const discrepancias = Array.isArray(reporte.discrepancias) ? reporte.discrepancias : [];
        const discrepanciasHtml = discrepancias.length
            ? `<div style="margin-top:8px;padding:8px;border:1px solid #f0c9c9;border-radius:6px;background:#fff5f5;">
                <strong>Discrepancias detectadas (${discrepancias.length}):</strong>
                <ul style="margin:6px 0 0 18px;">
                    ${discrepancias.map(d => `<li>${escapeHtml(d.codigo || 'SIN_CODIGO')} - ${escapeHtml(d.mensaje || '')}</li>`).join('')}
                </ul>
            </div>`
            : '<div style="margin-top:8px;color:#0b6b2f;"><strong>Conciliación:</strong> Sin discrepancias relevantes.</div>';

        const snapshot = reporte.snapshot || null;
        const snapshotHtml = snapshot?.id
            ? `<div style="margin-top:6px;font-size:12px;color:#444;">Snapshot BD #${snapshot.id} (${snapshot.reutilizado ? 'reutilizado' : 'nuevo'}) - ${snapshot.generado_en || '-'}</div>`
            : '';

        resumen.innerHTML = `
            <div class="card" style="padding:12px;border:1px solid #d8d8d8;border-radius:8px;">
                <strong>Semana:</strong> ${reporte.semana_inicio}<br>
                <strong>Tarifa por línea vigente:</strong> $${tarifa} MXN<br>
                <strong>Agentes:</strong> ${tot.agentes} |
                <strong>Pagados:</strong> ${tot.pagados} |
                <strong>Pendientes:</strong> ${tot.pendientes}<br>
                <strong>Deuda global:</strong> $${Number(tot.deuda_total_global || 0).toFixed(2)} MXN |
                <strong>Total abonado:</strong> $${Number(tot.total_abonado_global || 0).toFixed(2)} MXN |
                <strong style="${claseSaldo}">Saldo global:</strong> <span style="${claseSaldo}">$${saldoGlobal.toFixed(2)} MXN</span><br>
                <strong>Semana (reporte):</strong> $${Number(tot.monto_semana_reportado || 0).toFixed(2)} MXN |
                <strong>Semana (ledger):</strong> $${Number(tot.monto_semana_ledger || 0).toFixed(2)} MXN |
                <strong>Diferencia:</strong> $${Number(tot.discrepancia_semana || 0).toFixed(2)} MXN
                ${discrepanciasHtml}
                ${snapshotHtml}
            </div>
        `;

        await cargarTotalesCobranzaReporte(false);

        const filas = reporte.data || [];
        currentWeeklyReportRows = filas;
        if (filas.length === 0) {
            container.innerHTML = '<p>No hay agentes activos para esta semana.</p>';
        } else {
            const adminMode = canAdmin();
            let html = '<table class="data-table"><thead><tr>';
            html += '<th>ID</th><th>Nombre</th><th>Telefono</th><th>Líneas</th><th>Tarifa x Línea</th><th>Pagado</th><th>Monto Semana</th><th>Saldo Semana</th><th>Saldo Acumulado</th><th>Alerta</th>';
            html += '</tr></thead><tbody>';
            filas.forEach((f, index) => {
                html += `<tr>
                    <td>${f.agente_id}</td>
                    <td>${f.nombre || ''}</td>
                    <td>${f.telefono || ''}</td>
                    <td>${Number(f.lineas_activas || 0)}</td>
                    <td>$${Number(f.tarifa_linea_semanal || 0).toFixed(2)}</td>
                    <td>${f.pagado ? 'SI' : 'NO'}</td>
                    <td>$${Number(f.monto_pagado || 0).toFixed(2)}</td>
                    <td>$${Number(f.saldo || 0).toFixed(2)}</td>
                    <td>$${Number(f.saldo_acumulado || 0).toFixed(2)}</td>
                    <td>${f.alerta_emitida ? (f.alerta_atendida ? 'Atendida' : 'Pendiente') : 'Sin alerta'}<br><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px"><button onclick="generarQrIndividual(${f.agente_id})" class="btn btn-small btn-secondary">Ver QR</button><button onclick="generarReciboDesdeReporte(${index})" class="btn btn-small">Recibo</button>${adminMode && f.pago_id ? `<button onclick="editarPagoAdminDesdeReporte(${f.pago_id}, ${f.agente_id}, ${Number(f.monto_pagado || 0)})" class="btn btn-small btn-secondary">Editar Pago</button><button onclick="revertirPagoDesdeRecibo(${f.pago_id}, ${f.agente_id})" class="btn btn-small" style="background:#8b1d1d;color:#fff;">Revertir</button>` : ''}</div></td>
                </tr>`;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        }

        cargarAlertasPago();
        cargarRespaldos();
        cargarVistaAgentesPago();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando reporte semanal: ' + error.message);
    }
}

async function cargarTotalesCobranzaReporte(showAlerts = true) {
    const container = document.getElementById('reporteCobranzaTotales');
    if (!container) return;

    const fecha = document.getElementById('reporteCobroFechaInput')?.value || todayISO();
    const semana = document.getElementById('reporteSemanaInput')?.value || mondayISO();

    try {
        const res = await apiClient.getTotalesCobranza(fecha, semana);
        const data = res?.data || {};
        const serie = Array.isArray(data.serie_diaria_semana) ? data.serie_diaria_semana : [];
        const serieHtml = serie.map((row) => (
            `<tr><td>${row.fecha || '-'}</td><td>${Number(row.pagos || 0)}</td><td>$${Number(row.monto || 0).toFixed(2)} MXN</td></tr>`
        )).join('');

        container.innerHTML = `
            <div class="card" style="padding:12px;border:1px solid #d8d8d8;border-radius:8px;">
                <strong>Cobranza del día (${data.fecha || fecha}):</strong> $${Number(data.total_pagado_dia || 0).toFixed(2)} MXN<br>
                <strong>Pagos del día:</strong> ${Number(data.pagos_registrados_dia || 0)} |
                <strong>Agentes cobrados:</strong> ${Number(data.agentes_cobrados_dia || 0)}<br>
                <strong>Acumulado semanal (${data.semana_inicio || semana} a ${data.semana_fin || '-'}):</strong> $${Number(data.total_pagado_semana || 0).toFixed(2)} MXN<br>
                <strong>Pagos semana:</strong> ${Number(data.pagos_registrados_semana || 0)} |
                <strong>Agentes cobrados semana:</strong> ${Number(data.agentes_cobrados_semana || 0)}
            </div>
            <div class="table-responsive" style="margin-top:10px;">
                <table class="data-table">
                    <thead><tr><th>Fecha</th><th>Pagos</th><th>Total</th></tr></thead>
                    <tbody>${serieHtml || '<tr><td colspan="3">Sin pagos en la semana seleccionada</td></tr>'}</tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<p style="color:#b00020;">No fue posible cargar los totales de cobranza.</p>';
        if (showAlerts) {
            alert('Error cargando totales de cobranza: ' + error.message);
        }
    }
}

async function editarPagoAdminDesdeReporte(pagoId, agenteId, montoActual = 0) {
    if (!canAdmin()) {
        alert('Solo administradores pueden editar pagos manualmente.');
        return;
    }
    const montoRaw = await showAppPrompt(
        `Monto actual: $${Number(montoActual || 0).toFixed(2)} MXN\nNuevo monto semanal:`,
        { title: 'Editar pago', placeholder: String(Number(montoActual || 0).toFixed(2)), type: 'number' }
    );
    if (montoRaw === null) return;
    const monto = Number(montoRaw);
    if (!Number.isFinite(monto) || monto < 0) {
        alert('Monto inválido.');
        return;
    }
    const observaciones = await showAppPrompt('Observaciones (opcional):', { title: 'Observaciones', placeholder: 'Deja en blanco si no aplica' }) || null;
    try {
        await apiClient.editarPagoSemanalAdmin(pagoId, { monto, observaciones });
        alert('Pago actualizado correctamente.');
        await cargarReporteSemanal();
        if (Number(document.getElementById('pagoAgenteId')?.value || 0) === Number(agenteId)) {
            await consultarResumenPagoActual(false);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('No fue posible editar el pago: ' + error.message);
    }
}

async function cargarVistaAgentesPago() {
    const semana = document.getElementById('reporteSemanaInput')?.value || '';
    const search = document.getElementById('estadoAgenteSearch')?.value.trim() || '';
    const container = document.getElementById('agentesEstadoPagoContainer');
    if (!container) return;

    try {
        const res = await apiClient.getAgentesEstadoPago(semana, search);
        const rows = res.data || [];
        if (!rows.length) {
            container.innerHTML = '<p>No hay resultados para la vista operativa.</p>';
            return;
        }

        let html = '<table class="data-table"><thead><tr>';
        html += '<th>ID</th><th>Agente</th><th>Estado Línea</th><th>Extensión</th><th>Semana</th><th>Estado Pago</th><th>Monto</th><th>Fecha Pago</th>';
        html += '</tr></thead><tbody>';
        rows.forEach(row => {
            const lineaEstado = (row.linea_estado || (row.extension_numero ? 'ASIGNADA' : 'SIN_LINEA')).replace('_', ' ');
            const saldoAcumulado = Number(row.saldo_acumulado ?? 0);
            const pendiente = saldoAcumulado > 0.009 || String(row.estado_pago || '').toLowerCase().includes('pendiente');
            const estadoPago = pendiente
                ? (saldoAcumulado > 0.009 ? `Debe $${saldoAcumulado.toFixed(2)}` : 'Pendiente de Pago')
                : 'Al Corriente';
            html += `<tr>
                <td>${row.agente_id}</td>
                <td>${row.nombre || ''}</td>
                <td>${lineaEstado}</td>
                <td>${row.extension_numero || '-'}</td>
                <td>${row.semana_inicio || '-'}</td>
                <td><span class="payment-pill ${pendiente ? 'unpaid' : 'paid'}">${estadoPago}</span></td>
                <td>$${Number(row.monto || 0).toFixed(2)}</td>
                <td>${row.fecha_pago ? new Date(row.fecha_pago).toLocaleString() : '-'}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<p>Error cargando vista operativa: ${escapeHtml(error.message)}</p>`;
    }
}

async function cargarRecibosPersistidos() {
    const container = document.getElementById('recibosHistoricosContainer');
    if (!container) return;
    const agenteIdRaw = document.getElementById('recibosAgenteFiltro')?.value || '';
    const agenteId = Number(agenteIdRaw);

    try {
        const res = await apiClient.getRecibosPago(Number.isFinite(agenteId) && agenteId > 0 ? agenteId : '');
        const rows = res.data || [];
        if (!rows.length) {
            container.innerHTML = '<p>No hay recibos vigentes guardados.</p>';
            return;
        }

        let html = '<h4>Recibos guardados</h4>';
        html += '<div style="margin:8px 0 12px;display:flex;gap:8px;flex-wrap:wrap;">';
        html += '<label for="recibosPorHojaSelect" style="display:flex;align-items:center;gap:6px;">';
        html += '<span>Recibos por hoja</span>';
        html += '<select id="recibosPorHojaSelect" class="form-control" style="width:85px;">';
        html += '<option value="2">2</option>';
        html += '<option value="3" selected>3</option>';
        html += '<option value="4">4</option>';
        html += '</select>';
        html += '</label>';
        html += '<button type="button" class="btn" onclick="imprimirRecibosSeleccionados()">Imprimir seleccionados (varios por hoja)</button>';
        html += '</div>';
        html += '<table class="data-table"><thead><tr>';
        html += '<th>Sel</th><th>Agente</th><th>Línea</th><th>Semana</th><th>Monto</th><th>Estado</th><th>Vence</th><th>Acción</th>';
        html += '</tr></thead><tbody>';
        rows.forEach(row => {
            const serialized = encodeURIComponent(JSON.stringify(row));
            const estadoPago = row.estado_pago || (row.pagado ? 'Al Corriente' : (Number(row.monto || 0) > 0 ? 'Abonado' : 'Pendiente'));
            html += `<tr>
                <td><input type="checkbox" class="recibo-select-item" data-recibo="${serialized}"></td>
                <td>${row.agente_nombre || '-'} (ID ${row.agente_id || '-'})</td>
                <td>${row.linea_numero || '-'}</td>
                <td>${row.semana_inicio || '-'}</td>
                <td>$${Number(row.monto || 0).toFixed(2)}</td>
                <td>${estadoPago}</td>
                <td>${row.expira_en ? new Date(row.expira_en).toLocaleString() : '-'}</td>
                <td style="display:flex;gap:6px;flex-wrap:wrap;">
                    <button type="button" class="btn btn-small" onclick="reimprimirReciboPorToken('${row.token}')">Reimprimir</button>
                    ${canAdmin() && row.pago_id ? `<button type="button" class="btn btn-small btn-secondary" onclick="editarPagoDesdeRecibo(${row.pago_id}, ${Number(row.monto || 0)})">Editar</button>` : ''}
                    ${canAdmin() && row.pago_id ? `<button type="button" class="btn btn-small" style="background:#8b1d1d;color:#fff;" onclick="revertirPagoDesdeRecibo(${row.pago_id}, ${Number(row.agente_id || 0)})">Revertir</button>` : ''}
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<p>Error cargando recibos: ${escapeHtml(error.message)}</p>`;
    }
}

async function cargarAlertasPago() {
    const semana = document.getElementById('reporteSemanaInput')?.value || '';
    const container = document.getElementById('alertasPagoContainer');

    try {
        const res = await apiClient.getAlertasPago(semana, true);
        const alertas = res.data || [];
        if (alertas.length === 0) {
            container.innerHTML = '<p>No hay alertas pendientes.</p>';
            return;
        }

        let html = '<h4>Alertas de pago pendientes</h4><table class="data-table"><thead><tr>';
        html += '<th>ID Alerta</th><th>Agente</th><th>Semana</th><th>Fecha Alerta</th><th>Motivo</th>';
        html += '</tr></thead><tbody>';
        alertas.forEach(a => {
            html += `<tr>
                <td>${a.id}</td>
                <td>${a.agente_id}</td>
                <td>${a.semana_inicio}</td>
                <td>${a.fecha_alerta ? new Date(a.fecha_alerta).toLocaleString() : ''}</td>
                <td>${a.motivo || ''}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<p>Error cargando alertas.</p>';
    }
}

async function procesarAlertasPagoManual() {
    try {
        const res = await apiClient.procesarAlertasPago();
        const data = res.data || {};
        alert(`Alertas procesadas. Nuevas alertas: ${data.alertas_creadas || 0}`);
        cargarReporteSemanal();
    } catch (error) {
        console.error('Error:', error);
        alert('Error procesando alertas: ' + error.message);
    }
}

async function generarBackupManual() {
    try {
        const backupDir = (document.getElementById('backupDirInput')?.value || currentBackupDir || '').trim();
        const res = await apiClient.generarBackupManual(backupDir);
        const data = res.data || {};
        alert(`Respaldo generado: ${data.file || 'OK'}`);
        if (backupDir) {
            currentBackupDir = backupDir;
        }
        await cargarConfiguracionRespaldos(false);
        cargarRespaldos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error generando respaldo: ' + error.message);
    }
}

async function cargarConfiguracionRespaldos(showErrors = true) {
    const input = document.getElementById('backupDirInput');
    const hint = document.getElementById('backupDirHint');
    if (!input || !hint) return;

    try {
        const res = await apiClient.getBackupConfig();
        const data = res.data || {};
        currentBackupDir = String(data.backup_dir || '').trim();
        input.value = currentBackupDir;
        hint.textContent = `Ruta activa: ${currentBackupDir || 'No configurada'}${Number.isFinite(Number(data.files)) ? ` | archivos detectados: ${data.files}` : ''}`;
    } catch (error) {
        console.error('Error cargando configuración de respaldos:', error);
        if (showErrors) {
            alert('Error cargando configuración de respaldos: ' + error.message);
        }
    }
}

async function guardarRutaRespaldos() {
    const input = document.getElementById('backupDirInput');
    const backupDir = (input?.value || '').trim();
    if (!backupDir) {
        alert('Ingresa una ruta válida para respaldos.');
        return;
    }

    try {
        await apiClient.updateBackupConfig(backupDir, true);
        currentBackupDir = backupDir;
        alert('Ruta de respaldos guardada correctamente.');
        await cargarConfiguracionRespaldos(false);
        await cargarRespaldos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error guardando la ruta de respaldos: ' + error.message);
    }
}

async function cargarRespaldos() {
    const container = document.getElementById('backupsContainer');
    if (!container) return;
    try {
        const res = await apiClient.listBackups();
        const items = res.data || [];
        if (!items.length) {
            container.innerHTML = '<p>No hay respaldos disponibles.</p>';
            return;
        }

        let html = '<h4>Respaldos disponibles</h4><table class="data-table"><thead><tr>';
        html += '<th>Archivo</th><th>Tamaño</th><th>Fecha</th><th>Acciones</th></tr></thead><tbody>';
        items.forEach(item => {
            html += `<tr>
                <td>${item.filename}</td>
                <td>${Math.round((item.size || 0) / 1024)} KB</td>
                <td>${item.modified ? new Date(item.modified).toLocaleString() : ''}</td>
                <td><button class="btn btn-small btn-danger" onclick="restaurarRespaldo('${item.filename}')">Restaurar</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<p>Error cargando respaldos.</p>';
    }
}

async function restaurarRespaldo(filename) {
    if (!(await showAppConfirm(`¿Restaurar el respaldo ${filename}? Esta acción reemplazará la base actual.`, { title: 'Restaurar respaldo', tone: 'warning', acceptText: 'Restaurar' }))) return;
    if (!(await showAppConfirm('Confirma nuevamente. Se hará un respaldo de rescate antes de continuar.', { title: 'Segunda confirmación', tone: 'warning', acceptText: 'Sí, restaurar' }))) return;
    try {
        const res = await apiClient.restoreBackup(filename);
        alert(`Respaldo restaurado: ${res?.data?.file || filename}`);
    } catch (error) {
        console.error('Error:', error);
        alert('Error restaurando respaldo: ' + error.message);
    }
}

async function generarQRVerificacion(e) {
    e.preventDefault();
    const agenteId = document.getElementById('qrAgenteId').value;
    if (!agenteId) {
        alert('Ingresa ID del agente.');
        return;
    }

    try {
        const result = await apiClient.getQrAgente(agenteId);
        const data = result.data || {};
        if (!data.public_url) {
            throw new Error('No se pudo generar URL de verificación estática');
        }
        renderSimpleQR(data.public_url);
        alert(`QR estático generado para el agente ${agenteId}. El servidor validará la línea y el estado actual al escanear.`);
    } catch (error) {
        console.error('Error:', error);
        alert('Error generando QR de verificación: ' + error.message);
    }
}

// === AUDITORÍA ===
async function cargarAuditoria() {
    return cargarAuditoriaInterna(true);
}

async function cargarAuditoriaInterna(showErrors = true) {
    try {
        const data = await fetchJson(`${API_URL}/auditoria/`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        const container = document.getElementById('auditoriaContainer');
        if (!container) return;

        if (data.length === 0) {
            container.innerHTML = '<p>No hay registros de auditoría</p>';
            return;
        }

        let html = '<table class="data-table"><thead><tr>';
        html += '<th>Fecha</th><th>Usuario</th><th>Acción</th><th>IP</th></tr></thead><tbody>';

        data.forEach(registro => {
            html += `<tr>
                <td>${new Date(registro.fecha).toLocaleString()}</td>
                <td>${registro.usuario_id}</td>
                <td>${registro.tipo_accion}</td>
                <td>${registro.ip_origen}</td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        if (showErrors) {
            console.error('Error:', error);
        }
    }
}

// === GESTIÓN DE BASES DE DATOS ===
async function cargarDatabases() {
    try {
        const data = await apiClient.getDatabases();
        
        if (data.status === 'success') {
            mostrarDatabases(data.data);
            const maintenanceSelect = document.getElementById('maintenanceDatabaseSelect');
            if (maintenanceSelect) {
                maintenanceSelect.innerHTML = '<option value="">-- Base de datos para mantenimiento --</option>';
                (data.data || []).forEach(db => {
                    maintenanceSelect.innerHTML += `<option value="${db}">${db}</option>`;
                });
                if (!maintenanceSelect.value && data.data?.length) {
                    maintenanceSelect.value = pickPreferredDatabase(data.data) || data.data[0];
                }
            }
        } else {
            alert('Error al cargar bases de datos');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar bases de datos: ' + error.message);
    }
}

function mostrarDatabases(databases) {
    const container = document.getElementById('databasesContainer');
    const hiddenCount = hiddenDatabases.length;
    const displayList = databases.filter(db => showHiddenDatabases || !hiddenDatabases.includes(db));
    const adminMode = canAdmin();

    let html = `<div style="margin-bottom:12px">
        <button onclick="toggleMostrarOcultas()" class="btn btn-secondary btn-small">
            ${showHiddenDatabases ? 'Ocultar inactivas' : `Mostrar ocultas (${hiddenCount})`}
        </button>
    </div>
    <table class="data-table">
        <thead><tr><th>Base de Datos</th><th>Acciones</th></tr></thead>
        <tbody>`;

    displayList.forEach(db => {
        const isHidden = hiddenDatabases.includes(db);
        html += `<tr${isHidden ? ' style="opacity:0.5"' : ''}><td>${db}${isHidden ? ' <em style="color:#999;font-size:.85em">(oculta)</em>' : ''}</td><td>`;
        if (!isHidden) {
            html += `
                <button onclick="verTablas('${db}')" class="btn btn-small">Ver Tablas</button>
                ${canCapture() ? `<button onclick="abrirImportBD('${db}')" class="btn btn-small">Importar</button>` : ''}
                ${adminMode ? `<button onclick="abrirQueryPanel('${db}')" class="btn btn-small btn-secondary">Query</button>` : ''}
                <button onclick="ocultarDatabase('${db}')" class="btn btn-small btn-secondary">Ocultar</button>
                ${adminMode ? `<button onclick="eliminarDatabase('${db}')" class="btn btn-small btn-danger">Eliminar</button>` : ''}`;
        } else {
            html += `<button onclick="mostrarDatabase('${db}')" class="btn btn-small">Mostrar</button>`;
        }
        html += `</td></tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;

    // Actualizar select de query (solo bases visibles)
    const select = document.getElementById('queryDatabase');
    select.innerHTML = '<option value="">-- Selecciona BD --</option>';
    const visibleDatabases = databases.filter(db => !hiddenDatabases.includes(db));
    visibleDatabases.forEach(db => {
        select.innerHTML += `<option value="${db}">${db}</option>`;
    });
    const preferredDatabase = pickPreferredDatabase(visibleDatabases);
    if (preferredDatabase) {
        select.value = preferredDatabase;
    }
}

function ocultarDatabase(name) {
    if (!hiddenDatabases.includes(name)) {
        hiddenDatabases.push(name);
        localStorage.setItem('hiddenDatabases', JSON.stringify(hiddenDatabases));
    }
    cargarDatabases();
}

function mostrarDatabase(name) {
    hiddenDatabases = hiddenDatabases.filter(d => d !== name);
    localStorage.setItem('hiddenDatabases', JSON.stringify(hiddenDatabases));
    cargarDatabases();
}

function toggleMostrarOcultas() {
    showHiddenDatabases = !showHiddenDatabases;
    cargarDatabases();
}

async function eliminarDatabase(name) {
    if (!(await showAppConfirm(`¿Eliminar permanentemente la base de datos "${name}"? Esta acción borrará todos sus datos y no se puede deshacer.`, { title: 'Eliminar base de datos', tone: 'error', acceptText: 'Eliminar' }))) return;
    if (!(await showAppConfirm(`Segunda confirmación: ¿continuar con la eliminación de "${name}"?`, { title: 'Confirmar eliminación', tone: 'error', acceptText: 'Sí, eliminar definitivamente' }))) return;
    try {
        await apiClient.deleteDatabase(name);
        alert(`Base de datos "${name}" eliminada.`);
        cargarDatabases();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al eliminar: ' + error.message);
    }
}

async function verTablas(database) {
    try {
        const data = await apiClient.getTables(database);
        
        if (data.status === 'success') {
            mostrarTablas(database, data.data);
        } else {
            alert('Error al cargar tablas');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar tablas: ' + error.message);
    }
}

function mostrarTablas(database, tables) {
    const container = document.getElementById('databasesContainer');
    const adminMode = canAdmin();
    const captureMode = canCapture();
    
    let html = `<div style="margin-bottom:12px">
        <button onclick="cargarDatabases()" class="btn btn-secondary btn-small">← Bases de Datos</button>
        ${captureMode ? `<button onclick="abrirImportBD('${database}')" class="btn btn-small" style="margin-left:8px">Importar archivo</button>` : ''}
        ${adminMode ? `<button onclick="eliminarTablasPruebaUI('${database}')" class="btn btn-small btn-danger" style="margin-left:8px">Eliminar Tablas de Prueba</button>` : ''}
        <button onclick="verVistas('${database}')" class="btn btn-small btn-secondary" style="margin-left:8px">Vistas</button>
        ${adminMode ? `<button onclick="crearVistaTemporal('${database}')" class="btn btn-small btn-secondary" style="margin-left:8px">Crear Vista</button>` : ''}
    </div>
    <h3>Tablas en ${database}</h3>
    <table class="data-table">
        <thead><tr><th>Tabla</th><th>Acciones</th></tr></thead>
        <tbody>`;
    
    tables.forEach(table => {
        html += `
            <tr>
                <td>${renderDbObjectCell(table)}</td>
                <td>
                    <button onclick="verDatosTabla('${database}', '${table}')" class="btn btn-small">Ver Datos</button>
                    ${captureMode ? `<button onclick="abrirImportBD('${database}', '${table}')" class="btn btn-small">Importar</button>` : ''}
                    ${adminMode ? `<button onclick="eliminarTabla('${database}', '${table}')" class="btn btn-small btn-danger">Eliminar</button>` : ''}
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function eliminarTablasPruebaUI(database) {
    if (!canAdmin()) {
        alert('Solo administradores pueden eliminar tablas de prueba.');
        return;
    }
    if (!(await showAppConfirm(`Se eliminarán tablas de prueba en ${database} con prefijos tmp_, temp_, test_, ui_temp_ o debug_.`, { title: 'Eliminar tablas de prueba', tone: 'warning', acceptText: 'Eliminar' }))) {
        return;
    }

    try {
        const query = `
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '${database}'
              AND table_type = 'BASE TABLE'
              AND (
                table_name LIKE 'tmp_%' OR
                table_name LIKE 'temp_%' OR
                table_name LIKE 'test_%' OR
                table_name LIKE 'ui_temp_%' OR
                table_name LIKE 'debug_%'
              )
        `;
        const result = await apiClient.executeQuery(database, query);
        const rows = result.data || [];
        if (!rows.length) {
            alert('No se encontraron tablas de prueba para eliminar.');
            return;
        }

        for (const row of rows) {
            const tableName = row.table_name;
            await apiClient.deleteTable(database, tableName);
        }

        alert(`Se eliminaron ${rows.length} tabla(s) de prueba.`);
        await verTablas(database);
    } catch (error) {
        console.error('Error:', error);
        alert('Error eliminando tablas de prueba: ' + error.message);
    }
}

async function verVistas(database) {
    try {
        const data = await apiClient.getViews(database);
        if (data.status !== 'success') {
            alert('Error al cargar vistas');
            return;
        }

        const views = data.data || [];
        const container = document.getElementById('databasesContainer');
        const adminMode = canAdmin();
        let html = `<div style="margin-bottom:12px">
            <button onclick="verTablas('${database}')" class="btn btn-secondary btn-small">← Tablas</button>
            ${adminMode ? `<button onclick="crearVistaTemporal('${database}')" class="btn btn-small" style="margin-left:8px">Crear Vista</button>` : ''}
        </div>
        <h3>Vistas en ${database}</h3>`;

        if (!views.length) {
            html += '<p>No hay vistas creadas.</p>';
            container.innerHTML = html;
            return;
        }

        html += '<table class="data-table"><thead><tr><th>Vista</th><th>Acciones</th></tr></thead><tbody>';
        views.forEach(view => {
            html += `<tr>
                <td>${renderDbObjectCell(view)}</td>
                <td>
                    <button onclick="verDatosTabla('${database}', '${view}')" class="btn btn-small">Consultar</button>
                    ${adminMode ? `<button onclick="eliminarVista('${database}', '${view}')" class="btn btn-small btn-danger">Eliminar</button>` : ''}
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar vistas: ' + error.message);
    }
}

async function crearVistaTemporal(database) {
    const viewName = await showAppPrompt('Nombre de la vista: (solo letras, números y _)', { title: 'Crear vista', placeholder: 'nombre_vista' });
    if (!viewName) return;
    const selectQuery = await showAppPrompt('Consulta SELECT para la vista:', { title: 'Consulta de la vista', placeholder: 'SELECT ...' });
    if (!selectQuery) return;

    try {
        await apiClient.createView(database, viewName.trim(), selectQuery.trim(), true);
        alert(`Vista ${viewName} creada/actualizada en ${database}.`);
        verVistas(database);
    } catch (error) {
        console.error('Error:', error);
        alert('Error creando vista: ' + error.message);
    }
}

async function eliminarVista(database, viewName) {
    if (!(await showAppConfirm(`¿Eliminar la vista ${viewName}?`, { title: 'Eliminar vista', tone: 'warning', acceptText: 'Eliminar' }))) return;
    try {
        await apiClient.deleteView(database, viewName);
        alert('Vista eliminada.');
        verVistas(database);
    } catch (error) {
        console.error('Error:', error);
        alert('Error eliminando vista: ' + error.message);
    }
}

async function verDatosTabla(database, table) {
    try {
        currentTableBrowserState = {
            database,
            table,
            orderBy: currentTableBrowserState.table === table ? currentTableBrowserState.orderBy : 'id',
            direction: currentTableBrowserState.table === table ? currentTableBrowserState.direction : 'desc',
            limit: 50,
        };
        const data = await apiClient.getTableData(
            database,
            table,
            currentTableBrowserState.limit,
            0,
            currentTableBrowserState.orderBy,
            currentTableBrowserState.direction
        );
        
        if (data.status === 'success') {
            mostrarDatosTabla(database, table, data);
        } else {
            alert('Error al cargar datos');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar datos: ' + error.message);
    }
}

async function cargarResumenMantenimiento() {
    if (!canAdmin()) return;
    const database = document.getElementById('maintenanceDatabaseSelect')?.value || document.getElementById('queryDatabase')?.value || '';
    if (!database) {
        alert('Selecciona una base de datos para mantenimiento.');
        return;
    }
    try {
        const result = await apiClient.getMaintenanceOverview(database);
        const target = document.getElementById('dbMaintenanceResult');
        const objects = result.objects || [];
        const actions = result.recommended_actions || [];
        let html = `<p><strong>${database}</strong>: ${objects.length} objetos analizados.</p>`;
        html += `<p>Acciones sugeridas: ${actions.length ? actions.join(' | ') : 'Sin objetos temporales detectados.'}</p>`;
        html += '<table class="data-table"><thead><tr><th>Objeto</th><th>Tipo</th><th>Filas</th><th>Estado</th></tr></thead><tbody>';
        objects.forEach(item => {
            const flags = [];
            if (item.is_protected) flags.push('Protegido');
            if (item.is_temp_candidate) flags.push('Temporal');
            html += `<tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.type)}</td><td>${item.row_count ?? '-'}</td><td>${escapeHtml(flags.join(' · ') || 'Normal')}</td></tr>`;
        });
        html += '</tbody></table>';
        target.innerHTML = html;
        document.getElementById('dbMaintenancePanel').style.display = 'block';
    } catch (error) {
        console.error('Error:', error);
        alert('Error analizando esquema: ' + error.message);
    }
}

async function crearVistasUtilesUI() {
    if (!canAdmin()) return;
    const database = document.getElementById('maintenanceDatabaseSelect')?.value || '';
    if (!database) {
        alert('Selecciona una base de datos para crear vistas.');
        return;
    }
    try {
        const result = await apiClient.createUsefulViews(database);
        alert(result.message || 'Vistas útiles creadas.');
        cargarResumenMantenimiento();
    } catch (error) {
        console.error('Error:', error);
        alert('Error creando vistas útiles: ' + error.message);
    }
}

async function depurarObjetosTemporales() {
    if (!canAdmin()) return;
    const database = document.getElementById('maintenanceDatabaseSelect')?.value || '';
    if (!database) {
        alert('Selecciona una base de datos para depurar.');
        return;
    }
    if (!(await showAppConfirm('Se eliminarán objetos temporales o de prueba detectados automáticamente.', { title: 'Depurar objetos temporales', tone: 'warning', acceptText: 'Depurar' }))) return;
    try {
        const result = await apiClient.purgeTemporaryObjects(database, false);
        alert(result.message || 'Depuración completada.');
        cargarResumenMantenimiento();
        verTablas(database);
    } catch (error) {
        console.error('Error:', error);
        alert('Error depurando objetos temporales: ' + error.message);
    }
}

async function depurarAgentesRedundantesUI() {
    if (!canAdmin()) return;
    const database = document.getElementById('maintenanceDatabaseSelect')?.value || '';
    if (!database) {
        alert('Selecciona una base de datos para depurar agentes.');
        return;
    }
    if (database !== 'database_manager') {
        alert('Esta depuración solo aplica en database_manager.');
        return;
    }

    try {
        const preview = await apiClient.cleanupRedundantAgents(database, true);
        const data = preview?.data || {};
        const candidatos = Number(data.candidate_ids?.length || 0);
        const testLike = Number(data.test_like_candidates || 0);
        const dupes = Number(data.duplicate_candidates || 0);
        if (!candidatos) {
            alert('No se detectaron agentes redundantes o de prueba para eliminar.');
            return;
        }

        const msg = `Se detectaron ${candidatos} candidatos (test=${testLike}, duplicados=${dupes}).\n¿Aplicar depuración ahora?`;
        if (!(await showAppConfirm(msg, { title: 'Depurar agentes redundantes', tone: 'warning', acceptText: 'Aplicar' }))) return;

        const result = await apiClient.cleanupRedundantAgents(database, false);
        const finalData = result?.data || {};
        alert(`Depuración completada. Eliminados: ${finalData.deleted || 0}. Activos: ${finalData.after_active || 0}.`);
        cargarResumenMantenimiento();
        verTablas(database);
    } catch (error) {
        console.error('Error:', error);
        alert('Error depurando agentes redundantes: ' + error.message);
    }
}

async function refrescarDatosTablaNavegador() {
    if (!currentTableBrowserState.database || !currentTableBrowserState.table) return;
    try {
        const data = await apiClient.getTableData(
            currentTableBrowserState.database,
            currentTableBrowserState.table,
            currentTableBrowserState.limit,
            0,
            currentTableBrowserState.orderBy,
            currentTableBrowserState.direction
        );
        if (data.status === 'success') {
            mostrarDatosTabla(currentTableBrowserState.database, currentTableBrowserState.table, data);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error refrescando tabla: ' + error.message);
    }
}

function cambiarOrdenTablaNavegador() {
    const orderBy = document.getElementById('dbTableOrderBy')?.value || 'id';
    const direction = document.getElementById('dbTableOrderDir')?.value || 'desc';
    currentTableBrowserState.orderBy = orderBy;
    currentTableBrowserState.direction = direction;
    refrescarDatosTablaNavegador();
}

function mostrarDatosTabla(database, table, data) {
    const container = document.getElementById('databasesContainer');
    const columns = data.columns || [];
    const orderBy = data.order_by || currentTableBrowserState.orderBy || 'id';
    const direction = (data.direction || currentTableBrowserState.direction || 'desc').toLowerCase();
    currentTableBrowserState = {
        database,
        table,
        orderBy,
        direction,
        limit: currentTableBrowserState.limit || 50,
    };
    
    const info = getDbObjectInfo(table);
    const titleText = info ? `${info.logical} [${table}]` : table;
    let html = `<h3>Datos de ${escapeHtml(titleText)} en ${escapeHtml(database)}</h3>`;
    if (info) {
        html += `<p class="hint">${escapeHtml(info.purpose)}</p>`;
    }
    html += `<p>Total de registros: ${data.total}</p>`;
    html += `<div class="search-bar" style="margin-bottom:10px;max-width:760px;">
        <select id="dbTableOrderBy" onchange="cambiarOrdenTablaNavegador()">
            ${columns.map(col => `<option value="${col}" ${col === orderBy ? 'selected' : ''}>Ordenar por ${col}</option>`).join('')}
        </select>
        <select id="dbTableOrderDir" onchange="cambiarOrdenTablaNavegador()">
            <option value="desc" ${direction === 'desc' ? 'selected' : ''}>Descendente</option>
            <option value="asc" ${direction === 'asc' ? 'selected' : ''}>Ascendente</option>
        </select>
        <button type="button" class="btn btn-secondary" onclick="refrescarDatosTablaNavegador()">Refrescar</button>
    </div>`;
    
    if (data.data.length === 0) {
        html += '<p>No hay datos</p>';
        container.innerHTML = html;
        return;
    }
    
    html += '<table class="data-table"><thead><tr>';
    columns.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    data.data.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            html += `<td>${row[col] || ''}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

function abrirQueryPanel(database = '') {
    const panel = document.getElementById('queryPanel');
    panel.style.display = 'block';
    if (database) {
        document.getElementById('queryDatabase').value = database;
    }
}

function cerrarQueryPanel() {
    document.getElementById('queryPanel').style.display = 'none';
    document.getElementById('queryResult').innerHTML = '';
}

async function ejecutarQuerySQL() {
    const database = document.getElementById('queryDatabase').value;
    const query = document.getElementById('querySQL').value.trim();
    
    if (!database || !query) {
        alert('Selecciona base de datos y escribe una consulta');
        return;
    }
    
    try {
        const data = await apiClient.executeQuery(database, query);
        mostrarResultadoQuery(data);
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('queryResult').innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
    }
}

function mostrarResultadoQuery(data) {
    const container = document.getElementById('queryResult');
    
    if (data.data && data.data.length > 0) {
        let html = `<p>Resultado (${data.row_count} filas):</p>`;
        html += '<table class="data-table"><thead><tr>';
        
        const columns = Object.keys(data.data[0]);
        columns.forEach(col => {
            html += `<th>${col}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        data.data.forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                html += `<td>${row[col] || ''}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    } else {
        container.innerHTML = '<p>Consulta ejecutada exitosamente</p>';
    }
}

async function eliminarTabla(database, table) {
    if (!(await showAppConfirm(`¿Eliminar la tabla ${table}?`, { title: 'Eliminar tabla', tone: 'error', acceptText: 'Eliminar' }))) {
        return;
    }
    
    try {
        await apiClient.deleteTable(database, table);
        alert('Tabla eliminada exitosamente');
        verTablas(database);
    } catch (error) {
        console.error('Error:', error);
        alert('Error al eliminar tabla: ' + error.message);
    }
}

// === IMPORTAR ARCHIVO A BASE DE DATOS ===
function abrirImportBD(dbName, tableHint = '') {
    currentImportDB = dbName;
    document.getElementById('importBDName').textContent = dbName;
    document.getElementById('importBDTableInput').value = tableHint;
    document.getElementById('importBDFile').value = '';
    document.getElementById('importBDProgress').style.display = 'none';
    document.getElementById('importBDResult').textContent = '';
    document.getElementById('importBDModal').style.display = 'block';
}

function cerrarImportBD() {
    document.getElementById('importBDModal').style.display = 'none';
}

async function importarABD(e) {
    e.preventDefault();
    const file = document.getElementById('importBDFile').files[0];
    const tableName = document.getElementById('importBDTableInput').value.trim();
    const delimiter = document.getElementById('importBDDelimiter').value;
    const encoding = document.getElementById('importBDEncoding').value;

    if (!file || !tableName) {
        alert('Selecciona un archivo y escribe el nombre de la tabla destino.');
        return;
    }

    const progress = document.getElementById('importBDProgress');
    const resultEl = document.getElementById('importBDResult');
    progress.style.display = 'block';
    resultEl.textContent = '';

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('table_name', tableName);
        formData.append('delimiter', delimiter);
        formData.append('encoding', encoding);

        const result = await apiClient.importToDatabase(currentImportDB, formData);
        progress.style.display = 'none';
        const msg = `Importación completada: ${result.imported} registros importados` +
            (result.failed ? `, ${result.failed} fallidos` : '') +
            ` en ${currentImportDB}.${result.table}`;
        alert(msg);
        cerrarImportBD();
    } catch (error) {
        progress.style.display = 'none';
        resultEl.textContent = 'Error: ' + error.message;
        console.error('Error importando:', error);
    }
}

// === ESTADO DE AGENTES ===
async function cargarEstadoAgentes() {
    const search = (document.getElementById('estadoAgentesSearch')?.value || '').trim();
    const container = document.getElementById('estadoAgentesContainer');
    const result = document.getElementById('estadoAgentesResult');
    if (!container) return;
    container.innerHTML = '<p class="hint">Cargando...</p>';
    if (result) result.innerHTML = '';
    try {
        const url = `${API_URL}/qr/agentes/estado${search ? '?search=' + encodeURIComponent(search) : ''}`;
        const data = await fetchJson(url, { headers: { 'Authorization': `Bearer ${authToken}` } });

        const rows = Array.isArray(data?.data) ? data.data : [];
        const sinLineaCount = rows.filter(r => Number(r.lineas_count || 0) <= 0).length;
        const countEl = document.getElementById('estadoAgentesCount');
        if (countEl) countEl.textContent = sinLineaCount;

        if (!rows.length) {
            container.innerHTML = '<p class="hint" style="color:green;">No hay agentes activos para mostrar.</p>';
            return;
        }

        let html = `<table class="data-table">
            <thead><tr>
                <th>ID</th><th>Nombre</th><th>Alias</th><th>Estado Línea</th><th>Líneas Activas</th><th>Números de Línea</th><th>QR</th><th>Alta</th><th>Acciones</th>
            </tr></thead><tbody>`;
        rows.forEach(ag => {
            const alias = ag.alias || ag.datos_adicionales?.alias || '—';
            const lineaEstado = String(ag.linea_estado || (ag.extension_numero ? 'ASIGNADA' : 'SIN_LINEA')).toUpperCase();
            const lineasCount = Number(ag.lineas_count || 0);
            const lineasNumeros = String(ag.lineas_numeros || '').trim() || '—';
            const tieneQr = ag.tiene_qr ? '✓ Sí' : '✗ No';
            const qrClass = ag.tiene_qr ? 'color:green;' : 'color:#b37400;';
            const alta = ag.fecha_creacion ? new Date(ag.fecha_creacion).toLocaleDateString() : '—';
            const rowClass = lineaEstado === 'ASIGNADA' ? '' : 'row-sin-linea';
            html += `<tr class="${rowClass}">
                <td>${ag.id}</td>
                <td>${escapeHtml(ag.nombre || '—')}</td>
                <td>${escapeHtml(String(alias))}</td>
                <td>${lineaEstado.replace('_', ' ')}</td>
                <td>${lineasCount}</td>
                <td>${escapeHtml(lineasNumeros)}</td>
                <td style="${qrClass}">${tieneQr}</td>
                <td>${escapeHtml(alta)}</td>
                <td>
                    <button type="button" class="btn btn-small" onclick="mostrarQrParaAgente(${ag.id}, '${String(ag.nombre || 'Agente').replace(/'/g, "\\'")}')" title="Generar y ver código QR de este agente">&#128247; QR</button>
                    <button type="button" class="btn btn-small btn-secondary" onclick="loadSection('altasAgentes')" title="Ir a Altas para asignar línea">&#128222; Línea</button>
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<p style="color:red;">Error al cargar estado de agentes: ${escapeHtml(err.message)}</p>`;
    }
}

async function generarQRMasivo() {
    const btn = document.getElementById('btnGenerarQRMasivo');
    const result = document.getElementById('estadoAgentesResult');
    if (!(await showAppConfirm('¿Generar QR automático para todos los agentes que aún no lo tienen?', { title: 'Generación masiva de QR', tone: 'info', acceptText: 'Generar' }))) return;
    if (btn) btn.disabled = true;
    if (result) result.innerHTML = '<p class="hint">Generando QRs, espera...</p>';
    try {
        const data = await fetchJson(`${API_URL}/qr/agentes/generar-qr-masivo`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' }
        });
        if (result) {
            result.innerHTML = `<p style="color:green;">✓ QRs generados: <strong>${data.generados ?? 0}</strong> de ${data.total_sin_qr ?? 0} agentes sin QR.${data.errores?.length ? ` (${data.errores.length} errores)` : ''}</p>`;
        }
        cargarEstadoAgentes();
    } catch (err) {
        if (result) result.innerHTML = `<p style="color:red;">Error: ${escapeHtml(err.message)}</p>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function generarQRAgenteIndividual(agenteId) {
    const rows = Array.isArray(currentAgentManagementRows) ? currentAgentManagementRows : [];
    const found = rows.find(item => Number(item.id) === Number(agenteId));
    return mostrarQrParaAgente(agenteId, found?.nombre || 'Agente');
}

// === GESTIÓN DE USUARIOS ===
async function cargarUsuarios() {
    try {
        const orderBy = document.getElementById('usuariosOrderBy')?.value || 'fecha_creacion';
        const direction = document.getElementById('usuariosOrderDir')?.value || 'desc';
        const usuarios = await apiClient.getUsuarios(orderBy, direction);
        currentUsuariosRows = Array.isArray(usuarios) ? usuarios : [];
        mostrarUsuarios(usuarios);
        if (canAdmin()) {
            cargarMantenimientoUsuarios(false);
            cargarSolicitudesPermisosTemporales(false);
            cargarHistorialTemporales(false);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar usuarios: ' + error.message);
    }
}

function mostrarUsuarios(usuarios) {
    const container = document.getElementById('usuariosContainer');
    
    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Usuario</th>
                    <th>Email</th>
                    <th>Nombre</th>
                    <th>Rol</th>
                    <th>Temporal</th>
                    <th>Expira</th>
                    <th>Solicitud</th>
                    <th>Activo</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    usuarios.forEach(user => {
        const temporalBadge = user.es_temporal
            ? '<span class="status-pill temp">Temporal</span>'
            : '<span class="status-pill normal">Normal</span>';
        const requestState = String(user.solicitud_permiso_estado || 'none').toLowerCase();
        const requestBadge = requestState === 'pending'
            ? '<span class="status-pill pending">Pendiente</span>'
            : requestState === 'approved'
                ? '<span class="status-pill approved">Aprobada</span>'
                : requestState === 'rejected'
                    ? '<span class="status-pill rejected">Rechazada</span>'
                    : '-';
        const renewButton = user.es_temporal
            ? `<button onclick="renovarUsuarioTemporal(${user.id}, 10)" class="btn btn-small btn-secondary">Renovar 10d</button>`
            : '';
        const requestButtons = user.es_temporal
                ? `<button onclick="solicitarPermisosTemporal(${user.id}, 'viewer')" class="btn btn-small btn-secondary">Solicitar normal limitado</button>
                    <button onclick="solicitarPermisosTemporal(${user.id}, 'capture')" class="btn btn-small btn-secondary">Solicitar capture</button>
               <button onclick="solicitarPermisosTemporal(${user.id}, 'admin')" class="btn btn-small btn-secondary">Solicitar admin</button>`
            : '';
        html += `
            <tr>
                <td>${user.id}</td>
                <td>${user.username}</td>
                <td>${user.email}</td>
                <td>${user.nombre_completo || ''}</td>
                <td>${user.rol || (user.es_admin ? 'admin' : 'viewer')}</td>
                <td>${temporalBadge}</td>
                <td>${formatDateTimeSafe(user.temporal_expira_en)}</td>
                <td>${requestBadge}</td>
                <td>${user.es_activo ? 'Sí' : 'No'}</td>
                <td>
                    <button onclick="editarUsuario(${user.id})" class="btn btn-small">Editar</button>
                    <button onclick="cambiarPassword(${user.id})" class="btn btn-small btn-secondary">Contraseña</button>
                    <button onclick="eliminarUsuario(${user.id}, false)" class="btn btn-small btn-danger">Desactivar</button>
                    <button onclick="eliminarUsuario(${user.id}, true)" class="btn btn-small btn-danger">Eliminar Definitivo</button>
                    ${renewButton}
                    ${requestButtons}
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function cargarMantenimientoUsuarios(showErrors = true) {
    if (!canAdmin()) return;
    const container = document.getElementById('usuariosMaintenanceContainer');
    if (!container) return;
    try {
        const result = await apiClient.getUsuariosMaintenanceOverview();
        const summary = result.summary || {};
        const candidates = result.candidates || [];

        let html = `<div class="card" style="padding:12px;border:1px solid #d8e6f4;border-radius:10px;background:#f9fcff;color:#173049;">
            <strong>Resumen:</strong>
            Total ${summary.total ?? 0} · Activos ${summary.activos ?? 0} · Inactivos ${summary.inactivos ?? 0} ·
            Viewer ${summary.viewers ?? 0} · Capture ${summary.captures ?? 0} · Admin ${summary.admins ?? 0}<br>
            <strong>Candidatos a depurar:</strong> ${summary.candidatos_depurar ?? 0}
            <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
                <button type="button" class="btn btn-secondary" onclick="aplicarReclasificacionMasiva()">Aplicar Cambios de Rol</button>
            </div>
        </div>`;

        if (!candidates.length) {
            html += '<p class="hint" style="margin-top:8px;">No hay usuarios temporales u obsoletos detectados.</p>';
            container.innerHTML = html;
            return;
        }

        html += '<table class="data-table" style="margin-top:8px;"><thead><tr><th>Aplicar</th><th>ID</th><th>Usuario</th><th>Rol Nuevo</th><th>Activo</th><th>Temp</th><th>Obsoleto</th></tr></thead><tbody>';
        candidates.forEach(user => {
            html += `<tr>
                <td><input type="checkbox" class="bulk-user-check" data-user-id="${user.id}" checked></td>
                <td>${user.id}</td>
                <td>${escapeHtml(user.username)}</td>
                <td>
                    <select class="bulk-user-role" data-user-id="${user.id}">
                        <option value="viewer" ${user.rol === 'viewer' ? 'selected' : ''}>viewer</option>
                        <option value="capture" ${user.rol === 'capture' ? 'selected' : ''}>capture</option>
                        <option value="admin" ${user.rol === 'admin' ? 'selected' : ''}>admin</option>
                    </select>
                </td>
                <td><input type="checkbox" class="bulk-user-active" data-user-id="${user.id}" ${user.es_activo ? 'checked' : ''}></td>
                <td>${user.is_temp_name ? 'Sí' : 'No'}</td>
                <td>${user.is_stale ? 'Sí' : 'No'}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        if (showErrors) {
            console.error('Error:', error);
            alert('Error cargando mantenimiento de usuarios: ' + error.message);
        }
    }
}

async function aplicarReclasificacionMasiva() {
    if (!canAdmin()) return;
    const checks = Array.from(document.querySelectorAll('.bulk-user-check')).filter(el => el.checked);
    if (!checks.length) {
        alert('Selecciona al menos un usuario en la lista de mantenimiento.');
        return;
    }
    const updates = checks.map(el => {
        const userId = Number(el.getAttribute('data-user-id'));
        const role = document.querySelector(`.bulk-user-role[data-user-id="${userId}"]`)?.value || 'viewer';
        const active = document.querySelector(`.bulk-user-active[data-user-id="${userId}"]`)?.checked ?? true;
        return { id: userId, rol: role, es_activo: active };
    });

    try {
        const result = await apiClient.reclassifyUsuariosBulk(updates);
        alert(`Reclasificación aplicada a ${result.count || 0} usuarios.`);
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error en reclasificación masiva: ' + error.message);
    }
}

async function depurarUsuariosTemporales() {
    if (!canAdmin()) return;
    if (!(await showAppConfirm('Se eliminarán definitivamente usuarios temporales/obsoletos (excepto admins).', { title: 'Depurar usuarios temporales', tone: 'warning', acceptText: 'Depurar' }))) return;
    try {
        const result = await apiClient.purgeTemporaryUsuarios(true);
        alert(`Depuración completada. Eliminados: ${result.count || 0}`);
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error depurando usuarios temporales: ' + error.message);
    }
}

async function crearUsuarioTemporal(event) {
    event.preventDefault();
    if (!canAdmin()) return;
    const payload = {
        username: document.getElementById('tempUsername')?.value?.trim(),
        email: document.getElementById('tempEmail')?.value?.trim(),
        nombre_completo: document.getElementById('tempNombre')?.value?.trim() || null,
        password: document.getElementById('tempPassword')?.value || '',
        dias_vigencia: Number(document.getElementById('tempDias')?.value || 10),
    };
    try {
        await apiClient.crearUsuarioTemporal(payload);
        alert('Usuario temporal creado.');
        document.getElementById('tempUsername').value = '';
        document.getElementById('tempEmail').value = '';
        document.getElementById('tempNombre').value = '';
        document.getElementById('tempPassword').value = '';
        document.getElementById('tempDias').value = '10';
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error creando usuario temporal: ' + error.message);
    }
}

async function renovarUsuarioTemporal(userId, diasVigencia = 10) {
    if (!canAdmin()) return;
    try {
        await apiClient.renovarUsuarioTemporal(userId, diasVigencia);
        alert('Usuario temporal renovado.');
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error renovando usuario temporal: ' + error.message);
    }
}

async function solicitarPermisosTemporal(userId, role = 'capture') {
    const motivo = await showAppPrompt('Motivo de la solicitud de permisos (opcional):', { title: 'Solicitar permisos temporales', placeholder: 'Motivo o circunstancia' }) || '';
    try {
        await apiClient.solicitarPermisoTemporal(userId, { rol_solicitado: role, motivo });
        alert('Solicitud registrada.');
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error registrando solicitud: ' + error.message);
    }
}

async function cargarSolicitudesPermisosTemporales(showErrors = true) {
    if (!canAdmin()) return;
    const container = document.getElementById('usuariosSolicitudesContainer');
    if (!container) return;
    try {
        const result = await apiClient.getSolicitudesPermisosTemporales();
        const items = result.items || [];
        if (!items.length) {
            container.innerHTML = '<p class="hint">Sin solicitudes de permisos pendientes.</p>';
            return;
        }
        let html = '<table class="data-table"><thead><tr><th>ID</th><th>Usuario</th><th>Rol Actual</th><th>Solicita</th><th>Motivo</th><th>Fecha</th><th>Acciones</th></tr></thead><tbody>';
        items.forEach(item => {
            html += `<tr>
                <td>${item.id}</td>
                <td>${escapeHtml(item.username)}</td>
                <td>${escapeHtml(item.rol_actual || '-')}</td>
                <td>${escapeHtml(item.rol_solicitado || '-')}</td>
                <td>${escapeHtml(item.motivo || '')}</td>
                <td>${formatDateTimeSafe(item.solicitado_en)}</td>
                <td>
                    <button type="button" class="btn btn-small" onclick="resolverSolicitudPermisoTemporal(${item.id}, true, 'viewer')">Aprobar consulta</button>
                    <button type="button" class="btn btn-small" onclick="resolverSolicitudPermisoTemporal(${item.id}, true, 'capture')">Aprobar capture</button>
                    <button type="button" class="btn btn-small btn-secondary" onclick="resolverSolicitudPermisoTemporal(${item.id}, true, 'admin')">Aprobar admin</button>
                    <button type="button" class="btn btn-small btn-danger" onclick="resolverSolicitudPermisoTemporal(${item.id}, false, 'capture')">Rechazar</button>
                </td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        if (showErrors) {
            console.error('Error:', error);
            alert('Error cargando solicitudes: ' + error.message);
        }
    }
}

async function resolverSolicitudPermisoTemporal(userId, aprobar, rolAprobado = 'capture') {
    if (!canAdmin()) return;
    const mensaje = aprobar
        ? `¿Aprobar solicitud del usuario ${userId} con rol ${rolAprobado}?`
        : `¿Rechazar solicitud del usuario ${userId}?`;
    if (!(await showAppConfirm(mensaje, { title: aprobar ? 'Aprobar solicitud' : 'Rechazar solicitud', tone: aprobar ? 'info' : 'warning', acceptText: aprobar ? 'Aprobar' : 'Rechazar' }))) return;
    try {
        await apiClient.resolverSolicitudPermisoTemporal(userId, {
            aprobar: Boolean(aprobar),
            rol_aprobado: rolAprobado,
        });
        alert('Solicitud procesada.');
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error resolviendo solicitud: ' + error.message);
    }
}

async function cargarHistorialTemporales(showErrors = true) {
    if (!canAdmin()) return;
    const container = document.getElementById('usuariosTempHistoryContainer');
    if (!container) return;
    try {
        const rows = await apiClient.getHistorialTemporales(120);
        if (!Array.isArray(rows) || !rows.length) {
            container.innerHTML = '<p class="hint">No hay historial de temporales eliminados.</p>';
            return;
        }
        let html = '<table class="data-table"><thead><tr><th>ID Hist</th><th>Usuario</th><th>Rol</th><th>Creado</th><th>Expiraba</th><th>Eliminado</th><th>Motivo</th></tr></thead><tbody>';
        rows.forEach(row => {
            html += `<tr>
                <td>${row.id}</td>
                <td>${escapeHtml(row.username)}</td>
                <td>${escapeHtml(row.rol || '-')}</td>
                <td>${formatDateTimeSafe(row.fecha_creacion_usuario)}</td>
                <td>${formatDateTimeSafe(row.fecha_expiracion)}</td>
                <td>${formatDateTimeSafe(row.fecha_eliminacion)}</td>
                <td>${escapeHtml(row.motivo || '-')}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        if (showErrors) {
            console.error('Error:', error);
            alert('Error cargando historial de temporales: ' + error.message);
        }
    }
}

function mostrarCrearUsuario() {
    document.getElementById('usuarioId').value = '';
    document.getElementById('usuarioUsername').value = '';
    document.getElementById('usuarioEmail').value = '';
    document.getElementById('usuarioNombreCompleto').value = '';
    document.getElementById('usuarioPassword').value = '';
    document.getElementById('usuarioRol').value = 'viewer';
    document.getElementById('usuarioEsActivo').checked = true;
    document.getElementById('passwordGroup').style.display = 'block';
    document.getElementById('usuarioPassword').required = true;
    document.getElementById('modalTitle').textContent = 'Crear Usuario';
    syncUsuarioRoleOptions();
    document.getElementById('usuarioModal').style.display = 'block';
}

async function editarUsuario(userId) {
    try {
        const user = await apiClient.getUsuario(userId);
        
        document.getElementById('usuarioId').value = user.id;
        document.getElementById('usuarioUsername').value = user.username;
        document.getElementById('usuarioEmail').value = user.email;
        document.getElementById('usuarioNombreCompleto').value = user.nombre_completo || '';
        document.getElementById('usuarioRol').value = user.rol || (user.es_admin ? 'admin' : 'viewer');
        document.getElementById('usuarioEsActivo').checked = user.es_activo;
        document.getElementById('passwordGroup').style.display = 'none';
        document.getElementById('usuarioPassword').required = false;
        document.getElementById('usuarioPassword').value = '';
        document.getElementById('modalTitle').textContent = 'Editar Usuario';
        syncUsuarioRoleOptions();
        document.getElementById('usuarioModal').style.display = 'block';
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar usuario: ' + error.message);
    }
}

function cerrarModal() {
    document.getElementById('usuarioModal').style.display = 'none';
}

async function guardarUsuario(e) {
    e.preventDefault();
    
    const userId = document.getElementById('usuarioId').value;
    const role = document.getElementById('usuarioRol').value;
    const userData = {
        username: document.getElementById('usuarioUsername').value,
        email: document.getElementById('usuarioEmail').value,
        nombre_completo: document.getElementById('usuarioNombreCompleto').value,
        rol: role,
        es_admin: role === 'admin' || role === 'super_admin',
        es_activo: document.getElementById('usuarioEsActivo').checked
    };
    
    if (!userId) {
        // Crear usuario
        userData.password = document.getElementById('usuarioPassword').value;
    }
    
    try {
        if (userId) {
            await apiClient.actualizarUsuario(userId, userData);
            alert('Usuario actualizado');
        } else {
            await apiClient.crearUsuario(userData);
            alert('Usuario creado');
        }
        
        cerrarModal();
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al guardar usuario: ' + error.message);
    }
}

async function cambiarPassword(userId) {
    const newPassword = await showAppPrompt('Ingresa la nueva contraseña:', { title: 'Cambiar contraseña', placeholder: '••••••••', type: 'password', acceptText: 'Cambiar' });
    if (!newPassword) return;
    
    try {
        await apiClient.cambiarPasswordUsuario(userId, newPassword);
        alert('Contraseña actualizada');
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cambiar contraseña: ' + error.message);
    }
}

async function eliminarUsuario(userId, hardDelete = false) {
    const message = hardDelete
        ? '¿Eliminar definitivamente este usuario y depurar sus dependencias controladas?'
        : '¿Desactivar este usuario?';
    if (!(await showAppConfirm(message, { title: hardDelete ? 'Eliminar usuario' : 'Desactivar usuario', tone: hardDelete ? 'error' : 'warning', acceptText: hardDelete ? 'Eliminar definitivamente' : 'Desactivar' }))) return;
    
    try {
        await apiClient.eliminarUsuario(userId, hardDelete);
        alert(hardDelete ? 'Usuario eliminado definitivamente' : 'Usuario desactivado');
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al eliminar usuario: ' + error.message);
    }
}


// === SIDEBAR TOGGLE (movil) ===
function toggleSidebar(forceOpen = null) {
    const sidebar = document.getElementById('appSidebar') || document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebarOverlay') || document.querySelector('.sidebar-overlay');
    if (!sidebar) return;
    const isOpen = forceOpen === null ? !sidebar.classList.contains('sidebar-open') : Boolean(forceOpen);
    sidebar.classList.toggle('sidebar-open', isOpen);
    if (overlay) {
        overlay.style.display = isOpen ? 'block' : 'none';
    }
    document.body.style.overflow = isOpen && isMobileViewport() ? 'hidden' : '';
}

// === ALERTAS DEL SISTEMA ===
function getAlertasFiltrosUI() {
    const soloActivas = document.getElementById('alertasSoloActivas')?.checked !== false;
    const nivel = String(document.getElementById('alertasNivelFiltro')?.value || '').trim();
    const texto = String(document.getElementById('alertasTextoFiltro')?.value || '').trim().toLowerCase();
    const limitRaw = parseInt(document.getElementById('alertasLimit')?.value || '50', 10);
    const limit = Number.isFinite(limitRaw) && limitRaw > 0 ? Math.min(limitRaw, 200) : 50;
    return { soloActivas, nivel, texto, limit };
}

async function cargarAlertas(forceRefresh = false) {
    const container = document.getElementById('alertasContainer');
    const envioPanel = document.getElementById('alertasEnvioPanel');
    const noEnvioHint = document.getElementById('alertasNoEnvioHint');
    if (!container) return;
    if (!alertasCache.length || forceRefresh) {
        container.innerHTML = '<p class="hint">Cargando alertas...</p>';
    }

    const canSendAlerts = canAdmin();
    if (envioPanel) envioPanel.style.display = canSendAlerts ? 'block' : 'none';
    if (noEnvioHint) noEnvioHint.style.display = canSendAlerts ? 'none' : 'block';

    try {
        const filters = getAlertasFiltrosUI();
        const ttlMs = 15000;
        const cacheValid = (Date.now() - alertasCacheStampMs) < ttlMs;
        if (forceRefresh || !cacheValid || !alertasCache.length) {
            const data = await fetchJson(`${API_URL}/alertas/?solo_activas=${filters.soloActivas ? 'true' : 'false'}&limit=${filters.limit}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            alertasCache = Array.isArray(data?.items) ? data.items : [];
            alertasCacheStampMs = Date.now();
        }

        renderAlertasDesdeCache();

    } catch (error) {
        container.innerHTML = `<p style="color:red;">Error al cargar alertas: ${error.message}</p>`;
    } finally {
        refreshAlertBadgeAndNotify(false);
    }
}

function renderAlertasDesdeCache() {
    const container = document.getElementById('alertasContainer');
    const stats = document.getElementById('alertasStats');
    if (!container) return;

    const filters = getAlertasFiltrosUI();
    const canManageAlerts = canAdmin();

    let rows = Array.isArray(alertasCache) ? [...alertasCache] : [];
    if (filters.nivel) {
        rows = rows.filter(a => String(a?.nivel || '') === filters.nivel);
    }
    if (filters.texto) {
        rows = rows.filter(a => {
            const hay = `${a?.titulo || ''} ${a?.mensaje || ''} ${a?.remitente_username || ''}`.toLowerCase();
            return hay.includes(filters.texto);
        });
    }

    if (!rows.length) {
        container.innerHTML = '<p class="hint">No hay alertas para los filtros actuales.</p>';
        if (stats) stats.textContent = `Mostrando 0 de ${alertasCache.length} alertas.`;
        return;
    }

    container.innerHTML = rows.map(a => {
        const nivelLabel = { info: 'Info', warning: 'Advertencia', danger: 'Urgente' }[a.nivel] || a.nivel;
        const leida = a.leida ? 'leida' : '';
        const fecha = a.fecha_envio ? new Date(a.fecha_envio).toLocaleString() : '';
        return `
            <div class="alerta-item nivel-${a.nivel} ${leida}" id="alerta-${a.id}">
                <div class="alerta-item-header">
                    <span class="alerta-item-title">${escapeHtml(a.titulo || '')}</span>
                    <span class="badge-nivel ${a.nivel}">${nivelLabel}</span>
                </div>
                <div class="alerta-item-meta">Enviado por: ${escapeHtml(a.remitente_username || '')} &middot; ${escapeHtml(fecha)}</div>
                <div class="alerta-item-body">${escapeHtml(a.mensaje || '')}</div>
                <div class="alerta-item-actions">
                    ${!a.leida ? '<button class="btn btn-small btn-secondary" onclick="marcarAlertaLeida(' + a.id + ')">&#10003; Marcar le\u00edda</button>' : '<span style="font-size:0.8rem;color:#888;">&#10003; Le\u00edda</span>'}
                    ${canManageAlerts ? '<button class="btn btn-small" style="background:#e74c3c;color:#fff;" onclick="desactivarAlerta(' + a.id + ')">&#128465; Desactivar</button>' : ''}
                </div>
            </div>`;
    }).join('');

    const totalUnread = rows.filter(a => !a.leida).length;
    if (stats) {
        stats.textContent = `Mostrando ${rows.length} de ${alertasCache.length} alertas | No leídas visibles: ${totalUnread}`;
    }
}

async function enviarAlerta(event) {
    event.preventDefault();
    const titulo = document.getElementById('alertaTitulo')?.value?.trim();
    const nivel = document.getElementById('alertaNivel')?.value || 'warning';
    const mensaje = document.getElementById('alertaMensaje')?.value?.trim();
    const result = document.getElementById('alertaEnvioResult');

    if (!titulo || !mensaje) {
        if (result) result.innerHTML = '<p style="color:orange;">T\u00edtulo y mensaje son obligatorios.</p>';
        return;
    }
    if (result) result.innerHTML = '<p class="hint">Enviando...</p>';

    try {
        const created = await fetchJson(`${API_URL}/alertas/enviar-json`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ titulo, mensaje, nivel })
        });
        if (result) result.innerHTML = '<p style="color:green;">&#10003; Alerta enviada correctamente.</p>';
        document.getElementById('alertaTitulo').value = '';
        document.getElementById('alertaMensaje').value = '';
        document.getElementById('alertaNivel').value = 'warning';
        lastAlertNotificationStamp = null;
        alertasCache = [created, ...alertasCache];
        alertasCacheStampMs = Date.now();
        renderAlertasDesdeCache();
        refreshAlertBadgeAndNotify(false);
    } catch (error) {
        if (result) result.innerHTML = `<p style="color:red;">Error: ${error.message}</p>`;
    }
}

async function marcarAlertaLeida(id) {
    const idx = alertasCache.findIndex(a => Number(a.id) === Number(id));
    let previous = null;
    if (idx >= 0) {
        previous = { ...alertasCache[idx] };
        alertasCache[idx].leida = true;
        renderAlertasDesdeCache();
    }
    try {
        await fetchJson(`${API_URL}/alertas/${id}/leer`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        refreshAlertBadgeAndNotify(false);
    } catch (error) {
        if (idx >= 0 && previous) {
            alertasCache[idx] = previous;
            renderAlertasDesdeCache();
        }
        alert('Error al marcar alerta: ' + error.message);
    }
}

async function desactivarAlerta(id) {
    if (!(await showAppConfirm('¿Desactivar esta alerta? Dejará de ser visible para los demás.', { title: 'Desactivar alerta', tone: 'warning', acceptText: 'Desactivar' }))) return;
    const idx = alertasCache.findIndex(a => Number(a.id) === Number(id));
    let previous = null;
    if (idx >= 0) {
        previous = { ...alertasCache[idx] };
        alertasCache[idx].es_activa = false;
        const soloActivas = document.getElementById('alertasSoloActivas')?.checked !== false;
        if (soloActivas) {
            alertasCache.splice(idx, 1);
        }
        renderAlertasDesdeCache();
    }
    try {
        await fetchJson(`${API_URL}/alertas/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        refreshAlertBadgeAndNotify(false);
    } catch (error) {
        if (previous) {
            if (idx >= 0 && idx <= alertasCache.length) {
                alertasCache.splice(idx, 0, previous);
            } else {
                alertasCache.push(previous);
            }
            renderAlertasDesdeCache();
        }
        alert('Error al desactivar alerta: ' + error.message);
    }
}
