let mobileToken = '';
let mobileCurrentUser = null;
let activeViewId = 'dashboardView';
let datosPage = 1;
let datosSearch = '';
let alertasSoloPendientes = true;
let qrScannerInstance = null;
let qrScannerStartInFlight = false;
let qrScannerStopInFlight = false;
let qrScannerLibraryLoadingPromise = null;
let qrLastDecodedText = '';
let qrLastDecodedAtMs = 0;
const datosLimit = 20;
const QR_SCAN_DUPLICATE_WINDOW_MS = 2500;
const QR_SCANNER_CDN_SOURCES = [
    'https://unpkg.com/html5-qrcode@2.3.8',
    'https://cdn.jsdelivr.net/npm/html5-qrcode@2.3.8/html5-qrcode.min.js',
];

// Offline-sync modules
let offlineDb = null;
let offlineSyncManager = null;
let offlineConflictResolver = null;
let offlineQueue = null;
const MOBILE_CACHE_PREFIX = 'dbm:mobile-cache:';

const refs = {
    mobileStatus: document.getElementById('mobileStatus'),
    loginView: document.getElementById('loginView'),
    dashboardView: document.getElementById('dashboardView'),
    qrView: document.getElementById('qrView'),
    pagosView: document.getElementById('pagosView'),
    alertasView: document.getElementById('alertasView'),
    datosView: document.getElementById('datosView'),
    bottomNav: document.getElementById('bottomNav'),
    statsGrid: document.getElementById('statsGrid'),
    networkCard: document.getElementById('networkCard'),
    versionCard: document.getElementById('versionCard'),
    appDownloadCard: document.getElementById('appDownloadCard'),
    phantomAppInfo: document.getElementById('phantomAppInfo'),
    phantomAppDownloadBtn: document.getElementById('phantomAppDownloadBtn'),
    qrWeek: document.getElementById('qrWeek'),
    qrCodeInput: document.getElementById('qrCodeInput'),
    qrResult: document.getElementById('qrResult'),
    qrCameraSelect: document.getElementById('qrCameraSelect'),
    qrCameraStatus: document.getElementById('qrCameraStatus'),
    qrScannerContainer: document.getElementById('qrScannerContainer'),
    qrCameraToggleBtn: document.getElementById('qrCameraToggleBtn'),
    refreshCamerasBtn: document.getElementById('refreshCamerasBtn'),
    sendToPagoBtn: document.getElementById('sendToPagoBtn'),
    qrPhantomAppBtn: document.getElementById('qrPhantomAppBtn'),
    pagoWeek: document.getElementById('pagoWeek'),
    quickAgenteId: document.getElementById('quickAgenteId'),
    quickMonto: document.getElementById('quickMonto'),
    pagoResult: document.getElementById('pagoResult'),
    pagoResumenCard: document.getElementById('pagoResumenCard'),
    totalesCard: document.getElementById('totalesCard'),
    alertasWeek: document.getElementById('alertasWeek'),
    alertasList: document.getElementById('alertasList'),
    datosList: document.getElementById('datosList'),
    pageInfo: document.getElementById('pageInfo'),
};

function setStatus(message) {
    refs.mobileStatus.textContent = String(message || 'Listo');
}

