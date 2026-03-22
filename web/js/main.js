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
let currentWeeklyReportRows = [];
let lastReceiptData = null;
let currentDatosDatabase = '';
let currentServerAccessUrl = '';
let brandingManageEnabled = false;
let currentAgentManagementRows = [];
let currentEditingAgentId = null;
let currentBackupDir = '';
let currentTableBrowserState = { database: '', table: '', orderBy: 'id', direction: 'desc', limit: 50 };
const DEFAULT_AGENT_DATABASE = 'registro_agentes';
const BRANDING_DEFAULTS = {
    appName: 'Database Manager',
    subtitle: 'database_manager',
    logoPath: 'sources/logo.png'
};

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

function setDefaultWeeklyDates() {
    const week = mondayISO();
    ['qrSemana', 'pagoSemana', 'reporteSemanaInput'].forEach(id => {
        const input = document.getElementById(id);
        if (input && !input.value) {
            input.value = week;
        }
    });
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
        throw new Error(detail);
    }

    if (response.status === 204) {
        return {};
    }

    return response.json();
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

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
    if (role === 'admin' || currentUser?.es_admin) return 'admin';
    if (role === 'capture') return 'capture';
    return 'viewer';
}

function canCapture() {
    return getCurrentRole() === 'capture' || getCurrentRole() === 'admin';
}

function canAdmin() {
    return getCurrentRole() === 'admin';
}

function canAccessSection(section) {
    const role = getCurrentRole();
    if (role === 'admin') return true;
    if (role === 'capture') {
        return ['dashboard', 'datos', 'importar', 'altasAgentes'].includes(section);
    }
    return ['dashboard', 'datos'].includes(section);
}

