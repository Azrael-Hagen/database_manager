/**
 * Datos section module extracted from main.js for maintainability.
 * Keeps the same global function names used by UI handlers.
 */

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