function setQrCameraStatus(message, tone = 'normal') {
    if (!refs.qrCameraStatus) return;
    refs.qrCameraStatus.textContent = String(message || 'Listo');
    refs.qrCameraStatus.style.color = tone === 'error'
        ? '#b42318'
        : tone === 'warning'
            ? '#9a6200'
            : '#5b7892';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatMoney(value) {
    return Number(value || 0).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
}

function isoDateMonday() {
    const now = new Date();
    const day = now.getDay();
    const diff = (day === 0 ? -6 : 1 - day);
    now.setDate(now.getDate() + diff);
    return now.toISOString().slice(0, 10);
}

function switchToDesktop() {
    localStorage.setItem('dbm:view', 'desktop');
    window.location.replace('/?view=desktop');
}

function clearDesktopOverride() {
    localStorage.removeItem('dbm:view');
}

function getDisplayName(user) {
    if (!user || typeof user !== 'object') return 'Usuario';
    return user.username || user.nombre_completo || user.email || 'Usuario';
}

function isInsideNativeApp() {
    return !!window.PhantomAndroid;
}

function getMobileSessionStorage() {
    return isInsideNativeApp() ? sessionStorage : localStorage;
}

function clearPersistentAuthCacheForNativeRuntime() {
    if (!isInsideNativeApp()) return;
    try {
        localStorage.removeItem('authToken');
        localStorage.removeItem('currentUser');
    } catch (_) {
        // noop
    }
}

function getCachedCurrentUser() {
    try {
        const raw = getMobileSessionStorage().getItem('currentUser');
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

function getSnapshotStorageKey(name) {
    const userKey = mobileCurrentUser?.id || mobileCurrentUser?.username || mobileCurrentUser?.email || 'anon';
    return `${MOBILE_CACHE_PREFIX}${userKey}:${name}`;
}

function saveSnapshot(name, payload) {
    try {
        localStorage.setItem(getSnapshotStorageKey(name), JSON.stringify({
            savedAt: new Date().toISOString(),
            payload,
        }));
    } catch (_) {
        // noop
    }
}

function readSnapshot(name) {
    try {
        const raw = localStorage.getItem(getSnapshotStorageKey(name));
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

function isConnectivityError(error) {
    const message = String(error?.message || error || '').toLowerCase();
    return !navigator.onLine
        || message.includes('failed to fetch')
        || message.includes('networkerror')
        || message.includes('network request failed')
        || message.includes('load failed');
}

function formatSnapshotStatus(savedAt) {
    if (!savedAt) return 'cache local';
    const saved = new Date(savedAt);
    if (Number.isNaN(saved.getTime())) return 'cache local';
    return `cache local ${saved.toLocaleString('es-MX')}`;
}

function applyNativeAppChrome() {
    if (!isInsideNativeApp()) return;

    const switchDesktopBtn = document.getElementById('switchDesktopBtn');
    if (switchDesktopBtn) {
        switchDesktopBtn.style.display = 'none';
    }

    if (refs.networkCard) {
        refs.networkCard.style.display = 'none';
    }

    if (refs.appDownloadCard) {
        refs.appDownloadCard.style.display = 'none';
    }
}

function setLoggedInUi(loggedIn) {
    refs.loginView.classList.toggle('active', !loggedIn);
    refs.bottomNav.style.display = loggedIn ? 'grid' : 'none';
    if (loggedIn) {
        showView(activeViewId);
    }
}

function showView(viewId) {
    ['dashboardView', 'qrView', 'pagosView', 'alertasView', 'datosView'].forEach((id) => {
        const el = refs[id];
        if (el) {
            el.classList.toggle('active', id === viewId);
        }
    });

    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.getAttribute('data-view') === viewId);
    });

    activeViewId = viewId;
}

function getEstadoPill(estado) {
    const raw = String(estado || '').toLowerCase();
    if (raw.includes('corriente') || raw.includes('pagado')) {
        return '<span class="pill success">Al corriente</span>';
    }
    if (raw.includes('abono')) {
        return '<span class="pill info">Abonado</span>';
    }
    if (raw.includes('sin') || raw.includes('revision')) {
        return '<span class="pill warning">En revisión</span>';
    }
    return '<span class="pill danger">Pendiente</span>';
}

function renderStats(summary) {
    const totals = summary?.totals || {};
    const cards = [
        ['Registros', totals.registros ?? 0],
        ['Activos', totals.registros_activos ?? 0],
        ['Inactivos', totals.registros_inactivos ?? 0],
        ['QR pendientes', totals.qr_pendientes ?? 0],
        ['Alertas', totals.alertas_pago_pendientes ?? 0],
        ['Sin línea', totals.sin_linea ?? 0],
    ];

    refs.statsGrid.innerHTML = cards.map(([label, value]) => `
        <div class="stat">
            <div class="label">${label}</div>
            <div class="value">${value}</div>
        </div>
    `).join('');
}

function renderNetworkInfo(netInfo) {
    if (!netInfo || netInfo.status !== 'ok') {
        refs.networkCard.innerHTML = '<span class="hint">No se pudo obtener la red local</span>';
        return;
    }
    refs.networkCard.innerHTML = `
        <strong>Acceso LAN</strong>
        <div class="meta">${escapeHtml(netInfo.share_url_preferida || '-')}</div>
        <div class="meta">IP servidor sugerida: ${escapeHtml(netInfo.ip_local || '-')}</div>
    `;
}

function renderVersionInfo(versionPayload) {
    if (!refs.versionCard) return;
    if (!versionPayload) {
        refs.versionCard.innerHTML = '<span class="hint">Versión de servidor no disponible</span>';
        return;
    }

    refs.versionCard.innerHTML = `
        <strong>Servidor</strong>
        <div class="meta">${escapeHtml(versionPayload.version || versionPayload.version_string || '-')}</div>
        <div class="meta">Revisión: ${escapeHtml(versionPayload.revision || '-')}</div>
    `;
}

function renderMobileAppInfo(data) {
    if (!refs.phantomAppInfo || !refs.phantomAppDownloadBtn || !refs.qrPhantomAppBtn) return;
    const isInsideApp = isInsideNativeApp();
    if (data?.disponible) {
        refs.phantomAppInfo.textContent = isInsideApp
            ? 'App instalada y activa.'
            : `Disponible · ${escapeHtml(data.nombre || 'PhantomApp.apk')} · ${escapeHtml(data.tamanio_mb || 0)} MB`;
        refs.phantomAppDownloadBtn.style.display = isInsideApp ? 'none' : '';
        refs.qrPhantomAppBtn.style.display = isInsideApp ? 'none' : '';
    } else {
        refs.phantomAppInfo.textContent = 'La app Android no está disponible en este servidor.';
        refs.phantomAppDownloadBtn.style.display = 'none';
        refs.qrPhantomAppBtn.style.display = 'none';
    }
}

function renderPagoResumen(data) {
    if (!refs.pagoResumenCard) return;
    if (!data || typeof data !== 'object') {
        refs.pagoResumenCard.classList.add('empty');
        refs.pagoResumenCard.textContent = 'Escanea o verifica un QR para cargar el resumen del agente.';
        return;
    }

    const deudaBase = Number(data.deuda_base_total || 0);
    const ajusteManual = Number(data.ajuste_manual_deuda || 0);
    const deudaTotal = Number(data.deuda_total || 0);
    const totalAbonado = Number(data.total_abonado || 0);
    const saldo = Number(data.saldo_acumulado || 0);
    refs.pagoResumenCard.classList.remove('empty');
    refs.pagoResumenCard.innerHTML = `
        <strong>Resumen del agente</strong>
        <div class="meta">Semana: ${escapeHtml(data.semana_inicio || refs.pagoWeek.value || '-')}</div>
        <div class="meta">Tarifa por línea: ${formatMoney(data.tarifa_linea_semanal || 0)} · Líneas activas: ${escapeHtml(data.lineas_activas || 0)}</div>
        <div class="meta">Cargo semanal: ${formatMoney(data.cuota_semanal || 0)}</div>
        <div class="meta">Deuda base: ${formatMoney(deudaBase)} · Ajuste manual: ${formatMoney(ajusteManual)}</div>
        <div class="meta">Deuda total: ${formatMoney(deudaTotal)} · Abonado: ${formatMoney(totalAbonado)}</div>
        <div class="meta">Saldo acumulado: ${formatMoney(saldo)} · Semanas pendientes: ${escapeHtml(data.semanas_pendientes || 0)}</div>
    `;
}

function renderQrResult(payload) {
    const agente = payload?.agente || {};
    const verificacion = payload?.verificacion || {};
    refs.qrResult.classList.remove('empty');
    refs.qrResult.innerHTML = `
        <div><strong>${escapeHtml(agente.display_name || agente.alias || agente.nombre || ('Agente ' + (agente.id || '-')))}</strong></div>
        <div class="meta">ID: ${escapeHtml(agente.id || '-')} · Tel: ${escapeHtml(agente.telefono || '-')} · VOIP: ${escapeHtml(agente.numero_voip || '-')}</div>
        <div class="meta">Estado: ${getEstadoPill(verificacion.estado_pago || '')} · Cuota: ${formatMoney(verificacion.cuota_semanal || 0)}</div>
        <div class="meta">Saldo acumulado: ${formatMoney(verificacion.saldo_acumulado || 0)} · Abonado: ${formatMoney(verificacion.total_abonado || 0)}</div>
        <div class="meta">Semana: ${escapeHtml(verificacion.semana_inicio || refs.qrWeek.value || '-')} · Semanas pendientes: ${escapeHtml(verificacion.semanas_pendientes || 0)}</div>
    `;

    if (refs.quickAgenteId && agente.id) {
        refs.quickAgenteId.value = String(agente.id);
    }
    if (refs.quickMonto) {
        refs.quickMonto.value = Number(verificacion.cuota_semanal || verificacion.saldo_acumulado || 0).toFixed(2);
    }
    if (refs.sendToPagoBtn) {
        refs.sendToPagoBtn.style.display = agente.id ? '' : 'none';
    }
}

function renderScannerState(active) {
    if (!refs.qrScannerContainer || !refs.qrCameraToggleBtn) return;
    refs.qrScannerContainer.style.display = active ? '' : 'none';
    refs.qrCameraToggleBtn.textContent = active ? 'Detener camara' : 'Camara web';
}

function setQrScannerButtonBusy(isBusy) {
    if (!refs.qrCameraToggleBtn) return;
    refs.qrCameraToggleBtn.disabled = !!isBusy;
}

function loadQrScannerScript(src) {
    return new Promise((resolve, reject) => {
        const existing = document.querySelector(`script[data-qr-scanner-src="${src}"]`);
        if (existing) {
            if (typeof Html5Qrcode !== 'undefined') {
                resolve(true);
                return;
            }
            existing.addEventListener('load', () => resolve(true), { once: true });
            existing.addEventListener('error', () => reject(new Error(`No se pudo cargar ${src}`)), { once: true });
            return;
        }

        const script = document.createElement('script');
        script.src = src;
        script.async = true;
        script.dataset.qrScannerSrc = src;
        script.onload = () => resolve(true);
        script.onerror = () => reject(new Error(`No se pudo cargar ${src}`));
        document.head.appendChild(script);
    });
}

async function ensureQrScannerLibrary() {
    if (typeof Html5Qrcode !== 'undefined') {
        return true;
    }
    if (qrScannerLibraryLoadingPromise) {
        return qrScannerLibraryLoadingPromise;
    }

    qrScannerLibraryLoadingPromise = (async () => {
        for (const src of QR_SCANNER_CDN_SOURCES) {
            try {
                await loadQrScannerScript(src);
                if (typeof Html5Qrcode !== 'undefined') {
                    return true;
                }
            } catch (_) {
                // Intentar siguiente CDN.
            }
        }
        return typeof Html5Qrcode !== 'undefined';
    })();

    try {
        return await qrScannerLibraryLoadingPromise;
    } finally {
        qrScannerLibraryLoadingPromise = null;
    }
}

function populatePagoFromVerification(agente, verificacion) {
    refs.quickAgenteId.value = agente?.id ? String(agente.id) : '';
    refs.quickMonto.value = Number(verificacion?.cuota_semanal || verificacion?.saldo_acumulado || 0).toFixed(2);
    refs.pagoWeek.value = verificacion?.semana_inicio || refs.qrWeek.value || isoDateMonday();
}

async function loadPagoResumen(agenteId, semana = '') {
    const parsedAgenteId = Number(agenteId);
    if (!Number.isInteger(parsedAgenteId) || parsedAgenteId <= 0) {
        renderPagoResumen(null);
        return;
    }

    const cacheKey = `pago-resumen:${parsedAgenteId}:${semana || '-'}`;

    try {
        const res = await apiClient.getResumenPagoAgente(parsedAgenteId, semana);
        const payload = res?.data || null;
        renderPagoResumen(payload);
        saveSnapshot(cacheKey, payload);
        return { source: 'network' };
    } catch (error) {
        const cached = readSnapshot(cacheKey);
        if (cached) {
            renderPagoResumen(cached.payload || null);
            return { source: 'cache', savedAt: cached.savedAt };
        }
        throw error;
    }
}

async function fetchAppDownloadInfo() {
    const response = await fetch('/api/download/phantom-app/info', { cache: 'no-store' });
    if (!response.ok) {
        throw new Error('No disponible');
    }
    return response.json();
}

function renderCameraOptions(cameras) {
    if (!refs.qrCameraSelect) return;
    const options = ['<option value="">Camara automatica</option>'];
    cameras.forEach((camera) => {
        options.push(`<option value="${escapeHtml(camera.deviceId)}">${escapeHtml(camera.label || camera.deviceId || 'Camara')}</option>`);
    });
    refs.qrCameraSelect.innerHTML = options.join('');
}

async function loadAvailableCameras(silent = false) {
    const scannerLibReady = await ensureQrScannerLibrary();
    if (!scannerLibReady) {
        if (!silent) {
            setQrCameraStatus('No fue posible cargar el escaner QR. Verifica internet o usa la app Android.', 'error');
        }
        return [];
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (!silent) {
            setQrCameraStatus('El navegador bloquea cámara en este contexto. Usa HTTPS o la app Android.', 'warning');
        }
        renderCameraOptions([]);
        return [];
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        stream.getTracks().forEach((track) => track.stop());
    } catch (_) {
        // Permitimos seguir; algunos navegadores entregan labels si ya hay permiso previo.
    }

    let cameras = [];
    try {
        cameras = await Html5Qrcode.getCameras();
    } catch (_) {
        cameras = [];
    }

    renderCameraOptions(cameras);
    if (!silent) {
        setQrCameraStatus(cameras.length ? `${cameras.length} camara(s) detectada(s)` : 'No se detectaron camaras disponibles.', cameras.length ? 'normal' : 'warning');
    }
    return cameras;
}

async function stopWebQrScanner() {
    if (qrScannerStopInFlight) {
        return;
    }
    qrScannerStopInFlight = true;
    setQrScannerButtonBusy(true);

    if (!qrScannerInstance) {
        renderScannerState(false);
        qrScannerStopInFlight = false;
        setQrScannerButtonBusy(false);
        return;
    }

    try {
        await qrScannerInstance.stop();
        await qrScannerInstance.clear();
    } catch (_) {
        // noop
    }
    qrScannerInstance = null;
    renderScannerState(false);
    setQrCameraStatus('Camara detenida.');
    qrScannerStopInFlight = false;
    setQrScannerButtonBusy(false);
}

async function startWebQrScanner() {
    if (qrScannerInstance || qrScannerStartInFlight || qrScannerStopInFlight) return;

    qrScannerStartInFlight = true;
    setQrScannerButtonBusy(true);

    const scannerLibReady = await ensureQrScannerLibrary();
    if (!scannerLibReady) {
        setQrCameraStatus('No se pudo cargar el escaner QR. Verifica internet o usa la app Android.', 'error');
        qrScannerStartInFlight = false;
        setQrScannerButtonBusy(false);
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setQrCameraStatus('La camara web requiere HTTPS o localhost en el navegador.', 'warning');
        return;
    }

    refs.qrScannerContainer.innerHTML = '';
    renderScannerState(true);
    setQrCameraStatus('Solicitando acceso a camara...');

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        stream.getTracks().forEach((track) => track.stop());
    } catch (error) {
        setQrCameraStatus(`No se concedio permiso de camara: ${error.message}`, 'error');
        renderScannerState(false);
        qrScannerStartInFlight = false;
        setQrScannerButtonBusy(false);
        return;
    }

    const cameras = await loadAvailableCameras(true);
    const selectedId = String(refs.qrCameraSelect?.value || '').trim();
    const isRear = (label) => /back|rear|trasera|environment|world/i.test(String(label || ''));
    const preferred = cameras.find((camera) => camera.deviceId === selectedId)
        || cameras.find((camera) => isRear(camera.label))
        || cameras[0]
        || null;

    const cameraConfig = preferred?.deviceId
        ? { deviceId: { exact: preferred.deviceId } }
        : { facingMode: { ideal: 'environment' } };

    const formats = typeof Html5QrcodeSupportedFormats !== 'undefined'
        ? [
            Html5QrcodeSupportedFormats.QR_CODE,
            Html5QrcodeSupportedFormats.CODE_128,
            Html5QrcodeSupportedFormats.CODE_39,
            Html5QrcodeSupportedFormats.EAN_13,
        ]
        : undefined;

    const scanner = new Html5Qrcode('qrScannerContainer');
    try {
        await scanner.start(
            cameraConfig,
            {
                fps: 15,
                qrbox: (viewfinderWidth, viewfinderHeight) => {
                    const minDim = Math.min(viewfinderWidth, viewfinderHeight);
                    const size = Math.max(200, Math.floor(minDim * 0.8));
                    return { width: size, height: size };
                },
                aspectRatio: 1.0,
                formatsToSupport: formats,
            },
            async (decodedText) => {
                const normalized = String(decodedText || '').trim();
                if (!normalized) return;
                const now = Date.now();
                if (normalized === qrLastDecodedText && (now - qrLastDecodedAtMs) < QR_SCAN_DUPLICATE_WINDOW_MS) {
                    return;
                }
                qrLastDecodedText = normalized;
                qrLastDecodedAtMs = now;
                refs.qrCodeInput.value = normalized;
                await stopWebQrScanner();
                try {
                    await verifyQr({ jumpToPagos: true, source: 'camera' });
                } catch (error) {
                    setStatus(`Error QR: ${error.message}`);
                    if (isConnectivityError(error)) {
                        setQrCameraStatus('Sin red. Reintenta al restablecer conexion.', 'warning');
                    }
                }
            },
            () => {}
        );
        qrScannerInstance = scanner;
        renderScannerState(true);
        setQrCameraStatus('Escaner activo. Apunta al QR del agente.');
    } catch (error) {
        renderScannerState(false);
        setQrCameraStatus(`No se pudo iniciar la camara: ${error.message}`, 'error');
        try {
            await scanner.clear();
        } catch (_) {
            // noop
        }
    } finally {
        qrScannerStartInFlight = false;
        setQrScannerButtonBusy(false);
    }
}

async function toggleWebQrScanner() {
    if (qrScannerInstance) {
        await stopWebQrScanner();
        return;
    }
    await startWebQrScanner();
}

function renderTotalesCobranza(totales) {
    if (!refs.totalesCard) return;
    if (!totales || typeof totales !== 'object') {
        refs.totalesCard.innerHTML = '<span class="hint">Totales no disponibles</span>';
        return;
    }

    refs.totalesCard.innerHTML = `
        <strong>Totales de cobranza</strong>
        <div class="meta">Pagado: ${formatMoney(totales.total_pagado || 0)}</div>
        <div class="meta">Pendiente: ${formatMoney(totales.total_pendiente || 0)}</div>
        <div class="meta">Abonos: ${formatMoney(totales.total_abonos || 0)}</div>
    `;
}

function renderAlertas(alertas) {
    if (!refs.alertasList) return;
    if (!Array.isArray(alertas) || !alertas.length) {
        refs.alertasList.innerHTML = '<div class="subcard empty">Sin alertas para los filtros actuales</div>';
        return;
    }

    refs.alertasList.innerHTML = alertas.slice(0, 60).map((alerta) => `
        <div class="item">
            <div class="title">Alerta #${escapeHtml(alerta.id)}</div>
            <div class="meta">Agente: ${escapeHtml(alerta.agente_id || '-')} · Semana: ${escapeHtml(alerta.semana_inicio || '-')}</div>
            <div class="meta">Motivo: ${escapeHtml(alerta.motivo || 'Sin detalle')}</div>
            <div class="meta">Fecha: ${escapeHtml(alerta.fecha_alerta ? new Date(alerta.fecha_alerta).toLocaleString() : '-')}</div>
        </div>
    `).join('');
}

function renderDatosList(payload) {
    const items = Array.isArray(payload?.data) ? payload.data : [];
    if (!items.length) {
        refs.datosList.innerHTML = '<div class="subcard empty">Sin resultados</div>';
        refs.pageInfo.textContent = `Página ${datosPage}`;
        return;
    }

    refs.datosList.innerHTML = items.map((item) => `
        <div class="item">
            <div class="title">${escapeHtml(item.alias || item.nombre || ('Registro ' + (item.id || '-')))}</div>
            <div class="meta">ID: ${escapeHtml(item.id || '-')} · Tel: ${escapeHtml(item.telefono || '-')} · VOIP: ${escapeHtml(item.numero_voip || '-')}</div>
            <div class="meta">Estado: ${item.es_activo ? '<span class="pill success">Activo</span>' : '<span class="pill danger">Inactivo</span>'} · QR: ${item.has_qr ? 'Sí' : 'No'}</div>
        </div>
    `).join('');

    refs.pageInfo.textContent = `Página ${datosPage} · ${items.length} resultados`;
}

async function loginMobile(event) {
    event.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
        setStatus('Captura usuario y contraseña');
        return;
    }

    try {
        setStatus('Autenticando...');
        const result = await apiClient.login(username, password);
        if (!result?.access_token) {
            throw new Error('No se recibió token');
        }

        apiClient.setToken(result.access_token);
        mobileToken = result.access_token;
        mobileCurrentUser = await apiClient.getMe();
        getMobileSessionStorage().setItem('currentUser', JSON.stringify(mobileCurrentUser));

        setLoggedInUi(true);
        await refreshAllOperationalData();
    } catch (error) {
        setStatus(`Login fallido: ${error.message}`);
    }
}

