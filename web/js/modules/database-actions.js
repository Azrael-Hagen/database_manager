/**
 * Database actions module extracted from main.js to reduce monolith size.
 * Preserves existing global API expected by inline handlers.
 */

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

window.abrirQueryPanel = abrirQueryPanel;
window.cerrarQueryPanel = cerrarQueryPanel;
window.ejecutarQuerySQL = ejecutarQuerySQL;
window.mostrarResultadoQuery = mostrarResultadoQuery;
window.eliminarTabla = eliminarTabla;
window.abrirImportBD = abrirImportBD;
window.cerrarImportBD = cerrarImportBD;
window.importarABD = importarABD;
