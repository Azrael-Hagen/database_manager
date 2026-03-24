/**
 * Smart Import – three-step wizard for intelligent file imports.
 *
 * Step 1: Upload → analyze (auto-detect columns + suggest mappings)
 * Step 2: Review / edit column→field mapping → preview changes
 * Step 3: Confirm mode and execute
 */

'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let _siAnalysis = null;      // result from /api/smart-import/analyze
let _siPreview  = null;      // result from /api/smart-import/preview
let _siFileContent = null;   // File object carried through all steps

// ---------------------------------------------------------------------------
// Tab switcher (Classic ↔ Intelligent)
// ---------------------------------------------------------------------------

function smartImportSetTab(tab) {
    document.getElementById('importClassicTab').style.display  = tab === 'classic'     ? '' : 'none';
    document.getElementById('importSmartTab').style.display    = tab === 'intelligent' ? '' : 'none';
    document.getElementById('importTabClassic').classList.toggle('active', tab === 'classic');
    document.getElementById('importTabSmart').classList.toggle('active', tab === 'intelligent');
}

// ---------------------------------------------------------------------------
// Step 1 – Analyze
// ---------------------------------------------------------------------------

async function smartAnalyzeFile() {
    const fileInput = document.getElementById('siFileInput');
    const delimInput = document.getElementById('siDelimitador');
    const file = fileInput?.files?.[0];

    if (!file) {
        alert('Selecciona un archivo primero.');
        return;
    }
    _siFileContent = file;

    const statusEl = document.getElementById('siAnalysisStatus');
    statusEl.textContent = 'Analizando…';
    statusEl.style.color = '#4a90d9';

    const formData = new FormData();
    formData.append('archivo', file);
    formData.append('delimitador', delimInput?.value || ',');

    try {
        const resp = await fetch(`${API_URL}/smart-import/analyze`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${authToken}` },
            body: formData,
        });
        const body = await resp.json();

        if (!resp.ok) {
            statusEl.textContent = body.detail || 'Error al analizar.';
            statusEl.style.color = '#e74c3c';
            return;
        }

        _siAnalysis = body.datos;
        statusEl.textContent = `${_siAnalysis.total_filas} fila(s) detectada(s).`;
        statusEl.style.color = '#2ecc71';

        _siRenderStep1Results(_siAnalysis);
    } catch (err) {
        statusEl.textContent = `Error de red: ${err.message}`;
        statusEl.style.color = '#e74c3c';
    }
}

function _siRenderStep1Results(analysis) {
    const container = document.getElementById('siStep1Results');
    if (!container) return;

    const { columnas_detectadas: cols, muestra, errores } = analysis;

    let html = '';

    if (errores?.length) {
        html += `<p class="hint" style="color:#e74c3c">${errores.map(escapeHtml).join('<br>')}</p>`;
    }

    if (cols.length === 0) {
        container.innerHTML = html || '<p class="hint">No se detectaron columnas.</p>';
        return;
    }

    // Column detection table
    html += '<h4 style="margin-top:12px;">Detección de Columnas</h4>';
    html += '<table class="data-table" style="font-size:0.85em;">';
    html += '<thead><tr><th>Columna Detectada</th><th>Campo Sugerido</th><th>Confianza</th><th>Tipo</th></tr></thead><tbody>';
    cols.forEach(c => {
        const badge = c.tipo === 'exacta'    ? '<span style="color:#2ecc71">●</span>'
                    : c.tipo === 'sinonimo'  ? '<span style="color:#3498db">●</span>'
                    : c.tipo === 'fuzzy'     ? '<span style="color:#f39c12">●</span>'
                    :                          '<span style="color:#e74c3c">●</span>';
        const pct = (c.confianza * 100).toFixed(0);
        html += `<tr>
            <td>${escapeHtml(c.header)}</td>
            <td>${c.campo ? escapeHtml(c.campo) : '<em>sin sugerencia</em>'}</td>
            <td>${pct}%</td>
            <td>${badge} ${escapeHtml(c.tipo)}</td>
        </tr>`;
    });
    html += '</tbody></table>';

    // Sample
    if (muestra?.length) {
        const sampleHeaders = Object.keys(muestra[0]);
        html += '<h4 style="margin-top:16px;">Muestra (primeras 5 filas)</h4>';
        html += '<div style="overflow-x:auto"><table class="data-table" style="font-size:0.8em;">';
        html += '<thead><tr>' + sampleHeaders.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr></thead>';
        html += '<tbody>';
        muestra.forEach(row => {
            html += '<tr>' + sampleHeaders.map(h => `<td>${escapeHtml(row[h] ?? '')}</td>`).join('') + '</tr>';
        });
        html += '</tbody></table></div>';
    }

    container.innerHTML = html;

    // Show step 2 button
    document.getElementById('siGoStep2Btn').style.display = '';
}

// ---------------------------------------------------------------------------
// Step 2 – Mapping + Preview
// ---------------------------------------------------------------------------

const CANONICAL_FIELDS = [
    '', 'nombre', 'email', 'telefono', 'empresa', 'ciudad', 'pais',
    'alias', 'ubicacion', 'fp', 'fc', 'grupo', 'numero_voip',
];

function siGoToStep2() {
    if (!_siAnalysis) return;
    _siRenderMappingTable(_siAnalysis.columnas_detectadas);
    siSetStep(2);
}

function siSetStep(n) {
    [1, 2, 3].forEach(i => {
        const el = document.getElementById(`siStep${i}`);
        if (el) el.style.display = i === n ? '' : 'none';
    });
}

function _siRenderMappingTable(cols) {
    const tbody = document.getElementById('siMappingBody');
    if (!tbody) return;

    tbody.innerHTML = '';
    cols.forEach((c, idx) => {
        const tr = document.createElement('tr');
        const tdHeader = document.createElement('td');
        tdHeader.textContent = c.header;

        const tdField = document.createElement('td');
        const sel = document.createElement('select');
        sel.className = 'si-field-sel';
        sel.dataset.header = c.header;
        CANONICAL_FIELDS.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f;
            opt.textContent = f || '— ignorar —';
            if (f === c.campo) opt.selected = true;
            sel.appendChild(opt);
        });
        tdField.appendChild(sel);

        const tdConf = document.createElement('td');
        const pct = (c.confianza * 100).toFixed(0);
        const color = c.confianza >= 0.9 ? '#2ecc71' : c.confianza >= 0.75 ? '#f39c12' : '#e74c3c';
        tdConf.innerHTML = `<span style="color:${color}">${pct}%</span>`;

        tr.appendChild(tdHeader);
        tr.appendChild(tdField);
        tr.appendChild(tdConf);
        tbody.appendChild(tr);
    });
}

function _siGetCurrentMapping() {
    const mapping = {};
    document.querySelectorAll('.si-field-sel').forEach(sel => {
        mapping[sel.dataset.header] = sel.value;
    });
    return mapping;
}

async function siPreview() {
    if (!_siFileContent || !_siAnalysis) return;

    const statusEl = document.getElementById('siPreviewStatus');
    statusEl.textContent = 'Generando vista previa…';

    const mapping = _siGetCurrentMapping();
    const delimInput = document.getElementById('siDelimitador');

    const formData = new FormData();
    formData.append('archivo', _siFileContent);
    formData.append('delimitador', delimInput?.value || ',');
    formData.append('mapeo', JSON.stringify(mapping));

    try {
        const resp = await fetch(`${API_URL}/smart-import/preview`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${authToken}` },
            body: formData,
        });
        const body = await resp.json();

        if (!resp.ok) {
            statusEl.textContent = body.detail || 'Error en preview.';
            statusEl.style.color = '#e74c3c';
            return;
        }

        _siPreview = body.datos;
        statusEl.textContent = '';
        _siRenderPreviewSummary(_siPreview);
        document.getElementById('siGoStep3Btn').style.display = '';
    } catch (err) {
        statusEl.textContent = `Error de red: ${err.message}`;
        statusEl.style.color = '#e74c3c';
    }
}