async function loadDashboard() {
    const cacheKey = 'dashboard';

    try {
        const [summary, network, versionInfo, appInfo] = await Promise.all([
            apiClient.getDashboardSummary(),
            apiClient.getLocalNetworkInfo(),
            apiClient.getServerVersion().catch(() => null),
            fetchAppDownloadInfo().catch(() => ({ disponible: false })),
        ]);

        renderStats(summary);
        renderNetworkInfo(network);
        renderVersionInfo(versionInfo);
        renderMobileAppInfo(appInfo);
        saveSnapshot(cacheKey, { summary, network, versionInfo, appInfo });
        return { source: 'network' };
    } catch (error) {
        const cached = readSnapshot(cacheKey);
        if (cached?.payload) {
            renderStats(cached.payload.summary);
            renderNetworkInfo(cached.payload.network);
            renderVersionInfo(cached.payload.versionInfo);
            renderMobileAppInfo(cached.payload.appInfo || { disponible: false });
            return { source: 'cache', savedAt: cached.savedAt };
        }
        throw error;
    }
}

async function verifyQr({ jumpToPagos = false, source = 'manual' } = {}) {
    const code = refs.qrCodeInput.value.trim();
    if (!code) {
        setStatus('Ingresa un código para verificar');
        return;
    }

    setStatus('Validando código QR...');
    const payload = await apiClient.verificarCodigoEscaneado(code, refs.qrWeek.value || '');
    renderQrResult(payload);
    populatePagoFromVerification(payload?.agente || {}, payload?.verificacion || {});
    await loadPagoResumen(Number(payload?.agente?.id || 0), refs.pagoWeek.value || refs.qrWeek.value || '');
    if (jumpToPagos) {
        showView('pagosView');
        setStatus(source === 'camera' ? 'QR leído. Pago listo para registrar.' : 'QR validado. Pago listo para registrar.');
    } else {
        setStatus('Código validado');
    }
}

