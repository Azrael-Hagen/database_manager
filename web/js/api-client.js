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

    _shouldInvalidateSession(status, detail = '') {
        if (status === 401) return true;
        if (status !== 403) return false;

        const text = String(detail || '').toLowerCase();
        // 403 puede ser un permiso funcional (no debe cerrar sesión).
        // Solo invalidamos sesión si el mensaje apunta a token/sesión inválida.
        return [
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
        ].some(fragment => text.includes(fragment));
    }

    _emitSessionInvalid(reason = 'token_invalid') {
        try {
            window.dispatchEvent(new CustomEvent('app:session-invalid', {
                detail: { reason }
            }));
        } catch (_) {
            // noop
        }
    }

    _requirePositiveInt(value, fieldName = 'id') {
        const n = Number(value);
        if (!Number.isInteger(n) || n <= 0) {
            throw new Error(`Validación fallida: ${fieldName} inválido`);
        }
        return n;
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
                if (this._shouldInvalidateSession(response.status, detail)) {
                    this._emitSessionInvalid('api_request_unauthorized');
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
                if (this._shouldInvalidateSession(response.status, detail)) {
                    this._emitSessionInvalid('api_upload_unauthorized');
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

    async registrarTemporal(username, email, password, nombreCompleto = '', diasVigencia = 10) {
        return this.request('POST', '/auth/registrar-temporal', {
            username,
            email,
            password,
            nombre_completo: nombreCompleto,
            dias_vigencia: diasVigencia,
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

    async getSelfServiceResumen() {
        return this.request('GET', '/usuarios/self-service/resumen');
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

    async getResumenPagoAgente(agenteId, semana = '') {
        const qs = semana ? `?semana=${encodeURIComponent(semana)}` : '';
        return this.request('GET', `/qr/pagos/resumen/${agenteId}${qs}`);
    }

    async getTotalesCobranza(fecha = '', semana = '') {
        const params = new URLSearchParams();
        if (fecha) params.append('fecha', fecha);
        if (semana) params.append('semana', semana);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/pagos/totales${qs}`);
    }

    async getDeudaManualAgente(agenteId, semana = '') {
        const qs = semana ? `?semana=${encodeURIComponent(semana)}` : '';
        return this.request('GET', `/qr/agentes/${agenteId}/deuda-manual${qs}`);
    }

    async setDeudaManualAgente(agenteId, payload) {
        return this.request('PUT', `/qr/agentes/${agenteId}/deuda-manual`, payload);
    }

    async editarPagoSemanalAdmin(pagoId, payload) {
        return this.request('PUT', `/qr/pagos/${pagoId}`, payload);
    }

    async revertirPagoSemanalAdmin(pagoId, payload = {}) {
        return this.request('POST', `/qr/pagos/${pagoId}/revertir`, payload);
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

    async getAgentesEstadoPago(semana = '', search = '') {
        const params = new URLSearchParams();
        if (semana) params.append('semana', semana);
        if (search) params.append('search', search);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/agentes/estado-pago${qs}`);
    }

    async getRecibosPago(agenteId = '', includeExpired = false) {
        const params = new URLSearchParams();
        if (agenteId) params.append('agente_id', String(agenteId));
        if (includeExpired) params.append('include_expired', 'true');
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/recibos${qs}`);
    }

    async getReciboPago(token) {
        return this.request('GET', `/qr/recibos/${encodeURIComponent(token)}`);
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

    async exportQrAgentesPdf({ idsCsv = '', search = '', layout = 'sheet', soloActivos = true, marcarImpreso = true, layoutOverrides = null } = {}) {
        const params = new URLSearchParams();
        if (idsCsv) params.append('ids_csv', idsCsv);
        if (search) params.append('search', search);
        if (layout) params.append('layout', layout);
        if (layoutOverrides && typeof layoutOverrides === 'object') {
            params.append('layout_overrides', JSON.stringify(layoutOverrides));
        }
        params.append('solo_activos', String(soloActivos));
        params.append('marcar_impreso', String(marcarImpreso));

        const url = `${this.baseURL}/qr/agentes/export/pdf?${params.toString()}`;
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
                detail = payload.detail || payload.mensaje || detail;
            } catch (_) {}
            if (this._shouldInvalidateSession(response.status, detail)) {
                this._emitSessionInvalid('api_blob_unauthorized');
            }
            throw new Error(detail);
        }
        return response.blob();
    }

    async getAgentesConQRSinImprimir(soloActivos = true) {
        return this.request('GET', `/qr/agentes/sin-imprimir?solo_activos=${soloActivos}`);
    }

    async marcarAgentesImpreso(ids, impreso = true) {
        return this.request('POST', '/qr/agentes/marcar-impreso', { ids, impreso });
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
            if (this._shouldInvalidateSession(response.status, detail)) {
                this._emitSessionInvalid('api_blob_unauthorized');
            }
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

    async getServerVersion() {
        return this.request('GET', '/system/version');
    }

    async getAlertasPago(semana = '', soloPendientes = true) {
        const params = new URLSearchParams();
        if (semana) params.append('semana', semana);
        params.append('solo_pendientes', String(soloPendientes));
        return this.request('GET', `/qr/alertas?${params.toString()}`);
    }

    async getAgentesQR(search = '', limit = 500) {
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (Number.isFinite(Number(limit)) && Number(limit) > 0) {
            params.append('limit', String(Number(limit)));
        }
        const suffix = params.toString() ? `?${params.toString()}` : '';
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

    async getLineas(search = '', soloOcupadas = false, lada = '', estado = 'todas') {
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (soloOcupadas) params.append('solo_ocupadas', 'true');
        if (lada) params.append('lada', lada);
        if (estado && estado !== 'todas') params.append('estado', estado);
        const qs = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/qr/lineas${qs}`);
    }

    async crearLinea(payload) {
        return this.request('POST', '/qr/lineas', payload);
    }

    async actualizarLinea(lineaId, payload) {
        const id = this._requirePositiveInt(lineaId, 'linea_id');
        return this.request('PUT', `/qr/lineas/${id}`, payload);
    }

    async syncLineas() {
        return this.request('POST', '/qr/lineas/sync', {});
    }

    async asignarLinea(lineaId, agenteId, billing = {}) {
        const id = this._requirePositiveInt(lineaId, 'linea_id');
        const agId = this._requirePositiveInt(agenteId, 'agente_id');
        return this.request('POST', `/qr/lineas/${id}/asignar`, {
            agente_id: agId,
            cobro_desde_semana: billing.cobroDesdeSemana || null,
            cargo_inicial: Number(billing.cargoInicial || 0),
        });
    }

    async liberarLinea(lineaId, agenteId = null) {
        const id = this._requirePositiveInt(lineaId, 'linea_id');
        const body = agenteId ? { agente_id: this._requirePositiveInt(agenteId, 'agente_id') } : {};
        return this.request('POST', `/qr/lineas/${id}/liberar`, body);
    }

    async desactivarLinea(lineaId) {
        const id = this._requirePositiveInt(lineaId, 'linea_id');
        return this.request('DELETE', `/qr/lineas/${id}`);
    }

    // === GESTIÓN DE BASES DE DATOS ===
    async getDatabases() {
        return this.request('GET', '/databases/');
    }

    async getTables(database) {
        return this.request('GET', `/databases/${database}/tables`);
    }

    async getTableData(database, table, limit = 50, offset = 0, orderBy = '', direction = 'asc') {
        const params = new URLSearchParams();
        params.append('limit', String(limit));
        params.append('offset', String(offset));
        if (orderBy) params.append('order_by', orderBy);
        if (direction) params.append('direction', direction);
        return this.request('GET', `/databases/${database}/tables/${table}?${params.toString()}`);
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

    async getMaintenanceOverview(database) {
        return this.request('GET', `/databases/${encodeURIComponent(database)}/maintenance/overview`);
    }

    async createUsefulViews(database) {
        return this.request('POST', `/databases/${encodeURIComponent(database)}/maintenance/useful-views`, {});
    }

    async purgeTemporaryObjects(database, includeEmpty = false) {
        return this.request('POST', `/databases/${encodeURIComponent(database)}/maintenance/purge-temporary?include_empty=${includeEmpty ? 'true' : 'false'}`, {});
    }

    async cleanupRedundantAgents(database, dryRun = false) {
        return this.request('POST', `/databases/${encodeURIComponent(database)}/maintenance/cleanup-redundant-agents?dry_run=${dryRun ? 'true' : 'false'}`, {});
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
            if (this._shouldInvalidateSession(response.status, detail)) {
                this._emitSessionInvalid('api_form_unauthorized');
            }
            throw new Error(detail);
        }
        return response.json();
    }

    // === GESTIÓN DE USUARIOS ===
    async getUsuarios(orderBy = 'fecha_creacion', direction = 'desc') {
        const params = new URLSearchParams();
        params.append('ordenar_por', orderBy);
        params.append('direccion', direction);
        return this.request('GET', `/usuarios/?${params.toString()}`);
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

    async eliminarUsuario(id, hardDelete = false) {
        const qs = hardDelete ? '?hard_delete=true' : '';
        return this.request('DELETE', `/usuarios/${id}${qs}`);
    }

    async getUsuariosMaintenanceOverview() {
        return this.request('GET', '/usuarios/maintenance/overview');
    }

    async reclassifyUsuariosBulk(updates) {
        return this.request('POST', '/usuarios/maintenance/reclassify', { updates });
    }

    async purgeTemporaryUsuarios(includeInactiveStale = true) {
        return this.request('POST', `/usuarios/maintenance/purge-temporary?include_inactive_stale=${includeInactiveStale ? 'true' : 'false'}`, {});
    }

    async crearUsuarioTemporal(payload) {
        return this.request('POST', '/usuarios/temporales', payload);
    }

    async renovarUsuarioTemporal(id, diasVigencia = 10) {
        return this.request('POST', `/usuarios/${id}/temporal/renovar`, { dias_vigencia: diasVigencia });
    }

    async solicitarPermisoTemporal(id, payload) {
        return this.request('POST', `/usuarios/${id}/solicitud-permisos`, payload);
    }

    async getSolicitudesPermisosTemporales() {
        return this.request('GET', '/usuarios/solicitudes-permisos');
    }

    async resolverSolicitudPermisoTemporal(id, payload) {
        return this.request('POST', `/usuarios/solicitudes-permisos/${id}/resolver`, payload);
    }

    async getHistorialTemporales(limit = 100) {
        return this.request('GET', `/usuarios/temporales/historial?limit=${encodeURIComponent(limit)}`);
    }

    async hardDeleteDato(id) {
        return this.request('DELETE', `/datos/${id}/hard-delete`);
    }

    async purgeInactiveDatos() {
        return this.request('DELETE', '/datos/purge/inactivos');
    }

    async listarPapelera(skip = 0, limit = 50) {
        return this.request('GET', `/datos/papelera?skip=${skip}&limit=${limit}`);
    }

    async rollbackDato(id) {
        return this.request('POST', `/datos/${id}/rollback`);
    }

    // === HEALTH CHECK ===
    async health() {
        return this.request('GET', '/health');
    }

    async getDashboardSummary() {
        return this.request('GET', '/dashboard/summary');
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
            if (this._shouldInvalidateSession(response.status, detail)) {
                this._emitSessionInvalid('api_upload_unauthorized');
            }
            throw new Error(detail);
        }
        return response.json();
    }
}

// Instancia global
const apiClient = new APIClient();
