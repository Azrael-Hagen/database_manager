/**
 * Cliente API JavaScript para Database Manager
 * Maneja todas las llamadas HTTP al backend
 */

class APIClient {
    constructor(baseURL = `${window.location.origin}/api`) {
        this.baseURL = baseURL;
        this.token = localStorage.getItem('authToken');
    }

    getToken() {
        return this.token || localStorage.getItem('authToken');
    }

    /**
     * Realizar solicitud HTTP
     */
    async request(method, endpoint, data = null) {
        const url = `${this.baseURL}${endpoint}`;
        const options = {
            method,
            cache: 'no-store',
            headers: {
                'Content-Type': 'application/json',
            }
        };

        const token = this.getToken();
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                let detail = `HTTP Error: ${response.status}`;
                try {
                    const payload = await response.json();
                    detail = payload.detail || payload.mensaje || detail;
                } catch (_) {
                    // ignore JSON parse errors
                }
                throw new Error(detail);
            }

            if (response.status === 204) {
                return {};
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    /**
     * Subir archivo
     */
    async uploadFile(endpoint, file) {
        const url = `${this.baseURL}${endpoint}`;
        const formData = new FormData();
        formData.append('file', file);

        const options = {
            method: 'POST',
            cache: 'no-store',
            headers: {}
        };

        const token = this.getToken();
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        options.body = formData;

        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                let detail = `HTTP Error: ${response.status}`;
                try {
                    const payload = await response.json();
                    detail = payload.detail || payload.mensaje || detail;
                } catch (_) {
                    // ignore JSON parse errors
                }
                throw new Error(detail);
            }

            return await response.json();
        } catch (error) {
            console.error('Upload Error:', error);
            throw error;
        }
    }

    // === AUTENTICACIÓN ===
    async registrar(username, email, password, nombreCompleto = '') {
        return this.request('POST', '/auth/registrar', {
            username,
            email,
            password,
            nombre_completo: nombreCompleto
        });
    }

    async login(username, password) {
        return this.request('POST', '/auth/login', {
            username,
            password
        });
    }

    async getMe() {
        return this.request('GET', '/auth/me');
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('authToken', token);
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('authToken');
    }

    // === DATOS ===
    async getDatos(page = 1, limit = 50, search = '') {
        let endpoint = `/datos?page=${page}&limit=${limit}`;
        if (search) {
            endpoint += `&search=${encodeURIComponent(search)}`;
        }
        return this.request('GET', endpoint);
    }

    async getDato(id) {
        return this.request('GET', `/datos/${id}`);
    }

    async getDatoByUUID(uuid) {
        return this.request('GET', `/datos/uuid/${uuid}`);
    }

    async getDatosTodos(search = '') {
        const suffix = search ? `&buscar=${encodeURIComponent(search)}` : '';
        return this.request('GET', `/datos/?todos=true${suffix}`);
    }

    async crearDato(data) {
        return this.request('POST', '/datos', data);
    }

    async actualizarDato(id, data) {
        return this.request('PUT', `/datos/${id}`, data);
    }

    async eliminarDato(id) {
        return this.request('DELETE', `/datos/${id}`);
    }

    // === IMPORTACIÓN ===
    async importarCSV(file) {
        return this.uploadFile('/import/csv', file);
    }

    async importarExcel(file) {
        return this.uploadFile('/import/excel', file);
    }

    async importarTXT(file) {
        return this.uploadFile('/import/txt', file);
    }

    async importarDAT(file) {
        return this.uploadFile('/import/dat', file);
    }

    async getEstadoImportacion(id) {
        return this.request('GET', `/import/estado/${id}`);
    }

    // === AUDITORÍA ===
    async getAuditoria() {
        return this.request('GET', '/auditoria');
    }

    // === QR VERIFICACION ===
    async verificarAgenteQR(agenteId, telefono = '', numeroVoip = '', semana = '') {
        const params = new URLSearchParams();
        if (telefono) params.append('telefono', telefono);
        if (numeroVoip) params.append('numero_voip', numeroVoip);
        if (semana) params.append('semana', semana);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/verificar/${agenteId}${qs}`);
    }

    async verificarAgenteQRPorUUID(uuid, semana = '') {
        const qs = semana ? `?semana=${encodeURIComponent(semana)}` : '';
        return this.request('GET', `/qr/verificar-uuid/${encodeURIComponent(uuid)}${qs}`);
    }

    async verificarCodigoEscaneado(code, semana = '') {
        const payload = { code };
        if (semana) payload.semana = semana;
        return this.request('POST', '/qr/scan/verify', payload);
    }

    async registrarPagoSemanal(payload) {
        return this.request('POST', '/qr/pagos', payload);
    }

    async getCuotaSemanal() {
        return this.request('GET', '/qr/config/cuota');
    }

    async updateCuotaSemanal(cuota) {
        return this.request('PUT', '/qr/config/cuota', { cuota_semanal: cuota });
    }

    async getReporteSemanal(semana = '', agente = '', empresa = '') {
        const params = new URLSearchParams();
        if (semana) params.append('semana', semana);
        if (agente) params.append('agente', agente);
        if (empresa) params.append('empresa', empresa);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/reporte-semanal${qs}`);
    }

    async procesarAlertasPago() {
        return this.request('POST', '/qr/alertas/procesar', {});
    }

    async generarBackupManual(backupDir = '') {
        const payload = backupDir ? { backup_dir: backupDir } : {};
        return this.request('POST', '/qr/backup', payload);
    }

    async getBackupConfig() {
        return this.request('GET', '/qr/backup/config');
    }

    async updateBackupConfig(backupDir, createIfMissing = true) {
        return this.request('PUT', '/qr/backup/config', {
            backup_dir: backupDir,
            create_if_missing: createIfMissing,
        });
    }

    async getQrAgente(agenteId) {
        return this.request('GET', `/qr/agente/${agenteId}/qr`);
    }

    async downloadQrAgente(agenteId) {
        const url = `${this.baseURL}/qr/agente/${agenteId}/qr/download`;
        const headers = {};
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(url, { method: 'GET', headers, cache: 'no-store' });
        if (!response.ok) {
            let detail = `HTTP Error: ${response.status}`;
            try {
                const payload = await response.json();
                detail = payload.detail || detail;
            } catch (_) {}
            throw new Error(detail);
        }
        return response.blob();
    }

    async listBackups() {
        return this.request('GET', '/qr/backups');
    }

    async restoreBackup(filename) {
        return this.request('POST', '/qr/restore', { filename });
    }

    async getAlertasPago(semana = '', soloPendientes = true) {
        const params = new URLSearchParams();
        if (semana) params.append('semana', semana);
        params.append('solo_pendientes', String(soloPendientes));
        return this.request('GET', `/qr/alertas?${params.toString()}`);
    }

    async getAgentesQR(search = '') {
        const suffix = search ? `?search=${encodeURIComponent(search)}` : '';
        return this.request('GET', `/qr/agentes${suffix}`);
    }

    async crearAgenteManual(payload) {
        return this.request('POST', '/qr/agentes/manual', payload);
    }

    async getLadas(search = '') {
        const suffix = search ? `?search=${encodeURIComponent(search)}` : '';
        return this.request('GET', `/qr/ladas${suffix}`);
    }

    async crearLada(payload) {
        return this.request('POST', '/qr/ladas', payload);
    }

    async getLineas(search = '', soloOcupadas = false, lada = '') {
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (soloOcupadas) params.append('solo_ocupadas', 'true');
        if (lada) params.append('lada', lada);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/lineas${qs}`);
    }

    async crearLinea(payload) {
        return this.request('POST', '/qr/lineas', payload);
    }

    async asignarLinea(lineaId, agenteId) {
        return this.request('POST', `/qr/lineas/${lineaId}/asignar`, { agente_id: agenteId });
    }

    async liberarLinea(lineaId, agenteId = null) {
        const body = agenteId ? { agente_id: agenteId } : {};
        return this.request('POST', `/qr/lineas/${lineaId}/liberar`, body);
    }

    async desactivarLinea(lineaId) {
        return this.request('DELETE', `/qr/lineas/${lineaId}`);
    }

    // === GESTIÓN DE BASES DE DATOS ===
    async getDatabases() {
        return this.request('GET', '/databases/');
    }

    async getTables(database) {
        return this.request('GET', `/databases/${database}/tables`);
    }

    async getTableData(database, table, limit = 50) {
        return this.request('GET', `/databases/${database}/tables/${table}?limit=${limit}`);
    }

    async executeQuery(database, query) {
        return this.request('POST', `/databases/${database}/query`, { query });
    }

    async deleteTable(database, table) {
        return this.request('DELETE', `/databases/${database}/tables/${table}`);
    }

    async getViews(database) {
        return this.request('GET', `/databases/${encodeURIComponent(database)}/views`);
    }

    async createView(database, viewName, selectQuery, orReplace = true) {
        return this.request('POST', `/databases/${encodeURIComponent(database)}/views`, {
            view_name: viewName,
            select_query: selectQuery,
            or_replace: orReplace
        });
    }

    async deleteView(database, viewName) {
        return this.request('DELETE', `/databases/${encodeURIComponent(database)}/views/${encodeURIComponent(viewName)}`);
    }

    async deleteDatabase(dbName) {
        return this.request('DELETE', `/databases/${encodeURIComponent(dbName)}`);
    }

    async importToDatabase(dbName, formData) {
        const url = `${this.baseURL}/databases/${encodeURIComponent(dbName)}/import`;
        const options = {
            method: 'POST',
            cache: 'no-store',
            headers: {}
        };
        const token = this.getToken();
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }
        options.body = formData;
        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = `HTTP Error: ${response.status}`;
            try {
                const payload = await response.json();
                detail = payload.detail || detail;
            } catch (_) {}
            throw new Error(detail);
        }
        return response.json();
    }

    // === GESTIÓN DE USUARIOS ===
    async getUsuarios() {
        return this.request('GET', '/usuarios/');
    }

    async getUsuario(id) {
        return this.request('GET', `/usuarios/${id}`);
    }

    async crearUsuario(userData) {
        return this.request('POST', '/usuarios/', userData);
    }

    async actualizarUsuario(id, userData) {
        return this.request('PUT', `/usuarios/${id}`, userData);
    }

    async cambiarPasswordUsuario(id, password) {
        return this.request('PUT', `/usuarios/${id}/password`, { password });
    }

    async eliminarUsuario(id) {
        return this.request('DELETE', `/usuarios/${id}`);
    }

    // === HEALTH CHECK ===
    async health() {
        return this.request('GET', '/health');
    }

    async getLocalNetworkInfo() {
        return this.request('GET', '/network/local');
    }

    async getBrandingAdminStatus() {
        return this.request('GET', '/branding/admin-status');
    }

    async uploadBrandingLogo(file) {
        const url = `${this.baseURL}/branding/logo`;
        const formData = new FormData();
        formData.append('logo', file);

        const options = {
            method: 'POST',
            cache: 'no-store',
            headers: {}
        };

        const token = this.getToken();
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        options.body = formData;

        const response = await fetch(url, options);
        if (!response.ok) {
            let detail = `HTTP Error: ${response.status}`;
            try {
                const payload = await response.json();
                detail = payload.detail || payload.mensaje || detail;
            } catch (_) {}
            throw new Error(detail);
        }
        return response.json();
    }
}

// Instancia global
const apiClient = new APIClient();
