(function bootstrapAppUtils(global) {
    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function getErrorMessage(error, fallback = 'Error inesperado') {
        if (!error) return fallback;
        if (typeof error === 'string') {
            const text = error.trim();
            return text || fallback;
        }
        if (typeof error.message === 'string' && error.message.trim()) {
            return error.message.trim();
        }
        if (typeof error.name === 'string' && error.name.trim()) {
            return error.name.trim();
        }
        try {
            const raw = JSON.stringify(error);
            return raw && raw !== '{}' ? raw : fallback;
        } catch (_) {
            return fallback;
        }
    }

    function ensureAppAlertRoot() {
        let root = document.getElementById('appAlertRoot');
        if (root) return root;

        root = document.createElement('div');
        root.id = 'appAlertRoot';
        root.className = 'app-alert-backdrop';
        root.style.display = 'none';
        root.innerHTML = `
            <div class="app-alert-modal" role="alertdialog" aria-modal="true" aria-labelledby="appAlertTitle" aria-describedby="appAlertMessage">
                <div class="app-alert-header">
                    <div class="app-alert-badge" id="appAlertBadge">Aviso</div>
                    <button type="button" class="app-alert-close" id="appAlertCloseBtn" aria-label="Cerrar">×</button>
                </div>
                <h3 id="appAlertTitle" class="app-alert-title">Aviso del sistema</h3>
                <div id="appAlertMessage" class="app-alert-message"></div>
                <div id="appAlertDetail" class="app-alert-detail" style="display:none;"></div>
                <div class="app-alert-actions">
                    <button type="button" class="btn" id="appAlertAcceptBtn">Aceptar</button>
                </div>
            </div>
        `;
        document.body.appendChild(root);

        const close = () => {
            root.style.display = 'none';
            root.classList.remove('visible');
        };

        root.addEventListener('click', event => {
            if (event.target === root) close();
        });
        root.querySelector('#appAlertAcceptBtn')?.addEventListener('click', close);
        root.querySelector('#appAlertCloseBtn')?.addEventListener('click', close);
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && root.classList.contains('visible')) {
                close();
            }
        });

        return root;
    }

    function showAppAlert(message, options = {}) {
        const root = ensureAppAlertRoot();
        const modal = root.querySelector('.app-alert-modal');
        const badge = root.querySelector('#appAlertBadge');
        const titleEl = root.querySelector('#appAlertTitle');
        const messageEl = root.querySelector('#appAlertMessage');
        const detailEl = root.querySelector('#appAlertDetail');
        const tone = String(options.tone || 'info').trim().toLowerCase();
        const title = String(options.title || (tone === 'error' ? 'Atención requerida' : 'Aviso del sistema'));
        const detail = String(options.detail || '').trim();
        const html = typeof options.html === 'string' ? options.html : '';
        const text = String(message || '').trim();
        const badgeText = tone === 'error' ? 'Error' : tone === 'success' ? 'Listo' : tone === 'warning' ? 'Revisar' : 'Aviso';

        modal.classList.remove('info', 'success', 'warning', 'error');
        modal.classList.add(tone);
        badge.textContent = badgeText;
        titleEl.textContent = title;
        if (html) {
            messageEl.innerHTML = html;
        } else {
            messageEl.innerHTML = `<p>${escapeHtml(text)}</p>`;
        }

        if (detail) {
            detailEl.style.display = 'block';
            detailEl.textContent = detail;
        } else {
            detailEl.style.display = 'none';
            detailEl.textContent = '';
        }

        root.style.display = 'flex';
        root.classList.add('visible');
        root.querySelector('#appAlertAcceptBtn')?.focus();
    }

    function formatDateTimeSafe(value) {
        if (!value) return '-';
        const dt = new Date(value);
        if (Number.isNaN(dt.getTime())) return '-';
        return dt.toLocaleString();
    }

    function toDateTimeLocalValue(value) {
        if (!value) return '';
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return '';
        const pad = number => String(number).padStart(2, '0');
        const year = parsed.getFullYear();
        const month = pad(parsed.getMonth() + 1);
        const day = pad(parsed.getDate());
        const hours = pad(parsed.getHours());
        const minutes = pad(parsed.getMinutes());
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    function formatDisplayDateTime(value) {
        if (!value) return '-';
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return String(value);
        return parsed.toLocaleString('es-MX', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    global.AppUtils = {
        escapeHtml,
        getErrorMessage,
        ensureAppAlertRoot,
        showAppAlert,
        formatDateTimeSafe,
        toDateTimeLocalValue,
        formatDisplayDateTime,
    };
})(window);
