/**
 * Cliente API JavaScript para Database Manager
 * Maneja todas las llamadas HTTP al backend
 */

class APIClient {
    constructor(baseURL = 'http://localhost:8000/api') {
        this.baseURL = baseURL;
        this.token = localStorage.getItem('authToken');
    }

    /**
     * Realizar solicitud HTTP
     */
    async request(method, endpoint, data = null) {
        const url = `${this.baseURL}${endpoint}`;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            }
        };

        if (this.token) {
            options.headers['Authorization'] = `Bearer ${this.token}`;
        }

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                throw new Error(`HTTP Error: ${response.status}`);
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
            headers: {}
        };

        if (this.token) {
            options.headers['Authorization'] = `Bearer ${this.token}`;
        }

        options.body = formData;

        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                throw new Error(`HTTP Error: ${response.status}`);
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

    // === HEALTH CHECK ===
    async health() {
        return this.request('GET', '/health');
    }
}

// Instancia global
const apiClient = new APIClient();
