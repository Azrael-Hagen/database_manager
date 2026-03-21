// === CONFIGURACIÓN GLOBAL ===
const API_URL = 'http://localhost:8000/api';
let authToken = null;
let currentUser = null;
let currentPage = 1;
let currentSearch = '';

// === INICIALIZACIÓN ===
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    if (token) {
        authToken = token;
        currentUser = JSON.parse(localStorage.getItem('currentUser') || '{}');
        showApp();
        loadDashboardData();
    } else {
        showLogin();
    }
});

// === AUTENTICACIÓN ===
function showLogin() {
    document.getElementById('loginSection').style.display = 'block';
    document.getElementById('registerSection').style.display = 'none';
    document.getElementById('dashboardSection').style.display = 'none';
    document.getElementById('datosSection').style.display = 'none';
    document.getElementById('importarSection').style.display = 'none';
    document.getElementById('qrSection').style.display = 'none';
    document.getElementById('auditoriaSection').style.display = 'none';
    document.querySelector('.navbar').style.display = 'none';
    document.querySelector('.sidebar').style.display = 'none';
    document.querySelector('footer').style.display = 'none';
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
    loadSection('dashboard');
}

async function login(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
            throw new Error('Credenciales inválidas');
        }

        const data = await response.json();
        authToken = data.access_token;
        currentUser = data.usuario;

        localStorage.setItem('authToken', authToken);
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
        const response = await fetch(`${API_URL}/auth/registrar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username,
                email,
                nombre_completo: fullName,
                password
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error en el registro');
        }

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
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    showLogin();
}

// === NAVEGACIÓN ===
function loadSection(section) {
    // Ocultar todas las secciones
    document.getElementById('dashboardSection').style.display = 'none';
    document.getElementById('datosSection').style.display = 'none';
    document.getElementById('importarSection').style.display = 'none';
    document.getElementById('qrSection').style.display = 'none';
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
        case 'importar':
            document.getElementById('importarSection').style.display = 'block';
            break;
        case 'qr':
            document.getElementById('qrSection').style.display = 'block';
            break;
        case 'auditoria':
            document.getElementById('auditoriaSection').style.display = 'block';
            cargarAuditoria();
            break;
    }

    event?.target?.classList.add('active');
}

// === DASHBOARD ===
async function loadDashboardData() {
    try {
        const datosRes = await fetch(`${API_URL}/datos?page=1&limit=1`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const datos = await datosRes.json();
        document.getElementById('totalRegistros').textContent = datos.total || 0;
        document.getElementById('totalImportaciones').textContent = '0';
        document.getElementById('totalQR').textContent = '0';
        document.getElementById('totalUsuarios').textContent = '0';
    } catch (error) {
        console.error('Error:', error);
    }
}

// === DATOS ===
async function cargarTablas() {
    try {
        const response = await fetch(`${API_URL}/datos?page=1&limit=100`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await response.json();
        mostrarDatos(data.datos || []);
    } catch (error) {
        console.error('Error:', error);
    }
}

async function buscarDatos() {
    const search = document.getElementById('searchInput').value;
    try {
        const url = search
            ? `${API_URL}/datos?search=${search}`
            : `${API_URL}/datos`;

        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await response.json();
        mostrarDatos(data.datos || []);
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
            html += `<td>${fila[col] || ''}</td>`;
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

    if (!file) {
        alert('Selecciona un archivo');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        document.getElementById('importProgress').style.display = 'block';
        document.getElementById('progressFill').style.width = '0%';

        const response = await fetch(`${API_URL}/import/${tipoArchivo}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body: formData
        });

        const data = await response.json();

        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress > 95) progress = 95;
            document.getElementById('progressFill').style.width = progress + '%';
        }, 500);

        let completed = false;
        while (!completed) {
            const statusRes = await fetch(
                `${API_URL}/import/estado/${data.importacion_id}`,
                { headers: { 'Authorization': `Bearer ${authToken}` } }
            );
            const status = await statusRes.json();

            if (status.estado === 'COMPLETADO' || status.estado === 'FALLIDO') {
                clearInterval(interval);
                document.getElementById('progressFill').style.width = '100%';
                alert(`Importación ${status.estado}: ${status.total_registros} registros`);
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

// === AUDITORÍA ===
async function cargarAuditoria() {
    try {
        const response = await fetch(`${API_URL}/auditoria`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await response.json();

        const container = document.getElementById('auditoriaContainer');
        if (data.length === 0) {
            container.innerHTML = '<p>No hay registros de auditoría</p>';
            return;
        }

        let html = '<table class="data-table"><thead><tr>';
        html += '<th>Fecha</th><th>Usuario</th><th>Acción</th><th>IP</th></tr></thead><tbody>';

        data.forEach(registro => {
            html += `<tr>
                <td>${new Date(registro.fecha_hora).toLocaleString()}</td>
                <td>${registro.usuario_id}</td>
                <td>${registro.tipo_accion}</td>
                <td>${registro.ip_origen}</td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error:', error);
    }
}
