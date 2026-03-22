/**
 * Métodos de API para las nuevas funcionalidades
 * Agregar estos métodos a web/js/api-client.js en la clase APIClient
 */

// ===== EXPORTACIÓN DE DATOS =====

/**
 * Exportar tabla a CSV o Excel
 */
async exportTableData(dbName, tableName, format = 'csv', limit = null) {
    const params = new URLSearchParams();
    if (format) params.append('format', format);
    if (limit) params.append('limit', limit);
    const qs = params.toString() ? `?${params.toString()}` : '';
    
    const url = `${this.baseURL}/export/table/${encodeURIComponent(dbName)}/${encodeURIComponent(tableName)}${qs}`;
    const headers = {};
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    
    const response = await fetch(url, { method: 'GET', headers, cache: 'no-store' });
    if (!response.ok) throw new Error(`Error: ${response.status}`);
    
    return response.blob();
}

/**
 * Exportar agentes a CSV o Excel
 */
async exportAgentes(format = 'csv', withPayments = false) {
    const params = new URLSearchParams();
    params.append('format', format);
    params.append('with_pagos', String(withPayments));
    const qs = params.toString() ? `?${params.toString()}` : '';
    
    const url = `${this.baseURL}/export/agentes${qs}`;
    const headers = {};
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    
    const response = await fetch(url, { method: 'GET', headers, cache: 'no-store' });
    if (!response.ok) throw new Error(`Error: ${response.status}`);
    
    return response.blob();
}

// ===== GESTIÓN DE ESQUEMAS =====

/**
 * Exportar esquema de BD completo como JSON
 */
async exportDatabaseSchema(dbName) {
    return this.request('GET', `/export/schemas/${encodeURIComponent(dbName)}`);
}

/**
 * Guardar versión del esquema
 */
async saveDatabaseSchema(dbName, version = '1.0.0', etiqueta = null, descripcion = null) {
    return this.request('POST', `/export/schemas/${encodeURIComponent(dbName)}/save`, {
        version,
        etiqueta,
        descripcion,
    });
}

/**
 * Listar versiones guardadas del esquema
 */
async listSchemaVersions(dbName) {
    return this.request('GET', `/export/schemas/${encodeURIComponent(dbName)}/versions`);
}

/**
 * Descargar una versión específica del esquema
 */
async downloadSchemaVersion(schemaId) {
    const url = `${this.baseURL}/export/schemas/${schemaId}/download`;
    const headers = {};
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    
    const response = await fetch(url, { method: 'GET', headers, cache: 'no-store' });
    if (!response.ok) throw new Error(`Error: ${response.status}`);
    
    return response.blob();
}

// ===== INTEGRACIÓN CON PBX =====

/**
 * Listar extensiones disponibles desde PBX
 */
async listPbxExtensions(pbxDb = 'asterisk', search = null, limit = 100) {
    const params = new URLSearchParams();
    params.append('pbx_db', pbxDb);
    if (search) params.append('search', search);
    if (limit) params.append('limit', limit);
    
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this.request('GET', `/export/pbx/extensions${qs}`);
}

/**
 * Sincronizar extensiones PBX a catálogo local
 */
async syncPbxExtensions(pbxDb = 'asterisk') {
    return this.request('POST', `/export/pbx/sync-extensions?pbx_db=${encodeURIComponent(pbxDb)}`);
}

// ===== GESTIÓN AVANZADA DE BACKUPS =====

/**
 * Listar todas las rutas de backup configuradas
 */
async listBackupPaths() {
    return this.request('GET', '/export/backup/paths');
}

/**
 * Agregar nueva ruta de backup
 */
async addBackupPath(path, isActive = false) {
    return this.request('POST', '/export/backup/paths', {
        path,
        is_active: isActive,
    });
}

/**
 * Establecer ruta activa para backups
 */
async setActiveBackupPath(index) {
    return this.request('PUT', `/export/backup/paths/activate/${index}`);
}

/**
 * Obtener configuración de auto-backup
 */
async getAutoBackupConfig() {
    return this.request('GET', '/export/backup/auto-config');
}

/**
 * Configurar auto-backup automático
 */
