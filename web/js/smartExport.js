/**
 * Smart Export – flexible data export with field selection, pattern filters,
 * and multiple output formats (CSV, Excel, TXT, DAT).
 */

'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let _seAvailableTables  = [];   // from /api/smart-export/tables
let _seAvailableFields  = [];   // from /api/smart-export/fields/{table}
let _seSelectedTable    = '';
let _seFilterCount      = 0;

// ---------------------------------------------------------------------------
// Initialize section
// ---------------------------------------------------------------------------

async function exportCargarTablas() {
    const sel = document.getElementById('seTablaSelect');
    if (!sel) return;
    sel.innerHTML = '<option value="">Cargando tablas…</option>';
    sel.disabled = true;

    try {
        const resp = await fetch(`${API_URL}/smart-export/tables`, {
            headers: { Authorization: `Bearer ${authToken}` },
        });
        if (!resp.ok) throw new Error(resp.statusText);
        const body = await resp.json();

        _seAvailableTables = body.tablas || [];
        sel.innerHTML = '<option value="">— Selecciona una tabla —</option>';
        _seAvailableTables.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            sel.appendChild(opt);
        });
        sel.disabled = false;
    } catch (err) {
        sel.innerHTML = '<option value="">Error al cargar tablas</option>';
        console.error('exportCargarTablas:', err);
    }
    // Reset downstream UI
    _seResetFields();
    document.getElementById('seFiltersContainer').innerHTML = '';
    _seFilterCount = 0;
}

// ---------------------------------------------------------------------------
// Field loading
// ---------------------------------------------------------------------------

async function exportSeleccionarTabla() {
    const sel = document.getElementById('seTablaSelect');
    _seSelectedTable = sel?.value || '';

    _seResetFields();
    if (!_seSelectedTable) return;

    const statusEl = document.getElementById('seFieldsStatus');
    statusEl.textContent = 'Cargando campos…';

    try {
        const resp = await fetch(`${API_URL}/smart-export/fields/${encodeURIComponent(_seSelectedTable)}`, {
            headers: { Authorization: `Bearer ${authToken}` },
        });
        const body = await resp.json();

        if (!resp.ok) {
            statusEl.textContent = body.detail || 'Error al cargar campos.';
            return;
        }

        _seAvailableFields = body.campos || [];
        statusEl.textContent = '';
        _seRenderFieldCheckboxes(_seAvailableFields);

        // Also update filter campo selects
        _seRefreshFilterFieldOptions();
    } catch (err) {
        statusEl.textContent = `Error de red: ${err.message}`;
    }
}

function _seResetFields() {
    const container = document.getElementById('seFieldsContainer');
    if (container) container.innerHTML = '<p class="hint">Selecciona una tabla para ver los campos disponibles.</p>';
    _seAvailableFields = [];
    document.getElementById('seFieldsStatus').textContent = '';
}

function _seRenderFieldCheckboxes(fields) {
    const container = document.getElementById('seFieldsContainer');
    if (!container) return;

    // "Select all" header
    let html = `<div style="margin-bottom:8px;">
        <label><input type="checkbox" id="seSelectAll" onchange="_seToggleAll(this.checked)"> <strong>Seleccionar todos</strong></label>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px 16px;">`;

    fields.forEach(f => {
        const typeHint = f.tipo ? ` <small class="hint">(${escapeHtml(f.tipo)})</small>` : '';
        html += `<label style="min-width:160px;cursor:pointer;">
            <input type="checkbox" class="se-field-chk" name="seField" value="${escapeHtml(f.campo)}" checked>
            ${escapeHtml(f.campo)}${typeHint}
        </label>`;
    });
    html += '</div>';

    container.innerHTML = html;
}

function _seToggleAll(checked) {
    document.querySelectorAll('.se-field-chk').forEach(chk => { chk.checked = checked; });
}

function _seGetSelectedFields() {
    return Array.from(document.querySelectorAll('.se-field-chk:checked')).map(c => c.value);
}

// ---------------------------------------------------------------------------
// Filter builder
// ---------------------------------------------------------------------------

const OPERATOR_LABELS = {
    eq:          '= igual a',
    neq:         '≠ diferente de',
    contains:    'contiene',
    starts_with: 'empieza con',
    ends_with:   'termina en',
    gt:          '> mayor que',
    lt:          '< menor que',
    gte:         '>= mayor o igual',
    lte:         '<= menor o igual',
    is_null:     'es nulo',
    is_not_null: 'no es nulo',
    in:          'en lista (a,b,c)',
};

