// === CONFIGURACIÓN GLOBAL ===
const API_URL = 'http://localhost:8000/api';
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
});

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
    const ids = ['loginSection', 'registerSection', 'dashboardSection', 'datosSection', 'databasesSection', 'importarSection', 'qrSection', 'usuariosSection', 'auditoriaSection'];
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
    stopRealtimeUpdates();
    showLogin();
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
            cargarTablas();
            break;
        case 'databases':
            document.getElementById('databasesSection').style.display = 'block';
            cargarDatabases();
            break;
        case 'importar':
            document.getElementById('importarSection').style.display = 'block';
            break;
        case 'qr':
            document.getElementById('qrSection').style.display = 'block';
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
async function cargarTablas() {
    try {
        const data = await fetchJson(`${API_URL}/datos?pagina=1&por_pagina=100`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        mostrarDatos(data.data || []);
    } catch (error) {
        console.error('Error:', error);
    }
}

async function cargarTodosLosDatos() {
    try {
        const search = document.getElementById('searchInput').value.trim();
        const data = await apiClient.getDatosTodos(search);
        mostrarDatos(data.data || []);
        alert(`Mostrando ${data.total || (data.data || []).length} registros activos.`);
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
        const dato = /^\d+$/.test(value)
            ? await apiClient.getDato(Number(value))
            : await apiClient.getDatoByUUID(value);
        mostrarDatos([dato]);
    } catch (error) {
        console.error('Error:', error);
        alert('No se encontró el registro: ' + error.message);
    }
}

async function buscarDatos() {
    const search = document.getElementById('searchInput').value;
    try {
        const url = search
            ? `${API_URL}/datos?buscar=${encodeURIComponent(search)}&pagina=1&por_pagina=100`
            : `${API_URL}/datos?pagina=1&por_pagina=100`;

        const data = await fetchJson(url, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        mostrarDatos(data.data || []);
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
        html += `<td>
            <button onclick="editarDato(${fila.id})" class="btn btn-small">Editar</button>
            <button onclick="eliminarDato(${fila.id})" class="btn btn-small">Eliminar</button>
        </td></tr>`;
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
    buscarDatos();
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

function renderSimpleQR(text) {
    const container = document.getElementById('qrContainer');
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

        box.innerHTML = `
            <div class="card" style="padding:12px;border:1px solid #d8d8d8;border-radius:8px;">
                <strong>Agente:</strong> ${a.nombre || '-'} (ID ${a.id || '-'})<br>
                <strong>Teléfono:</strong> ${a.telefono || '-'}<br>
                <strong>VoIP:</strong> ${a.numero_voip || '-'}<br>
                <strong>Asignación válida:</strong> ${v.asignacion_valida ? 'SI' : 'NO'}<br>
                <strong>Pagado:</strong> ${v.pagado ? 'SI' : 'NO'}<br>
                <strong>Monto:</strong> ${v.monto ?? 0}
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
        await apiClient.registrarPagoSemanal(payload);
        alert('Pago semanal guardado correctamente.');
    } catch (error) {
        console.error('Error:', error);
        alert('Error guardando pago: ' + error.message);
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
    databases.filter(db => !hiddenDatabases.includes(db)).forEach(db => {
        select.innerHTML += `<option value="${db}">${db}</option>`;
    });
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