async configureAutoBackup(enabled = false, hour = 2, retentionDays = 30) {
    return this.request('POST', '/export/backup/auto-config', {
        enabled,
        hour,
        retention_days: retentionDays,
    });
}

/**
 * Limpiar backups antiguos
 */
async cleanupOldBackups(days = 30, path = null) {
    return this.request('POST', '/export/backup/cleanup', {
        days,
        path,
    });
}

// ===== FUNCIONES FRONTEND AUXILIARES =====

/**
 * Descargar archivo exportado con nombre automático
 */
async downloadFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

/**
 * Exportar tabla con descarga automática
 */
async exportTableWithDownload(dbName, tableName, format = 'csv') {
    try {
        const blob = await this.exportTableData(dbName, tableName, format);
        const ext = format === 'excel' ? 'xlsx' : 'csv';
        const filename = `${tableName}.${ext}`;
        await this.downloadFile(blob, filename);
        return { success: true, filename };
    } catch (error) {
        console.error('Export error:', error);
        throw error;
    }
}

/**
 * Exportar agentes con descarga automática
 */
async exportAgentesWithDownload(format = 'csv', withPayments = false) {
    try {
        const blob = await this.exportAgentes(format, withPayments);
        const ext = format === 'excel' ? 'xlsx' : 'csv';
        const filename = `agentes_${new Date().toISOString().slice(0, 10)}.${ext}`;
        await this.downloadFile(blob, filename);
        return { success: true, filename };
    } catch (error) {
        console.error('Export agentes error:', error);
        throw error;
    }
}

// ===== EJEMPLOS DE USO =====

/*
// En web/js/main.js o en eventos de botones:

// Exportar agentes a CSV
async function exportarAgentesCSV() {
    try {
        const result = await apiClient.exportAgentesWithDownload('csv', false);
        alert(`Archivo descargado: ${result.filename}`);
    } catch (error) {
        alert('Error al exportar: ' + error.message);
    }
}

// Exportar agentes a Excel con pagos
async function exportarAgentesExcel() {
    try {
        const result = await apiClient.exportAgentesWithDownload('excel', true);
        alert(`Archivo descargado: ${result.filename}`);
    } catch (error) {
        alert('Error al exportar: ' + error.message);
    }
}

// Listar extensiones PBX
async function listarExtensionesDisponibles() {
    try {
        const res = await apiClient.listPbxExtensions('asterisk', null, 50);
        console.log('Extensiones disponibles:', res.data);
        // Renderizar en una tabla o select
    } catch (error) {
        alert('Error al listar extensiones: ' + error.message);
    }
}

// Sincronizar extensiones PBX
async function sincronizarExtensiones() {
    try {
        const res = await apiClient.syncPbxExtensions('asterisk');
        alert(`Sincronización completada: ${res.data.message}`);
        console.log('Detalles:', res.data);
    } catch (error) {
        alert('Error al sincronizar: ' + error.message);
    }
}

// Configurar múltiples rutas de backup
async function configurarRutasBackup() {
    try {
        // Agregar ruta principal
        await apiClient.addBackupPath('D:/backups/principal', true);
        
        // Agregar ruta secundaria
        await apiClient.addBackupPath('D:/backups/secundario');
        
        // Listar todas las rutas
        const paths = await apiClient.listBackupPaths();
        console.log('Rutas configuradas:', paths.data);
    } catch (error) {
        alert('Error configurando backups: ' + error.message);
    }
}

// Habilitar auto-backup
async function habilitarAutoBackup() {
    try {
        // Configurar backup automático a las 2 AM, retener 30 días
        await apiClient.configureAutoBackup(true, 2, 30);
        alert('Auto-backup configurado correctamente');
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Guardar esquema de BD
async function guardarEsquemaActual() {
    try {
        const res = await apiClient.saveDatabaseSchema(
            'registro_agentes',
            '1.0.0',
            'Esquema producción',
            'Versión inicial de la BD'
        );
        console.log('Esquema guardado:', res.data);
    } catch (error) {
        alert('Error al guardar esquema: ' + error.message);
    }
}

// Listar versiones de esquemas
async function listarEsquemasGuardados() {
    try {
        const res = await apiClient.listSchemaVersions('registro_agentes');
        console.log('Versiones guardadas:', res.data);
        // Renderizar tabla de versiones
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
*/