function exportAgregarFiltro() {
    if (!_seSelectedTable || _seAvailableFields.length === 0) {
        alert('Selecciona una tabla primero.');
        return;
    }

    _seFilterCount++;
    const id = _seFilterCount;
    const container = document.getElementById('seFiltersContainer');
    const row = document.createElement('div');
    row.className = 'se-filter-row';
    row.id = `seFilter_${id}`;
    row.style.cssText = 'display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap;';

    // Campo select
    const campoSel = document.createElement('select');
    campoSel.className = 'se-filter-campo';
    campoSel.style.cssText = 'flex:1;min-width:150px;';
    _seAvailableFields.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.campo;
        opt.textContent = f.campo;
        campoSel.appendChild(opt);
    });

    // Operator select
    const opSel = document.createElement('select');
    opSel.className = 'se-filter-op';
    opSel.style.cssText = 'flex:1;min-width:160px;';
    opSel.onchange = () => _seUpdateFilterValueVisibility(opSel, valueInput);
    Object.entries(OPERATOR_LABELS).forEach(([val, label]) => {
        const opt = document.createElement('option');
        opt.value = val;
        opt.textContent = label;
        opSel.appendChild(opt);
    });

    // Value input
    const valueInput = document.createElement('input');
    valueInput.type = 'text';
    valueInput.className = 'se-filter-valor';
    valueInput.placeholder = 'Valor…';
    valueInput.style.cssText = 'flex:2;min-width:150px;';

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-small';
    removeBtn.style.cssText = 'background:#e74c3c;color:#fff;padding:4px 10px;';
    removeBtn.textContent = '✕';
    removeBtn.onclick = () => container.removeChild(row);

    row.appendChild(campoSel);
    row.appendChild(opSel);
    row.appendChild(valueInput);
    row.appendChild(removeBtn);
    container.appendChild(row);
}

function _seUpdateFilterValueVisibility(opSel, valueInput) {
    const noValue = ['is_null', 'is_not_null'].includes(opSel.value);
    valueInput.style.display = noValue ? 'none' : '';
    valueInput.disabled = noValue;
}

function _seRefreshFilterFieldOptions() {
    document.querySelectorAll('.se-filter-campo').forEach(sel => {
        const currentVal = sel.value;
        sel.innerHTML = '';
        _seAvailableFields.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f.campo;
            opt.textContent = f.campo;
            if (f.campo === currentVal) opt.selected = true;
            sel.appendChild(opt);
        });
    });
}

function _seGetFilters() {
    const filters = [];
    document.querySelectorAll('[id^="seFilter_"]').forEach(row => {
        const campo    = row.querySelector('.se-filter-campo')?.value;
        const operador = row.querySelector('.se-filter-op')?.value;
        const valorEl  = row.querySelector('.se-filter-valor');
        const valor    = valorEl?.disabled ? null : (valorEl?.value || null);
        if (campo && operador) {
            filters.push({ campo, operador, valor });
        }
    });
    return filters;
}

// ---------------------------------------------------------------------------
// Execute export
// ---------------------------------------------------------------------------

async function exportEjecutar() {
    if (!_seSelectedTable) {
        alert('Selecciona una tabla.');
        return;
    }

    const campos = _seGetSelectedFields();
    if (campos.length === 0) {
        alert('Selecciona al menos un campo.');
        return;
    }

    const formato       = document.getElementById('seFormato')?.value || 'csv';
    const nombreArchivo = document.getElementById('seNombreArchivo')?.value.trim() || null;
    const limiteRaw     = document.getElementById('seLimite')?.value;
    const limite        = limiteRaw ? parseInt(limiteRaw, 10) : null;
    const filtros       = _seGetFilters();

    const payload = {
        tabla: _seSelectedTable,
        campos,
        filtros,
        formato,
        nombre_archivo: nombreArchivo || undefined,
        limite: limite || undefined,
    };

    const statusEl = document.getElementById('seExportStatus');
    statusEl.textContent = 'Exportando…';
    statusEl.style.color = '#4a90d9';

    try {
        const resp = await fetch(`${API_URL}/smart-export/export`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${authToken}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            statusEl.textContent = body.detail || `Error ${resp.status}`;
            statusEl.style.color = '#e74c3c';
            return;
        }

        // Trigger browser download
        const cd   = resp.headers.get('content-disposition') || '';
        const match = cd.match(/filename=([^;\s]+)/);
        const filename = match?.[1] || `export.${formato}`;

        const blob = await resp.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        statusEl.textContent = `✓ Descargado: ${filename}`;
        statusEl.style.color = '#2ecc71';
    } catch (err) {
        statusEl.textContent = `Error de red: ${err.message}`;
        statusEl.style.color = '#e74c3c';
    }
}