function applyRoleBasedUI() {
    const role = getCurrentRole();
    const roleLabel = role === 'admin' ? 'Administrador' : role === 'capture' ? 'Altas' : 'Consulta';
    const userNameEl = document.getElementById('userName');
    if (userNameEl) {
        userNameEl.textContent = `${currentUser?.username || 'Usuario'} · ${roleLabel}`;
    }

    const menuRules = {
        dashboard: true,
        datos: true,
        databases: canAdmin(),
        importar: canCapture(),
        altasAgentes: canCapture(),
        cambiosBajas: canAdmin(),
        qr: canAdmin(),
        usuarios: canAdmin(),
        auditoria: canAdmin(),
    };
    Object.entries(menuRules).forEach(([section, visible]) => {
        const item = document.querySelector(`.menu-item[onclick*="'${section}'"]`);
        if (item) {
            item.style.display = visible ? '' : 'none';
        }
    });

    const purgeBtn = document.getElementById('purgeInactiveBtn');
    if (purgeBtn) purgeBtn.style.display = canAdmin() ? '' : 'none';
    const maintenancePanel = document.getElementById('dbMaintenancePanel');
    if (maintenancePanel) maintenancePanel.style.display = canAdmin() ? 'block' : 'none';
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
    window.addEventListener('scroll', updateScrollTopButton, { passive: true });
    updateScrollTopButton();
    setDefaultWeeklyDates();
    loadBrandingConfig();
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
    const ids = ['loginSection', 'registerSection', 'dashboardSection', 'datosSection', 'databasesSection', 'importarSection', 'altasAgentesSection', 'cambiosBajasSection', 'qrSection', 'usuariosSection', 'auditoriaSection'];
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
    stopRealtimeUpdates();
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
    applyRoleBasedUI();
    cargarAccesoServidorLocal();
    cargarPermisosBrandingAdmin();
    syncRealtimeControls();
    loadSection('dashboard');
    startRealtimeUpdates();
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

        localStorage.setItem('currentUser', JSON.stringify(currentUser));

        showApp();
        loadDashboardData();
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

    try {
        await fetchJson(`${API_URL}/auth/registrar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                email,
                nombre_completo: fullName,
                password
            })
        });

        alert('Registro exitoso. Ahora inicia sesión.');
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
    showLogin();
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
    if (!valueEl || !wrapEl || !btnEl) {
        return;
    }

    valueEl.textContent = 'cargando...';
    btnEl.disabled = true;

    try {
        const res = await apiClient.getLocalNetworkInfo();
        const url = String(res.share_url || '').trim();
        const ip = String(res.ip_local || '').trim();
        currentServerAccessUrl = url;
        valueEl.textContent = url || ip || 'No disponible';
        wrapEl.title = ip ? `IP local: ${ip}` : 'Acceso local';
        btnEl.disabled = !(url || ip);
    } catch (error) {
        console.warn('No se pudo obtener IP local:', error.message);
        currentServerAccessUrl = '';
        valueEl.textContent = 'No disponible';
        wrapEl.title = 'No se pudo detectar IP local';
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
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
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
    currentSection = section;
    // Ocultar todas las secciones
    document.getElementById('dashboardSection').style.display = 'none';
    document.getElementById('datosSection').style.display = 'none';
    document.getElementById('databasesSection').style.display = 'none';
    document.getElementById('importarSection').style.display = 'none';
    document.getElementById('altasAgentesSection').style.display = 'none';
    document.getElementById('cambiosBajasSection').style.display = 'none';
    document.getElementById('qrSection').style.display = 'none';
    document.getElementById('usuariosSection').style.display = 'none';
    document.getElementById('auditoriaSection').style.display = 'none';

    // Remover clase active
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));

    switch (section) {
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
        case 'altasAgentes':
            document.getElementById('altasAgentesSection').style.display = 'block';
            cargarLineasYAgentes();
            break;
        case 'cambiosBajas':
            document.getElementById('cambiosBajasSection').style.display = 'block';
            cargarAgentesGestion();
            break;
        case 'qr':
            document.getElementById('qrSection').style.display = 'block';
            cargarCuotaSemanal();
            cargarConfiguracionRespaldos();
            cargarReporteSemanal();
            cargarRespaldos();
            cargarLineasYAgentes();
            break;
        case 'usuarios':
            document.getElementById('usuariosSection').style.display = 'block';
            cargarUsuarios();
            break;
        case 'auditoria':
            document.getElementById('auditoriaSection').style.display = 'block';
            cargarAuditoria();
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

function isAgentDataTableContext(dbName, tableName) {
    return tableName === 'datos_importados' && (dbName === DEFAULT_AGENT_DATABASE || dbName === 'database_manager');
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
                    return `<div class="dashboard-item">
                        <strong>${escapeHtml(agent.nombre || 'Agente')}</strong>
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
    } catch (error) {
        if (showErrors) {
            console.error('Error:', error);
        }
    }
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
            html += `<option value="${t}">${t}</option>`;
        });
        tableSelect.innerHTML = html;

        if (prevTable && tables.includes(prevTable)) {
            tableSelect.value = prevTable;
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

async function cargarTodosLosDatos() {
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
        if (search) {
            const s = search.toLowerCase();
            rows = rows.filter(row => Object.values(row).some(v => String(v ?? '').toLowerCase().includes(s)));
        }
        mostrarDatos(rows);
        alert(`Mostrando ${rows.length} registros de ${dbName}.${tableName}`);
    } catch (error) {
        console.error('Error:', error);
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
        if (tableName === 'datos_importados' && registro.id && registro.qr_filename) {
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
        
        // Crear modal o panel para mostrar el QR
        const modal = document.createElement('div');
        modal.className = 'modal-overlay-qr';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.3s ease-in;
        `;
        
        const content = document.createElement('div');
        content.className = 'modal-content-qr';
        content.style.cssText = `
            background: white;
            border-radius: 12px;
            padding: 30px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            position: relative;
            animation: slideUp 0.3s ease-out;
        `;
        
        content.innerHTML = `
            <button type="button" class="close-modal-qr" onclick="this.closest('.modal-overlay-qr').remove()" 
                    style="position: absolute; top: 12px; right: 12px; background: none; border: none; font-size: 28px; cursor: pointer; color: #999;">
                ✕
            </button>
            <h2 style="margin-top: 0; color: #333; text-align: center;">QR del Agente</h2>
            <p style="text-align: center; color: #666; margin: 10px 0;">
                <strong>${agenteName}</strong><br>
                <span style="font-size: 0.9em; color: #999;">ID: ${agenteId}</span>
            </p>
            <div id="qr-preview-container" style="text-align: center; margin: 20px 0; padding: 20px; background: #f9f9f9; border-radius: 8px;"></div>
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                <button type="button" class="btn btn-secondary" onclick="descargarQrAgente(${agenteId})">
                    📥 Descargar PNG
                </button>
                <button type="button" class="btn" onclick="navigator.clipboard.writeText('${data.public_url}'); alert('URL copiada');">
                    📋 Copiar URL
                </button>
            </div>
            <p style="text-align: center; font-size: 0.85em; color: #999; margin-top: 15px;">
                ${data.public_url ? `<a href="${data.public_url}" target="_blank" style="color: #0066cc; text-decoration: none;">Abrir en navegador ↗</a>` : 'URL no disponible'}
            </p>
        `;
        
        modal.appendChild(content);
        document.body.appendChild(modal);
        
        // Renderizar QR en el contenedor
        renderSimpleQR(data.public_url, 'qr-preview-container');
        
    } catch (error) {
        console.error('Error mostrando QR:', error);
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
    const isAgentTable = tableName === 'datos_importados' || tableName === 'registro_agentes';
    
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
                actionHtml += `<button onclick="editarDato(${fila.id})" class="btn btn-small" title="Editar registro">✏️ Editar</button>`;
            }
            
            // Si es agente y tiene QR, mostrar botón para verlo
            if (isAgentTable) {
                if (hasQr) {
                    actionHtml += `<button onclick="mostrarQrParaAgente(${fila.id}, '${(fila.nombre || 'Agente').replace(/'/g, "\\'")}'); return false;" class="btn btn-small btn-secondary" title="${qrTitle}"><span title="${qrTitle}">${qrIndicator}</span> QR</button>`;
                } else {
                    actionHtml += `<button onclick="previsualizarQrAlta(${fila.id})" class="btn btn-small btn-secondary" title="Generar QR">⭕ QR</button>`;
                }
            }
            
            if (canAdmin()) {
                actionHtml += `<button onclick="eliminarDato(${fila.id})" class="btn btn-small" title="Eliminar registro">🗑️</button>`;
                actionHtml += `<button onclick="eliminarDatoDefinitivo(${fila.id})" class="btn btn-small btn-danger" title="Eliminar definitivamente">🔥</button>`;
            }
            actionHtml += `</td></tr>`;
            html += actionHtml;
        } else {
            html += `<td><span class="hint">Solo lectura</span></td></tr>`;
        }
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