async function loadPagos() {
    const semana = refs.pagoWeek.value || '';

    const cacheKey = `pagos:${semana || '-'}`;

    try {
        const [totales, agentes] = await Promise.all([
            apiClient.getTotalesCobranza('', semana),
            apiClient.getAgentesEstadoPago(semana, ''),
        ]);

        renderTotalesCobranza(totales?.data || totales);

        const top = Array.isArray(agentes?.data) ? agentes.data.slice(0, 8) : [];
        const listHtml = top.length
            ? top.map((item) => `<div class="item"><div class="title">${escapeHtml(item.agente_nombre || ('Agente ' + (item.agente_id || '-')))}</div><div class="meta">${getEstadoPill(item.estado_pago || '')} · Semana: ${escapeHtml(item.semana_inicio || semana || '-')}</div><div class="meta">Saldo: ${formatMoney(item.saldo_acumulado || 0)}</div></div>`).join('')
            : '<div class="subcard empty">Sin agentes en el estado de pago actual</div>';

        refs.pagoResult.classList.remove('empty');
        refs.pagoResult.innerHTML = `<strong>Top operativo</strong>${listHtml}`;
        saveSnapshot(cacheKey, {
            totales: totales?.data || totales,
            agentes: top,
            semana,
        });
        return { source: 'network' };
    } catch (error) {
        const cached = readSnapshot(cacheKey);
        if (cached?.payload) {
            renderTotalesCobranza(cached.payload.totales || null);
            const top = Array.isArray(cached.payload.agentes) ? cached.payload.agentes : [];
            const listHtml = top.length
                ? top.map((item) => `<div class="item"><div class="title">${escapeHtml(item.agente_nombre || ('Agente ' + (item.agente_id || '-')))}</div><div class="meta">${getEstadoPill(item.estado_pago || '')} · Semana: ${escapeHtml(item.semana_inicio || semana || '-')}</div><div class="meta">Saldo: ${formatMoney(item.saldo_acumulado || 0)}</div></div>`).join('')
                : '<div class="subcard empty">Sin agentes en el estado de pago actual</div>';

            refs.pagoResult.classList.remove('empty');
            refs.pagoResult.innerHTML = `<strong>Top operativo</strong>${listHtml}`;
            return { source: 'cache', savedAt: cached.savedAt };
        }
        throw error;
    }
}