function _siRenderPreviewSummary(preview) {
    const el = document.getElementById('siPreviewSummary');
    if (!el) return;

    const { nuevos, actualizaciones, sin_cambios, filas_preview, errores_formato } = preview;
    const total = filas_preview.length + (errores_formato?.length || 0);

    let html = `<div class="stats-grid" style="margin:12px 0; grid-template-columns: repeat(auto-fit, minmax(130px,1fr));">
        <div class="stat-card"><div class="stat-number" style="color:#2ecc71">${nuevos}</div><div class="stat-label">Nuevos</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#3498db">${actualizaciones}</div><div class="stat-label">Actualizaciones</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#95a5a6">${sin_cambios}</div><div class="stat-label">Sin Cambios</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#e74c3c">${errores_formato?.length || 0}</div><div class="stat-label">Errores de Formato</div></div>
    </div>`;

    if (errores_formato?.length) {
        html += `<p class="hint" style="color:#e74c3c">${errores_formato.map(escapeHtml).join('<br>')}</p>`;
    }

    // First 10 rows preview
    const rows = filas_preview.slice(0, 10);
    if (rows.length) {
        html += '<h4 style="margin-top:12px;">Vista previa (primeras 10 filas)</h4>';
        html += '<table class="data-table" style="font-size:0.8em;"><thead><tr><th>#</th><th>Acción</th><th>¿Tiene Número?</th><th>Campos Mapeados</th></tr></thead><tbody>';
        rows.forEach(r => {
            const color = r.accion === 'nuevo' ? '#2ecc71'
                        : r.accion === 'actualizar' ? '#3498db'
                        : '#95a5a6';
            const numCell = r.tiene_numero === null ? '—'
                          : r.tiene_numero ? '<span style="color:#2ecc71">✓ Sí</span>'
                          : '<span style="color:#e74c3c">✗ No</span>';
            const campos = Object.entries(r.datos_mapeados)
                .slice(0, 4)
                .map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(v)}`)
                .join(', ');

            html += `<tr>
                <td>${r.fila}</td>
                <td><span style="color:${color};font-weight:bold">${escapeHtml(r.accion)}</span></td>
                <td>${numCell}</td>
                <td style="font-size:0.9em">${campos}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        if (filas_preview.length > 10) {
            html += `<p class="hint">… y ${filas_preview.length - 10} fila(s) más.</p>`;
        }
    }

    el.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Step 3 – Execute
// ---------------------------------------------------------------------------

function siGoToStep3() {
    siSetStep(3);
}

async function siExecuteImport() {
    if (!_siFileContent || !_siAnalysis) return;

    const modeEl = document.getElementById('siModo');
    const delimInput = document.getElementById('siDelimitador');
    const statusEl = document.getElementById('siExecuteStatus');
    statusEl.textContent = 'Importando…';
    statusEl.style.color = '#4a90d9';

    const mapping = _siGetCurrentMapping();

    const formData = new FormData();
    formData.append('archivo', _siFileContent);
    formData.append('delimitador', delimInput?.value || ',');
    formData.append('mapeo', JSON.stringify(mapping));
    formData.append('modo', modeEl?.value || 'insertar');

    try {
        const resp = await fetch(`${API_URL}/smart-import/execute`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${authToken}` },
            body: formData,
        });
        const body = await resp.json();

        if (!resp.ok) {
            statusEl.textContent = body.detail || 'Error al importar.';
            statusEl.style.color = '#e74c3c';
            return;
        }

        const d = body.datos;
        statusEl.innerHTML = `<span style="color:#2ecc71">✓ Completado:</span>
            ${d.insertados} insertado(s), ${d.actualizados} actualizado(s), ${d.omitidos} omitido(s)
            ${d.errores?.length ? `<br><span style="color:#e74c3c">${d.errores.length} error(es): ${d.errores.slice(0,3).join('; ')}</span>` : ''}`;

        // Reset wizard for a new import
        setTimeout(() => {
            _siAnalysis = null;
            _siPreview = null;
            _siFileContent = null;
            siSetStep(1);
            document.getElementById('siStep1Results').innerHTML = '';
            document.getElementById('siAnalysisStatus').textContent = '';
            document.getElementById('siGoStep2Btn').style.display = 'none';
            statusEl.textContent = '';
        }, 4000);
    } catch (err) {
        statusEl.textContent = `Error de red: ${err.message}`;
        statusEl.style.color = '#e74c3c';
    }
}