async function editarDato(id) {
    if (!canAdmin()) {
        alert('Solo administradores pueden editar registros existentes.');
        return;
    }
    const nuevoValor = prompt('Nuevo valor:');
    if (!nuevoValor) return;

    try {
        const response = await fetch(`${API_URL}/datos/${id}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nombre: nuevoValor })
        });

        if (response.ok) {
            alert('Dato actualizado');
            buscarDatos();
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function eliminarDatoDefinitivo(id) {
    if (!canAdmin()) {
        alert('Solo administradores pueden eliminar definitivamente.');
        return;
    }
    if (!confirm('Esto eliminará el registro y sus dependencias de forma permanente. ¿Continuar?')) return;
    try {
        await apiClient.hardDeleteDato(id);
        alert('Registro eliminado definitivamente.');
        cargarTodosLosDatos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error eliminando definitivamente: ' + error.message);
    }
}

async function purgarDatosInactivos() {
    if (!canAdmin()) {
        alert('Solo administradores pueden purgar registros.');
        return;
    }
    if (!confirm('Se eliminarán definitivamente todos los registros inactivos. ¿Continuar?')) return;
    try {
        const result = await apiClient.purgeInactiveDatos();
        alert(result.mensaje || 'Purgado completado.');
        cargarTodosLosDatos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error purgando inactivos: ' + error.message);
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
            box.innerHTML = `
                <div class="card" style="padding:12px;border:1px solid #d8d8d8;border-radius:8px;">
                    <strong>QR individual generado para:</strong> ${data.nombre || 'Agente'}<br>
                    <strong>Asignación:</strong> ${data.tiene_asignacion ? 'Con número asignado' : 'Sin número asignado'}<br>
                    <strong>URL pública:</strong> <a href="${data.public_url}" target="_blank">Abrir verificación</a><br>
                    <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
                        <button type="button" class="btn btn-secondary" onclick="descargarQrAgente(${agenteId})">Descargar PNG</button>
                        <button type="button" class="btn" onclick="navigator.clipboard.writeText('${data.public_url}')">Copiar URL</button>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error generando QR individual: ' + error.message);
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

async function leerCodigoManual() {
    const input = document.getElementById('codigoEscaneadoManual');
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

async function iniciarEscanerQR() {
    if (typeof Html5Qrcode === 'undefined') {
        alert('Librería de escaneo no disponible.');
        return;
    }
    if (qrScannerInstance) {
        return;
    }

    qrScannerInstance = new Html5Qrcode('qrScanner');
    try {
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

        await qrScannerInstance.start(
            { facingMode: 'environment' },
            {
                fps: 10,
                qrbox: { width: 240, height: 240 },
                formatsToSupport: formats,
            },
            async (decodedText) => {
                await manejarQRLeido(decodedText);
            },
            () => {}
        );
    } catch (error) {
        qrScannerInstance = null;
        alert('No se pudo iniciar la cámara: ' + error.message);
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
}

async function manejarQRLeido(decodedText) {
    await detenerEscanerQR();
    const week = document.getElementById('qrSemana').value;

    try {
        const result = await apiClient.verificarCodigoEscaneado(decodedText, week);
        const agente = result.agente || {};
        document.getElementById('qrAgenteId').value = agente.id || '';
        document.getElementById('qrTelefono').value = agente.telefono || '';
        document.getElementById('qrVoip').value = agente.numero_voip || '';
        await verificarAgenteQR();
    } catch (error) {
        console.error('Error de escaneo:', error);
        alert('No se pudo validar el código escaneado: ' + error.message);
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
    html += '<th>ID</th><th>Línea</th><th>Lada</th><th>Tipo</th><th>Estado</th><th>Agente</th><th>Acciones</th>';
    html += '</tr></thead><tbody>';

    lineas.forEach(linea => {
        const ocupada = !!linea.ocupada;
        const agente = linea.agente?.nombre ? `${linea.agente.nombre} (ID ${linea.agente.id})` : '-';
        const estado = ocupada ? '<span class="payment-pill unpaid">OCUPADA</span>' : '<span class="payment-pill paid">LIBRE</span>';
        const action = ocupada
            ? `<button class="btn btn-small btn-danger" onclick="liberarLinea(${linea.id})">Liberar</button>`
            : '<span class="hint">Disponible</span>';
        html += `<tr>
            <td>${linea.id}</td>
            <td>${linea.numero}</td>
            <td>${linea.lada || '-'}</td>
            <td>${linea.tipo || '-'}</td>
            <td>${estado}</td>
            <td>${agente}</td>
            <td>${action}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
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

function renderGestionAgentes(agentes) {
    const container = document.getElementById('gestionAgentesContainer');
    if (!container) return;
    if (!agentes.length) {
        container.innerHTML = '<p>No hay agentes activos que coincidan con la búsqueda.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr>';
    html += '<th>ID</th><th>Nombre</th><th>Alias</th><th>Teléfono</th><th>Líneas</th><th>Ladas</th><th>Acciones</th>';
    html += '</tr></thead><tbody>';

    agentes.forEach(agent => {
        const extras = getAgentExtras(agent);
        const lines = Array.isArray(agent.lineas) ? agent.lineas : [];
        const lineText = lines.length ? lines.map(line => `${line.numero} (${line.tipo || 'N/A'})`).join(', ') : 'Sin líneas';
        const ladas = Array.isArray(agent.ladas_preferidas) && agent.ladas_preferidas.length ? agent.ladas_preferidas.join(', ') : '-';
        html += `<tr>
            <td>${agent.id}</td>
            <td>${agent.nombre || '-'}</td>
            <td>${extras.alias || '-'}</td>
            <td>${agent.telefono || '-'}</td>
            <td>${lineText}</td>
            <td>${ladas}</td>
            <td>
                <button onclick="editarAgenteGestion(${agent.id})" class="btn btn-small">Editar</button>
                <button onclick="previsualizarQrGestion(${agent.id})" class="btn btn-small btn-secondary">QR</button>
                <button onclick="liberarLineasAgente(${agent.id})" class="btn btn-small btn-secondary">Liberar líneas</button>
                <button onclick="darBajaAgente(${agent.id})" class="btn btn-small btn-danger">Baja</button>
            </td>
        </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

async function cargarAgentesGestion(showErrors = true) {
    try {
        const search = document.getElementById('gestionAgenteSearch')?.value.trim() || '';
        const res = await apiClient.getAgentesQR(search);
        currentAgentManagementRows = res.data || [];
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
        nombre: document.getElementById('editarAgenteNombre')?.value.trim() || null,
        telefono: document.getElementById('editarAgenteTelefono')?.value.trim() || null,
        datos_adicionales: {
            ...extras,
            alias: document.getElementById('editarAgenteAlias')?.value.trim() || null,
            ubicacion: document.getElementById('editarAgenteUbicacion')?.value.trim() || null,
            fp: document.getElementById('editarAgenteFp')?.value.trim() || null,
            fc: document.getElementById('editarAgenteFc')?.value.trim() || null,
            grupo: document.getElementById('editarAgenteGrupo')?.value.trim() || null,
            numero_voip: document.getElementById('editarAgenteVoip')?.value.trim() || null,
        }
    };

    if (!payload.nombre) {
        alert('El nombre del agente es obligatorio.');
        return;
    }

    payload.datos_adicionales = Object.fromEntries(Object.entries(payload.datos_adicionales).filter(([, value]) => value !== null && value !== ''));

    try {
        await apiClient.actualizarDato(agenteId, payload);
        alert('Agente actualizado correctamente.');
        resetGestionAgentePanel();
        await cargarAgentesGestion(false);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error guardando cambios: ' + error.message);
    }
}

async function liberarLineasAgente(agenteId) {
    const agent = currentAgentManagementRows.find(item => Number(item.id) === Number(agenteId));
    const lines = Array.isArray(agent?.lineas) ? agent.lineas : [];
    if (!lines.length) {
        alert('Este agente no tiene líneas asignadas.');
        return;
    }
    if (!confirm(`¿Liberar ${lines.length} línea(s) del agente ${agent.nombre || agenteId}?`)) return;

    try {
        for (const line of lines) {
            await apiClient.liberarLinea(line.id, agenteId);
        }
        alert('Líneas liberadas correctamente.');
        await cargarAgentesGestion(false);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error liberando líneas: ' + error.message);
    }
}

async function darBajaAgente(agenteId) {
    const agent = currentAgentManagementRows.find(item => Number(item.id) === Number(agenteId));
    const label = agent?.nombre || `ID ${agenteId}`;
    if (!confirm(`¿Dar de baja al agente ${label}?`)) return;
    if ((agent?.lineas || []).length && !confirm('El agente tiene líneas asignadas. La baja no las libera automáticamente. ¿Continuar?')) return;

    try {
        await apiClient.eliminarDato(agenteId);
        alert('Agente dado de baja correctamente.');
        if (currentEditingAgentId === Number(agenteId)) {
            resetGestionAgentePanel();
        }
        await cargarAgentesGestion(false);
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error dando de baja al agente: ' + error.message);
    }
}

async function cargarLineasYAgentes() {
    try {
        const lada = (document.getElementById('lineasLadaFilter')?.value || '').trim();
        const [lineasRes, agentesRes] = await Promise.all([
            apiClient.getLineas('', false, lada),
            apiClient.getAgentesQR('')
        ]);

        const lineas = lineasRes.data || [];
        const agentes = agentesRes.data || [];
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
                html += `<option value="${a.id}">${a.nombre || 'Agente'} (ID ${a.id})</option>`;
            });
            agenteSelect.innerHTML = html;
        }

        renderLineasEstado(lineas);
        cambiarModoAsignacionAgente();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando agentes y líneas: ' + error.message);
    }
}

function cambiarModoAsignacionAgente() {
    const modo = document.getElementById('agenteModoAsignacion')?.value || 'ninguna';
    const selectManual = document.getElementById('agenteLineaManualSelect');
    const inputManual = document.getElementById('agenteLineaManualInput');
    if (!selectManual || !inputManual) return;

    const showManual = modo === 'manual';
    selectManual.style.display = showManual ? 'inline-block' : 'none';
    inputManual.style.display = showManual ? 'inline-block' : 'none';
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
        nombre: document.getElementById('agenteNombreInput')?.value.trim(),
        alias: document.getElementById('agenteAliasInput')?.value.trim() || null,
        ubicacion: document.getElementById('agenteUbicacionInput')?.value.trim() || null,
        telefono: document.getElementById('agenteTelefonoInput')?.value.trim() || null,
        fp: document.getElementById('agenteFpInput')?.value.trim() || null,
        fc: document.getElementById('agenteFcInput')?.value.trim() || null,
        grupo: document.getElementById('agenteGrupoInput')?.value.trim() || null,
        modo_asignacion: modo,
        lada_objetivo: document.getElementById('agenteLadaObjetivoSelect')?.value || null
    };

    if (!payload.nombre) {
        alert('El nombre del agente es obligatorio.');
        return;
    }

    if (modo === 'manual') {
        payload.linea_id = Number(document.getElementById('agenteLineaManualSelect')?.value || 0) || null;
        payload.numero_linea_manual = document.getElementById('agenteLineaManualInput')?.value.trim() || null;
        if (!payload.linea_id && !payload.numero_linea_manual) {
            alert('Para modo manual selecciona una línea o escribe un número nuevo.');
            return;
        }
    }

    try {
        const result = await apiClient.crearAgenteManual(payload);
        const data = result.data || {};
        document.getElementById('qrAgenteId').value = data.agente_id || '';
        document.getElementById('qrTelefono').value = payload.telefono || '';
        const asignacion = data.asignacion || {};
        const lineaText = asignacion.asignada ? `Línea ${asignacion.linea_numero} asignada.` : 'Sin asignación inicial.';
        alert(`Agente creado (ID ${data.agente_id}). ${lineaText}`);

        [
            'agenteNombreInput',
            'agenteAliasInput',
            'agenteUbicacionInput',
            'agenteTelefonoInput',
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

async function crearLineaTelefonica(e) {
    e.preventDefault();
    const numero = document.getElementById('lineaNumeroInput')?.value.trim();
    const tipo = (document.getElementById('lineaTipoInput')?.value || 'VOIP').trim();
    const descripcion = document.getElementById('lineaDescripcionInput')?.value.trim() || '';
    if (!numero) {
        alert('Ingresa un número de línea.');
        return;
    }

    try {
        await apiClient.crearLinea({ numero, tipo, descripcion });
        alert('Línea creada/reactivada correctamente.');
        document.getElementById('lineaNumeroInput').value = '';
        document.getElementById('lineaDescripcionInput').value = '';
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error creando línea: ' + error.message);
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
        await apiClient.asignarLinea(lineaId, agenteId);
        alert('Línea asignada correctamente.');
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error asignando línea: ' + error.message);
    }
}

async function liberarLinea(lineaId) {
    if (!confirm('¿Liberar esta línea?')) return;
    try {
        await apiClient.liberarLinea(lineaId);
        alert('Línea liberada.');
        await cargarLineasYAgentes();
    } catch (error) {
        console.error('Error:', error);
        alert('Error liberando línea: ' + error.message);
    }
}

async function eliminarDato(id) {
    if (!confirm('¿Estás seguro?')) return;

    try {
        const response = await fetch(`${API_URL}/datos/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        if (response.ok) {
            alert('Dato eliminado');
            buscarDatos();
        }
    } catch (error) {
        console.error('Error:', error);
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
    document.getElementById('pagoMonto').value = Number(verificacion.cuota_semanal || verificacion.monto || 300);
    document.getElementById('pagoPagado').checked = true;
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

    const telefono = document.getElementById('qrTelefono').value.trim();
    const voip = document.getElementById('qrVoip').value.trim();
    const semana = document.getElementById('qrSemana').value;

    try {
        const result = await apiClient.verificarAgenteQR(agenteId, telefono, voip, semana);
        const v = result.verificacion || {};
        const a = result.agente || {};
        const box = document.getElementById('qrVerificationResult');
        currentVerificationData = { agente: a, verificacion: v };
        const paidClass = v.pagado ? 'payment-status paid' : 'payment-status unpaid';
        const paidText = v.pagado ? 'PAGADO' : 'PENDIENTE';
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
    const payload = {
        agente_id: Number(document.getElementById('pagoAgenteId').value),
        telefono: document.getElementById('pagoTelefono').value.trim(),
        numero_voip: document.getElementById('pagoVoip').value.trim() || null,
        semana_inicio: document.getElementById('pagoSemana').value,
        monto: Number(document.getElementById('pagoMonto').value || 0),
        pagado: document.getElementById('pagoPagado').checked,
        observaciones: null
    };

    try {
        const pago = await apiClient.registrarPagoSemanal(payload);
        lastReceiptData = {
            agente_id: payload.agente_id,
            nombre: currentVerificationData?.agente?.nombre || `Agente ${payload.agente_id}`,
            telefono: payload.telefono,
            numero_voip: payload.numero_voip,
            semana_inicio: payload.semana_inicio,
            monto: Number(pago.monto ?? payload.monto ?? 0),
            fecha_pago: pago.fecha_pago || new Date().toISOString(),
            estado: payload.pagado ? 'PAGADO' : 'PENDIENTE'
        };
        renderReciboPago(lastReceiptData);
        alert('Pago semanal guardado correctamente.');
        if (document.getElementById('qrAgenteId').value === String(payload.agente_id)) {
            await verificarAgenteQR();
        }
        cargarReporteSemanal();
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
            <p><strong>Semana:</strong> ${data.semana_inicio || '-'}</p>
            <p><strong>Monto:</strong> $${Number(data.monto || 0).toFixed(2)} MXN</p>
            <p><strong>Fecha de pago:</strong> ${data.fecha_pago ? new Date(data.fecha_pago).toLocaleString() : '-'}</p>
            <p><strong>Estado:</strong> ${data.estado || 'PAGADO'}</p>
            <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                <button type="button" class="btn" onclick="imprimirReciboPago()">Imprimir Comprobante</button>
            </div>
        </div>
    `;
}

function imprimirReciboPago() {
    if (!lastReceiptData) {
        alert('No hay comprobante para imprimir.');
        return;
    }
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
                <p><strong>Agente:</strong> ${lastReceiptData.nombre || ''}</p>
                <p><strong>ID:</strong> ${lastReceiptData.agente_id || ''}</p>
                <p><strong>Teléfono:</strong> ${lastReceiptData.telefono || '-'}</p>
                <p><strong>VoIP:</strong> ${lastReceiptData.numero_voip || '-'}</p>
                <p><strong>Semana:</strong> ${lastReceiptData.semana_inicio || '-'}</p>
                <p><strong>Monto:</strong> $${Number(lastReceiptData.monto || 0).toFixed(2)} MXN</p>
                <p><strong>Fecha de pago:</strong> ${lastReceiptData.fecha_pago ? new Date(lastReceiptData.fecha_pago).toLocaleString() : '-'}</p>
                <p><strong>Estado:</strong> ${lastReceiptData.estado || 'PAGADO'}</p>
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

function generarReciboDesdeReporte(index) {
    const row = currentWeeklyReportRows[index];
    if (!row) return;
    lastReceiptData = {
        agente_id: row.agente_id,
        nombre: row.nombre,
        telefono: row.telefono,
        numero_voip: row.numero_voip || '',
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
        const cuota = Number(reporte.cuota_semanal || 300).toFixed(2);
        const tot = reporte.totales || { agentes: 0, pagados: 0, pendientes: 0 };

        resumen.innerHTML = `
            <div class="card" style="padding:12px;border:1px solid #d8d8d8;border-radius:8px;">
                <strong>Semana:</strong> ${reporte.semana_inicio}<br>
                <strong>Cuota vigente:</strong> $${cuota} MXN<br>
                <strong>Agentes:</strong> ${tot.agentes} |
                <strong>Pagados:</strong> ${tot.pagados} |
                <strong>Pendientes:</strong> ${tot.pendientes}
            </div>
        `;

        const filas = reporte.data || [];
        currentWeeklyReportRows = filas;
        if (filas.length === 0) {
            container.innerHTML = '<p>No hay agentes activos para esta semana.</p>';
        } else {
            let html = '<table class="data-table"><thead><tr>';
            html += '<th>ID</th><th>Nombre</th><th>Telefono</th><th>Pagado</th><th>Monto</th><th>Saldo</th><th>Alerta</th>';
            html += '</tr></thead><tbody>';
            filas.forEach((f, index) => {
                html += `<tr>
                    <td>${f.agente_id}</td>
                    <td>${f.nombre || ''}</td>
                    <td>${f.telefono || ''}</td>
                    <td>${f.pagado ? 'SI' : 'NO'}</td>
                    <td>$${Number(f.monto_pagado || 0).toFixed(2)}</td>
                    <td>$${Number(f.saldo || 0).toFixed(2)}</td>
                    <td>${f.alerta_emitida ? (f.alerta_atendida ? 'Atendida' : 'Pendiente') : 'Sin alerta'}<br><div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px"><button onclick="generarQrIndividual(${f.agente_id})" class="btn btn-small btn-secondary">Ver QR</button><button onclick="generarReciboDesdeReporte(${index})" class="btn btn-small">Recibo</button></div></td>
                </tr>`;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        }

        cargarAlertasPago();
        cargarRespaldos();
    } catch (error) {
        console.error('Error:', error);
        alert('Error cargando reporte semanal: ' + error.message);
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
    if (!confirm(`¿Restaurar el respaldo ${filename}? Esta acción reemplazará la base actual.`)) return;
    if (!confirm('Confirma nuevamente la restauración. Se hará un respaldo de rescate antes de continuar.')) return;
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

    const semana = document.getElementById('qrSemana').value;
    const verifyUrl = `${window.location.origin}/api/qr/public/verify-by-id/${encodeURIComponent(String(agenteId))}${semana ? `?semana=${encodeURIComponent(semana)}` : ''}`;
    renderSimpleQR(verifyUrl);
    alert('QR de verificación generado. Al escanearlo, consulta estado de pago de la semana.');
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
    if (!confirm(`¿Eliminar permanentemente la base de datos "${name}"?\nEsta acción borrará todos sus datos y no se puede deshacer.`)) return;
    if (!confirm(`Segunda confirmación: ¿continuar con la eliminación de "${name}"?`)) return;
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
                <td>${table}</td>
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
    if (!confirm(`Se eliminarán tablas de prueba en ${database} con prefijos tmp_, temp_, test_, ui_temp_ o debug_. ¿Continuar?`)) {
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
                <td>${view}</td>
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
    const viewName = prompt('Nombre de la vista: (solo letras, números y _)');
    if (!viewName) return;
    const selectQuery = prompt('Consulta SELECT para la vista:');
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
    if (!confirm(`¿Eliminar la vista ${viewName}?`)) return;
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
    if (!confirm('Se eliminarán objetos temporales o de prueba detectados automáticamente. ¿Continuar?')) return;
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
    
    let html = `<h3>Datos de ${table} en ${database}</h3>`;
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
    if (!confirm(`¿Estás seguro de eliminar la tabla ${table}?`)) {
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

// === GESTIÓN DE USUARIOS ===
async function cargarUsuarios() {
    try {
        const orderBy = document.getElementById('usuariosOrderBy')?.value || 'fecha_creacion';
        const direction = document.getElementById('usuariosOrderDir')?.value || 'desc';
        const usuarios = await apiClient.getUsuarios(orderBy, direction);
        mostrarUsuarios(usuarios);
        if (canAdmin()) {
            cargarMantenimientoUsuarios(false);
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
                    <th>Activo</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    usuarios.forEach(user => {
        html += `
            <tr>
                <td>${user.id}</td>
                <td>${user.username}</td>
                <td>${user.email}</td>
                <td>${user.nombre_completo || ''}</td>
                <td>${user.rol || (user.es_admin ? 'admin' : 'viewer')}</td>
                <td>${user.es_activo ? 'Sí' : 'No'}</td>
                <td>
                    <button onclick="editarUsuario(${user.id})" class="btn btn-small">Editar</button>
                    <button onclick="cambiarPassword(${user.id})" class="btn btn-small btn-secondary">Contraseña</button>
                    <button onclick="eliminarUsuario(${user.id}, false)" class="btn btn-small btn-danger">Desactivar</button>
                    <button onclick="eliminarUsuario(${user.id}, true)" class="btn btn-small btn-danger">Eliminar Definitivo</button>
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
    if (!confirm('Se eliminarán definitivamente usuarios temporales/obsoletos (excepto admins). ¿Continuar?')) return;
    try {
        const result = await apiClient.purgeTemporaryUsuarios(true);
        alert(`Depuración completada. Eliminados: ${result.count || 0}`);
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error depurando usuarios temporales: ' + error.message);
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
        es_admin: role === 'admin',
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
    const newPassword = prompt('Ingresa la nueva contraseña:');
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
    if (!confirm(message)) return;
    
    try {
        await apiClient.eliminarUsuario(userId, hardDelete);
        alert(hardDelete ? 'Usuario eliminado definitivamente' : 'Usuario desactivado');
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al eliminar usuario: ' + error.message);
    }
}