async function registrarPagoRapido(liquidarTotal) {
    const agenteId = Number(refs.quickAgenteId.value || 0);
    const monto = Number(refs.quickMonto.value || 0);
    const semana = refs.pagoWeek.value || isoDateMonday();

    if (!agenteId || monto <= 0) {
        setStatus('Captura ID de agente y monto válido');
        return;
    }

    setStatus('Registrando pago...');
    const payload = {
        agente_id: agenteId,
        telefono: null,
        numero_voip: null,
        semana_inicio: semana,
        monto,
        pagado: !!liquidarTotal,
        liquidar_total: !!liquidarTotal,
        observaciones: liquidarTotal ? 'Liquidación rápida móvil' : 'Abono rápido móvil',
    };

    let pago = null;
    let isOffline = false;

    try {
        pago = await apiClient.registrarPagoSemanal(payload);
        const estado = pago?.pagado ? 'Liquidado' : 'Abono registrado';

        refs.pagoResult.classList.remove('empty');
        refs.pagoResult.innerHTML = `
            <strong>Pago registrado</strong>
            <div class="meta">Agente: ${escapeHtml(agenteId)}</div>
            <div class="meta">Monto: ${formatMoney(pago?.monto ?? monto)}</div>
            <div class="meta">Estado: ${getEstadoPill(estado)}</div>
            <div class="meta">Semana: ${escapeHtml(semana)}</div>
        `;

        await loadPagos();
        await loadPagoResumen(agenteId, semana);
        setStatus('Pago guardado correctamente');
    } catch (error) {
        // Offline fallback
        console.warn('[mobile] Offline: queuing pago', error.message);
        isOffline = true;

        const pagoLocal = {
            id: `pago_local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            ...payload,
            synced: false,
            sync_attempts: 0,
            timestamp_created: new Date().toISOString(),
        };

        // Save to offline DB
        if (offlineDb) {
            await offlineDb.savePagoLocal(pagoLocal);
        }

        // Enqueue
        if (offlineQueue) {
            offlineQueue.enqueue(pagoLocal);
        }

        // Show UI feedback
        const estado = '💾 Guardado offline';
        refs.pagoResult.classList.remove('empty');
        refs.pagoResult.innerHTML = `
            <strong>Pago guardado localmente</strong>
            <div class="meta">Agente: ${escapeHtml(agenteId)}</div>
            <div class="meta">Monto: ${formatMoney(monto)}</div>
            <div class="meta">Estado: ${getEstadoPill(estado)}</div>
            <div class="meta">Semana: ${escapeHtml(semana)}</div>
            <div class="meta">⏳ Se sincronizará al conectar</div>
        `;

        setStatus('💾 Pago guardado. Se sincronizará al conectar.');
    }
}


async function loadAlertas() {
    const semana = refs.alertasWeek.value || '';
    const cacheKey = `alertas:${semana || '-'}:${alertasSoloPendientes ? 'pending' : 'all'}`;

    try {
        const res = await apiClient.getAlertasPago(semana, alertasSoloPendientes);
        const payload = res?.data || [];
        renderAlertas(payload);
        saveSnapshot(cacheKey, payload);
        return { source: 'network' };
    } catch (error) {
        const cached = readSnapshot(cacheKey);
        if (cached) {
            renderAlertas(cached.payload || []);
            return { source: 'cache', savedAt: cached.savedAt };
        }
        throw error;
    }
}

async function procesarAlertas() {
    setStatus('Procesando alertas de pago...');
    const res = await apiClient.procesarAlertasPago();
    const nuevas = Number(res?.data?.alertas_creadas || 0);
    setStatus(`Alertas procesadas: ${nuevas} nuevas`);
    await loadAlertas();
}

async function loadDatos() {
    const cacheKey = `datos:${datosPage}:${datosSearch || '-'}`;

    try {
        const payload = await apiClient.getDatos(datosPage, datosLimit, datosSearch);
        renderDatosList(payload);
        saveSnapshot(cacheKey, payload);
        return { source: 'network' };
    } catch (error) {
        const cached = readSnapshot(cacheKey);
        if (cached?.payload) {
            renderDatosList(cached.payload);
            return { source: 'cache', savedAt: cached.savedAt };
        }
        throw error;
    }
}

function bindNativeQr() {
    const btn = document.getElementById('nativeQrBtn');
    const isNativeAvailable = !!(window.PhantomAndroid && typeof window.PhantomAndroid.startNativeQrScan === 'function');
    if (!btn) return;

    btn.style.display = isNativeAvailable ? '' : 'none';
    if (!isNativeAvailable) return;

    btn.addEventListener('click', () => {
        window.PhantomAndroid.startNativeQrScan();
    });

    window.addEventListener('phantom-native-qr-scan', (event) => {
        const code = String(event?.detail?.code || '').trim();
        if (!code) return;
        refs.qrCodeInput.value = code;
        verifyQr({ jumpToPagos: true, source: 'native' }).catch((error) => setStatus(`Error QR nativo: ${error.message}`));
    });

    const pending = String(window.__phantomNativeLastScan || '').trim();
    if (pending) {
        window.__phantomNativeLastScan = '';
        refs.qrCodeInput.value = pending;
        verifyQr({ jumpToPagos: true, source: 'native' }).catch((error) => setStatus(`Error QR nativo: ${error.message}`));
    }
}

async function refreshAllOperationalData() {
    setStatus('Actualizando datos operativos...');
    const results = await Promise.allSettled([loadDashboard(), loadPagos(), loadAlertas(), loadDatos()]);
    const fulfilled = results.filter((result) => result.status === 'fulfilled');
    const cachedHits = fulfilled.filter((result) => result.value?.source === 'cache');

    if (!fulfilled.length) {
        throw results.find((result) => result.status === 'rejected')?.reason || new Error('Sin datos disponibles');
    }

    if (cachedHits.length) {
        const latestCache = cachedHits[0]?.value?.savedAt || null;
        setStatus(`Modo local: ${getDisplayName(mobileCurrentUser)} · ${formatSnapshotStatus(latestCache)}`);
        return;
    }

    if (fulfilled.length < results.length) {
        setStatus(`Operacion parcial: ${getDisplayName(mobileCurrentUser)}`);
        return;
    }

    setStatus(`Listo: ${getDisplayName(mobileCurrentUser)}`);
}

async function bootWithToken() {
    if (!mobileToken) {
        setLoggedInUi(false);
        setStatus('Inicia sesión para continuar');
        return;
    }

    try {
        apiClient.setToken(mobileToken);
        mobileCurrentUser = await apiClient.getMe();
        getMobileSessionStorage().setItem('currentUser', JSON.stringify(mobileCurrentUser));
        setLoggedInUi(true);
        await refreshAllOperationalData();
    } catch (error) {
        const cachedUser = getCachedCurrentUser();
        if (cachedUser && isConnectivityError(error)) {
            mobileCurrentUser = cachedUser;
            setLoggedInUi(true);
            await refreshAllOperationalData();
            return;
        }

        apiClient.clearToken();
        mobileToken = '';
        setLoggedInUi(false);
        setStatus('Sesión expirada. Inicia sesión');
    }
}

function logoutMobile() {
    stopWebQrScanner().catch(() => {});
    apiClient.clearToken();
    try {
        sessionStorage.removeItem('currentUser');
        localStorage.removeItem('currentUser');
    } catch (_) {
        // noop
    }
    mobileToken = '';
    mobileCurrentUser = null;
    setLoggedInUi(false);

    refs.statsGrid.innerHTML = '';
    refs.networkCard.innerHTML = '';
    refs.versionCard.innerHTML = '';
    refs.datosList.innerHTML = '';
    refs.alertasList.innerHTML = '';
    refs.pagoResult.classList.add('empty');
    refs.pagoResult.textContent = 'Sin operaciones';
    refs.pagoResumenCard.classList.add('empty');
    refs.pagoResumenCard.textContent = 'Escanea o verifica un QR para cargar el resumen del agente.';
    refs.qrResult.classList.add('empty');
    refs.qrResult.textContent = 'Sin verificación';
    refs.sendToPagoBtn.style.display = 'none';
    setQrScannerButtonBusy(false);

    setStatus('Sesión cerrada');
}

function bindEvents() {
    document.getElementById('loginForm').addEventListener('submit', (event) => {
        loginMobile(event).catch((error) => setStatus(`Error login: ${error.message}`));
    });

    const syncNowBtn = document.getElementById('syncNowBtn');
    if (syncNowBtn) {
        syncNowBtn.addEventListener('click', async () => {
            if (!offlineSyncManager) {
                setStatus('Sincronizacion offline no disponible');
                return;
            }
            setStatus('Sincronizando...');
            try {
                await offlineSyncManager.syncNow();
                await updateSyncUI();
                setStatus('Sincronizacion completada');
            } catch (error) {
                setStatus(`Error de sincronizacion: ${error.message}`);
            }
        });
    }

    document.getElementById('logoutBtn').addEventListener('click', logoutMobile);
    document.getElementById('switchDesktopBtn').addEventListener('click', switchToDesktop);

    document.getElementById('refreshDashboardBtn').addEventListener('click', () => {
        loadDashboard().then((result) => setStatus(result?.source === 'cache' ? 'Sin red: dashboard local activo' : 'Dashboard actualizado')).catch((error) => setStatus(`Error dashboard: ${error.message}`));
    });

    document.getElementById('verifyQrBtn').addEventListener('click', () => {
        verifyQr().catch((error) => setStatus(`Error QR: ${error.message}`));
    });

    document.getElementById('sendToPagoBtn').addEventListener('click', () => {
        showView('pagosView');
        loadPagoResumen(Number(refs.quickAgenteId.value || 0), refs.pagoWeek.value || '').catch((error) => setStatus(`Error resumen: ${error.message}`));
        setStatus('Pago listo para registro');
    });

    document.getElementById('qrCameraToggleBtn').addEventListener('click', () => {
        toggleWebQrScanner().catch((error) => setStatus(`Error camara: ${error.message}`));
    });

    document.getElementById('refreshCamerasBtn').addEventListener('click', () => {
        loadAvailableCameras().catch((error) => setQrCameraStatus(error.message, 'error'));
    });

    document.getElementById('refreshPagosBtn').addEventListener('click', () => {
        loadPagos().then((result) => setStatus(result?.source === 'cache' ? 'Sin red: pagos locales visibles' : 'Pagos actualizados')).catch((error) => setStatus(`Error pagos: ${error.message}`));
    });

    document.getElementById('procesarAlertasBtn').addEventListener('click', () => {
        procesarAlertas().catch((error) => setStatus(`Error alertas: ${error.message}`));
    });

    document.getElementById('registrarAbonoBtn').addEventListener('click', () => {
        registrarPagoRapido(false).catch((error) => setStatus(`Error pago: ${error.message}`));
    });

    document.getElementById('registrarLiquidacionBtn').addEventListener('click', () => {
        registrarPagoRapido(true).catch((error) => setStatus(`Error pago: ${error.message}`));
    });

    document.getElementById('refreshAlertasBtn').addEventListener('click', () => {
        loadAlertas().then((result) => setStatus(result?.source === 'cache' ? 'Sin red: alertas locales visibles' : 'Alertas actualizadas')).catch((error) => setStatus(`Error alertas: ${error.message}`));
    });

    document.getElementById('onlyPendingBtn').addEventListener('click', (event) => {
        alertasSoloPendientes = !alertasSoloPendientes;
        event.currentTarget.classList.toggle('active-toggle', alertasSoloPendientes);
        loadAlertas().catch((error) => setStatus(`Error alertas: ${error.message}`));
    });

    document.getElementById('datosSearchBtn').addEventListener('click', () => {
        datosSearch = document.getElementById('datosSearch').value.trim();
        datosPage = 1;
        loadDatos().then((result) => setStatus(result?.source === 'cache' ? 'Sin red: datos locales visibles' : 'Datos actualizados')).catch((error) => setStatus(`Error datos: ${error.message}`));
    });

    document.getElementById('prevPageBtn').addEventListener('click', () => {
        if (datosPage <= 1) return;
        datosPage -= 1;
        loadDatos().catch((error) => setStatus(`Error datos: ${error.message}`));
    });

    document.getElementById('nextPageBtn').addEventListener('click', () => {
        datosPage += 1;
        loadDatos().catch((error) => setStatus(`Error datos: ${error.message}`));
    });

    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-view');
            if (!target) return;
            showView(target);
            if (target === 'dashboardView') {
                loadDashboard().catch((error) => setStatus(`Error dashboard: ${error.message}`));
            }
            if (target === 'pagosView') {
                Promise.all([
                    loadPagos(),
                    loadPagoResumen(Number(refs.quickAgenteId.value || 0), refs.pagoWeek.value || ''),
                ]).catch((error) => setStatus(`Error pagos: ${error.message}`));
            }
            if (target === 'alertasView') {
                loadAlertas().catch((error) => setStatus(`Error alertas: ${error.message}`));
            }
            if (target === 'datosView') {
                loadDatos().catch((error) => setStatus(`Error datos: ${error.message}`));
            }
        });
    });

    window.addEventListener('focus', () => {
        if (!mobileToken) return;
        if (activeViewId === 'dashboardView') {
            loadDashboard().catch(() => {});
        }
    });

    window.addEventListener('app:session-invalid', () => {
        logoutMobile();
        setStatus('La sesión dejó de ser válida. Inicia sesión de nuevo.');
    });
}

/**
 * Initialize offline-first synchronization system
 */
async function initializeOfflineSync() {
    try {
        // Dynamically load modules from CDN/script (in real setup, these would be imported)
        // For now, we'll wait for them to be available globally
        if (typeof LocalDb === 'undefined') {
            console.warn('[offline-sync] LocalDb not loaded yet, retrying...');
            return;
        }

        offlineDb = new LocalDb();
        await offlineDb.initDb();

        offlineConflictResolver = new ConflictResolver();
        offlineSyncManager = new SyncManager(apiClient, offlineDb, offlineConflictResolver);
        offlineQueue = new OfflineQueue();

        // Start auto-sync every 10 minutes
        offlineSyncManager.startAutoSync(600000);

        console.log('[offline-sync] Initialized successfully. Auto-sync: every 10 min');

        // Wire online/offline events
        window.addEventListener('online', () => {
            console.log('[offline-sync] Online detected - syncing now');
            setStatus('Conexion restablecida. Sincronizando...');
            offlineSyncManager.syncNow().catch(err => console.error('[offline-sync] Sync error:', err));
        });

        window.addEventListener('offline', () => {
            console.log('[offline-sync] Offline mode - queueing enabled');
            setStatus(`Modo local: ${getDisplayName(mobileCurrentUser)} · sin conexion`);
        });

        // Listen for sync updates
        window.addEventListener('offline:sync-complete', async (e) => {
            console.log('[offline-sync] Sync complete', e.detail);
            updateSyncUI();
            await loadPagos().catch(() => {});
        });

        // Listen for queue updates
        window.addEventListener('offline:queue-updated', (e) => {
            console.log('[offline-sync] Queue updated', e.detail);
            updatePendingBadge(e.detail.queue_length);
        });

        // Listen for sync errors
        window.addEventListener('offline:sync-error', (e) => {
            console.error('[offline-sync] Error:', e.detail);
            setStatus(`⚠️ Error sync: ${e.detail.error}`);
        });

        // Update UI
        await updateSyncUI();
    } catch (error) {
        console.error('[offline-sync] Initialization failed:', error);
        setStatus(`Offline-sync error: ${error.message}`);
    }
}

/**
 * Update sync status UI
 */
async function updateSyncUI() {
    if (!offlineDb || !offlineSyncManager) return;

    const status = await offlineDb.getSyncStatus();
    const syncBanner = document.getElementById('syncStatusBanner');

    if (status.pending_pagos_count > 0) {
        if (syncBanner) {
            syncBanner.style.display = 'flex';
            document.getElementById('pendingPagosCount').textContent = status.pending_pagos_count;
            if (status.last_sync_time) {
                const lastSync = new Date(status.last_sync_time);
                const minAgo = Math.round((Date.now() - lastSync) / 60000);
                document.getElementById('lastSyncText').textContent = 
                    minAgo < 1 ? 'Ahora' : `Hace ${minAgo} min`;
            }
        }
    } else {
        if (syncBanner) {
            syncBanner.style.display = 'none';
        }
    }
}

/**
 * Update pending pagos badge
 */
function updatePendingBadge(count) {
    const badge = document.getElementById('pendingPagosBadge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }
}

/**
 * Show conflict resolution modal
 */
function showConflictModal(review) {
    const modal = document.getElementById('offlineConflictModal');
    if (!modal) {
        console.error('Conflict modal not found in DOM');
        return;
    }

    const prompt = offlineConflictResolver.getReviewPrompt(review.review_id);
    if (!prompt) {
        console.error('No prompt data for review', review.review_id);
        return;
    }

    // Populate modal
    document.getElementById('conflictTitle').textContent = `${prompt.title} - Agente #${prompt.details.agente}`;
    document.getElementById('conflictMessage').textContent = prompt.message;

    const detailsDiv = document.getElementById('conflictDetails');
    detailsDiv.innerHTML = `
        <div style="margin-bottom: 15px;">
            <strong>Mi pago:</strong> $${prompt.details.local.monto.toFixed(2)} (${prompt.details.local.estado})
            <br/>
            <strong>Pago servidor:</strong> $${prompt.details.server[0]?.monto.toFixed(2) || '0.00'} (${prompt.details.server[0]?.estado || 'N/A'})
        </div>
    `;

    // Clear old button handlers
    const oldKeepBoth = document.getElementById('conflictKeepBoth');
    const oldKeepLocal = document.getElementById('conflictKeepLocal');
    const oldKeepServer = document.getElementById('conflictKeepServer');

    oldKeepBoth?.replaceWith(oldKeepBoth.cloneNode(true));
    oldKeepLocal?.replaceWith(oldKeepLocal.cloneNode(true));
    oldKeepServer?.replaceWith(oldKeepServer.cloneNode(true));

    // Rebind handlers
    document.getElementById('conflictKeepBoth').addEventListener('click', async () => {
        const result = await offlineConflictResolver.resolveConflict(review.review_id, 'keep_both');
        if (result.success) {
            modal.style.display = 'none';
            setStatus(`✅ Resuelto: se mantienen ambos pagos`);
            await loadPagos().catch(() => {});
        }
    });

    document.getElementById('conflictKeepLocal').addEventListener('click', async () => {
        const result = await offlineConflictResolver.resolveConflict(review.review_id, 'keep_local');
        if (result.success) {
            modal.style.display = 'none';
            setStatus(`✅ Resuelto: se usa mi pago local`);
            await loadPagos().catch(() => {});
        }
    });

    document.getElementById('conflictKeepServer').addEventListener('click', async () => {
        const result = await offlineConflictResolver.resolveConflict(review.review_id, 'keep_server');
        if (result.success) {
            modal.style.display = 'none';
            setStatus(`✅ Resuelto: se usan pagos del servidor`);
            await loadPagos().catch(() => {});
        }
    });

    modal.style.display = 'flex';
}

(function bootstrap() {
    if (typeof apiClient?.setAuthPersistence === 'function') {
        apiClient.setAuthPersistence(isInsideNativeApp() ? 'session' : 'local');
    }
    clearPersistentAuthCacheForNativeRuntime();
    mobileToken = apiClient.getToken() || '';

    clearDesktopOverride();
    const monday = isoDateMonday();
    refs.qrWeek.value = monday;
    refs.pagoWeek.value = monday;
    refs.alertasWeek.value = monday;

    applyNativeAppChrome();
    // Debe ejecutarse antes de cualquier accion de UI para login/logout/tab switch.
    bindEvents();
    bindNativeQr();
    loadAvailableCameras(true).catch(() => {});
    initializeOfflineSync().catch(err => console.warn('[offline-sync] Init failed:', err));
    bootWithToken().catch(() => {
        setLoggedInUi(false);
        setStatus('No se pudo iniciar la vista móvil');
    });
})();
