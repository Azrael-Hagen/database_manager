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
    document.getElementById('userName').textContent = currentUser?.username || 'Usuario';
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
        const datos = await fetchJson(`${API_URL}/datos?pagina=1&por_pagina=1`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        document.getElementById('totalRegistros').textContent = datos.total || 0;
        document.getElementById('totalImportaciones').textContent = '0';
        document.getElementById('totalQR').textContent = '0';
        try {
            const usuarios = await apiClient.getUsuarios();
            document.getElementById('totalUsuarios').textContent = usuarios.length || 0;
        } catch (_) {
            document.getElementById('totalUsuarios').textContent = 'N/A';
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
        const data = await apiClient.getTableData(dbName, tableName, 500);
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
        mostrarDatos(rows);
    } catch (error) {
        console.error('Error:', error);
        alert('No se encontró el registro: ' + error.message);
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

        const data = await apiClient.getTableData(dbName, tableName, 500);
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
        container.innerHTML = '<p>No hay datos disponibles</p>';
        return;
    }

    const columnas = Object.keys(datos[0]);
    const dbName = document.getElementById('datosDatabaseSelect')?.value || '';
    const tableName = document.getElementById('tablasSelect')?.value || '';
    const editableContext = isAgentDataTableContext(dbName, tableName);
    let html = '<table class="data-table"><thead><tr>';

    columnas.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '<th>Acciones</th></tr></thead><tbody>';

    datos.forEach(fila => {
        html += '<tr>';
        columnas.forEach(col => {
            html += `<td>${fila[col] ?? ''}</td>`;
        });
        if (editableContext && Number.isFinite(Number(fila.id))) {
            html += `<td>
                <button onclick="editarDato(${fila.id})" class="btn btn-small">Editar</button>
                <button onclick="generarQrIndividual(${fila.id})" class="btn btn-small btn-secondary">QR</button>
                <button onclick="eliminarDato(${fila.id})" class="btn btn-small">Eliminar</button>
            </td></tr>`;
        } else {
            html += '<td><span class="hint">Solo lectura</span></td></tr>';
        }
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

async function editarDato(id) {
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
        renderSimpleQR(data.public_url, qrContainerId);
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
        'editarAgenteEmpresa',
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
    html += '<th>ID</th><th>Nombre</th><th>Alias</th><th>Teléfono</th><th>Empresa</th><th>Líneas</th><th>Ladas</th><th>Acciones</th>';
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
            <td>${agent.empresa || '-'}</td>
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
    document.getElementById('editarAgenteEmpresa').value = agent.empresa || '';
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
        empresa: document.getElementById('editarAgenteEmpresa')?.value.trim() || null,
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
        empresa: document.getElementById('agenteEmpresaInput')?.value.trim() || null,
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
            'agenteEmpresaInput',
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
        // Usar librería QRCode.js (se debe agregar en HTML)
        const container = document.getElementById('qrContainer');
        container.innerHTML = '';
        
        const qr = new QRCode(container, {
            text: contenido,
            width: 200,
            height: 200,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H
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
    if (!container) return;
    container.innerHTML = '';
    // QRCode global from qrcode.js loaded in index.html
    new QRCode(container, {
        text,
        width: 220,
        height: 220,
        colorDark: '#000000',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.H
    });
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
            estado: payload.pagado ? 'PAGADO' : 'PENDIENTE',
            empresa: currentVerificationData?.agente?.empresa || ''
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
            <p><strong>Empresa:</strong> ${data.empresa || '-'}</p>
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
                <p><strong>Empresa:</strong> ${lastReceiptData.empresa || '-'}</p>
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
        estado: row.pagado ? 'PAGADO' : 'PENDIENTE',
        empresa: row.empresa || ''
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
    const empresa = document.getElementById('reporteEmpresaInput')?.value.trim() || '';
    try {
        const reporte = await apiClient.getReporteSemanal(semana, agente, empresa);
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
            html += '<th>ID</th><th>Nombre</th><th>Telefono</th><th>Empresa</th><th>Pagado</th><th>Monto</th><th>Saldo</th><th>Alerta</th>';
            html += '</tr></thead><tbody>';
            filas.forEach((f, index) => {
                html += `<tr>
                    <td>${f.agente_id}</td>
                    <td>${f.nombre || ''}</td>
                    <td>${f.telefono || ''}</td>
                    <td>${f.empresa || ''}</td>
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
                <button onclick="abrirImportBD('${db}')" class="btn btn-small">Importar</button>
                <button onclick="abrirQueryPanel('${db}')" class="btn btn-small btn-secondary">Query</button>
                <button onclick="ocultarDatabase('${db}')" class="btn btn-small btn-secondary">Ocultar</button>
                <button onclick="eliminarDatabase('${db}')" class="btn btn-small btn-danger">Eliminar</button>`;
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
    
    let html = `<div style="margin-bottom:12px">
        <button onclick="cargarDatabases()" class="btn btn-secondary btn-small">← Bases de Datos</button>
        <button onclick="abrirImportBD('${database}')" class="btn btn-small" style="margin-left:8px">Importar archivo</button>
        <button onclick="verVistas('${database}')" class="btn btn-small btn-secondary" style="margin-left:8px">Vistas</button>
        <button onclick="crearVistaTemporal('${database}')" class="btn btn-small btn-secondary" style="margin-left:8px">Crear Vista</button>
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
                    <button onclick="abrirImportBD('${database}', '${table}')" class="btn btn-small">Importar</button>
                    <button onclick="eliminarTabla('${database}', '${table}')" class="btn btn-small btn-danger">Eliminar</button>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
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
        let html = `<div style="margin-bottom:12px">
            <button onclick="verTablas('${database}')" class="btn btn-secondary btn-small">← Tablas</button>
            <button onclick="crearVistaTemporal('${database}')" class="btn btn-small" style="margin-left:8px">Crear Vista</button>
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
                    <button onclick="eliminarVista('${database}', '${view}')" class="btn btn-small btn-danger">Eliminar</button>
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
        const data = await apiClient.getTableData(database, table, 50);
        
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

function mostrarDatosTabla(database, table, data) {
    const container = document.getElementById('databasesContainer');
    
    let html = `<h3>Datos de ${table} en ${database}</h3>`;
    html += `<p>Total de registros: ${data.total}</p>`;
    
    if (data.data.length === 0) {
        html += '<p>No hay datos</p>';
        container.innerHTML = html;
        return;
    }
    
    html += '<table class="data-table"><thead><tr>';
    data.columns.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    data.data.forEach(row => {
        html += '<tr>';
        data.columns.forEach(col => {
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
        const usuarios = await apiClient.getUsuarios();
        mostrarUsuarios(usuarios);
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
                    <th>Admin</th>
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
                <td>${user.es_admin ? 'Sí' : 'No'}</td>
                <td>${user.es_activo ? 'Sí' : 'No'}</td>
                <td>
                    <button onclick="editarUsuario(${user.id})" class="btn btn-small">Editar</button>
                    <button onclick="cambiarPassword(${user.id})" class="btn btn-small btn-secondary">Contraseña</button>
                    <button onclick="eliminarUsuario(${user.id})" class="btn btn-small btn-danger">Eliminar</button>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

function mostrarCrearUsuario() {
    document.getElementById('usuarioId').value = '';
    document.getElementById('usuarioUsername').value = '';
    document.getElementById('usuarioEmail').value = '';
    document.getElementById('usuarioNombreCompleto').value = '';
    document.getElementById('usuarioPassword').value = '';
    document.getElementById('usuarioEsAdmin').checked = false;
    document.getElementById('usuarioEsActivo').checked = true;
    document.getElementById('passwordGroup').style.display = 'block';
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
        document.getElementById('usuarioEsAdmin').checked = user.es_admin;
        document.getElementById('usuarioEsActivo').checked = user.es_activo;
        document.getElementById('passwordGroup').style.display = 'none';
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
    const userData = {
        username: document.getElementById('usuarioUsername').value,
        email: document.getElementById('usuarioEmail').value,
        nombre_completo: document.getElementById('usuarioNombreCompleto').value,
        es_admin: document.getElementById('usuarioEsAdmin').checked,
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

async function eliminarUsuario(userId) {
    if (!confirm('¿Estás seguro de eliminar este usuario?')) return;
    
    try {
        await apiClient.eliminarUsuario(userId);
        alert('Usuario eliminado');
        cargarUsuarios();
    } catch (error) {
        console.error('Error:', error);
        alert('Error al eliminar usuario: ' + error.message);
    }
}
