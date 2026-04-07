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
    const isSmart = tab === 'smart' || tab === 'intelligent';
    const classicTab = document.getElementById('importClassicTab');
    const smartTab = document.getElementById('importSmartTab');
    const classicBtn = document.getElementById('siTabClassicBtn');
    const smartBtn = document.getElementById('siTabSmartBtn');

    if (classicTab) classicTab.style.display = isSmart ? 'none' : '';
    if (smartTab) smartTab.style.display = isSmart ? '' : 'none';
    if (classicBtn) classicBtn.classList.toggle('active', !isSmart);
    if (smartBtn) smartBtn.classList.toggle('active', isSmart);
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
        const detectedRow = _siAnalysis.detected_header_row ?? 0;
        const rowInfo = detectedRow > 0 ? ` (fila de encabezado detectada: ${detectedRow + 1})` : '';
        statusEl.textContent = `${_siAnalysis.total_filas} fila(s) detectada(s).${rowInfo}`;
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

    // Detected header row info
    const detRow = analysis.detected_header_row ?? 0;
    if (detRow > 0) {
        html += `<p class="hint" style="color:#4a90d9;">ℹ️ Fila de encabezado detectada automáticamente: fila ${detRow + 1}</p>`;
    }

    // Multi-table regions
    const regiones = analysis.tabla_regiones || [];
    if (regiones.length > 1) {
        html += `<p class="hint" style="color:#9b59b6;">📋 Se detectaron ${regiones.length} tablas en la misma hoja.</p>`;
    }

    // Column detection table
    html += '<h4 style="margin-top:12px;">Detección de Columnas</h4>';
    html += '<table class="data-table" style="font-size:0.85em;">';
    html += '<thead><tr><th>Columna Detectada</th><th>Campo Sugerido</th><th>Confianza</th><th>Tipo</th><th>Evidencia</th></tr></thead><tbody>';
    cols.forEach(c => {
        const badgeColor = {
            exacta:          '#2ecc71',
            sinonimo:        '#3498db',
            fuzzy:           '#f39c12',
            valor_patron:    '#9b59b6',
            perfil_guardado: '#1abc9c',
            combinado:       '#3498db',
        }[c.tipo] || '#e74c3c';
        const badge = `<span style="color:${badgeColor}">●</span>`;
        const pct = (c.confianza * 100).toFixed(0);
        const evidencia = (c.evidencia || []).map(e => `<span style="font-size:0.8em;color:#999">${escapeHtml(e)}</span>`).join(' ');
        html += `<tr>
            <td>${escapeHtml(c.header)}</td>
            <td>${c.campo ? escapeHtml(c.campo) : '<em>sin sugerencia</em>'}</td>
            <td>${pct}%</td>
            <td>${badge} ${escapeHtml(c.tipo)}</td>
            <td>${evidencia || '—'}</td>
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
    'alias', 'ubicacion', 'fp', 'fc', 'fcc', 'grupo', 'numero_voip',
    'imei', 'deuda', 'extension',
];

const FIELD_DESCRIPTIONS = {
    'nombre':      'Nombre completo del agente',
    'alias':       'Identificador corto / apodo operativo',
    'email':       'Correo electrónico',
    'telefono':    'Número de teléfono o celular',
    'extension':   'Extensión telefónica interna',
    'empresa':     'Empresa u organización',
    'ciudad':      'Ciudad',
    'pais':        'País',
    'ubicacion':   'Sede o ubicación física',
    'fp':          'Fecha de primer pago',
    'fc':          'Fecha de cobro regular',
    'fcc':         'Fecha de cobro de cheque',
    'grupo':       'Grupo o equipo al que pertenece',
    'numero_voip': 'Número de línea VoIP asignada',
    'imei':        'Identificador de equipo (IMEI)',
    'deuda':       'Saldo o deuda pendiente',
};

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

        const tdDesc = document.createElement('td');
        tdDesc.className = 'si-field-desc';
        tdDesc.style.cssText = 'font-size:0.8em;color:#888;font-style:italic;';
        tdDesc.textContent = FIELD_DESCRIPTIONS[c.campo] || '';
        sel.addEventListener('change', () => {
            tdDesc.textContent = FIELD_DESCRIPTIONS[sel.value] || '';
        });

        tr.appendChild(tdHeader);
        tr.appendChild(tdField);
        tr.appendChild(tdConf);
        tr.appendChild(tdDesc);
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
    const conflictModeEl = document.getElementById('siResolucionConflictoLinea');

    const formData = new FormData();
    formData.append('archivo', _siFileContent);
    formData.append('delimitador', delimInput?.value || ',');
    formData.append('mapeo', JSON.stringify(mapping));
    formData.append('header_fila', String(_siAnalysis?.detected_header_row ?? 0));
    formData.append('resolucion_conflicto_linea', conflictModeEl?.value || 'conservar');

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

    const { nuevos, actualizaciones, sin_cambios, filas_preview, errores_formato, diagnostico_ai } = preview;
    const total = filas_preview.length + (errores_formato?.length || 0);
    const conflictosLinea = filas_preview.filter(r => r.plan_linea?.accion === 'conflicto_linea_ocupada').length;
    const incoherencias = diagnostico_ai?.incoherencias?.length || 0;
    const alertasTest = diagnostico_ai?.alertas_test_data?.length || 0;

    let html = `<div class="stats-grid" style="margin:12px 0; grid-template-columns: repeat(auto-fit, minmax(130px,1fr));">
        <div class="stat-card"><div class="stat-number" style="color:#2ecc71">${nuevos}</div><div class="stat-label">Nuevos</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#3498db">${actualizaciones}</div><div class="stat-label">Actualizaciones</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#95a5a6">${sin_cambios}</div><div class="stat-label">Sin Cambios</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#e74c3c">${errores_formato?.length || 0}</div><div class="stat-label">Errores de Formato</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#d35400">${conflictosLinea}</div><div class="stat-label">Conflictos Línea</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#8e44ad">${incoherencias}</div><div class="stat-label">Incoherencias</div></div>
        <div class="stat-card"><div class="stat-number" style="color:#7f8c8d">${alertasTest}</div><div class="stat-label">Alertas Test</div></div>
    </div>`;

    if (diagnostico_ai) {
        const riesgos = diagnostico_ai.riesgos_priorizados || [];
        if (riesgos.length) {
            const riesgoRows = riesgos.slice(0, 8).map(r => {
                const color = r.nivel === 'alto' ? '#c0392b' : r.nivel === 'medio' ? '#d35400' : '#16a085';
                return `<div style="margin:4px 0;">
                    <span style="display:inline-block;min-width:62px;color:${color};font-weight:700;text-transform:uppercase;">${escapeHtml(r.nivel)}</span>
                    <span>Fila ${escapeHtml(String(r.fila))} · ${escapeHtml(r.categoria || 'riesgo')} · ${escapeHtml(r.detalle || '')}</span>
                </div>`;
            }).join('');
            html += `<div style="padding:10px;border:1px solid #f5cba7;background:#fff7ef;border-radius:6px;margin-bottom:10px;">
                <strong>Riesgos priorizados (alto → bajo):</strong>${riesgoRows}
            </div>`;
        }

        if (diagnostico_ai.sugerencias?.length) {
            html += `<div style="padding:10px;border:1px solid #dfe6e9;background:#f8fbff;border-radius:6px;margin-bottom:10px;">
                <strong>Sugerencias IA:</strong><br>${diagnostico_ai.sugerencias.map(escapeHtml).join('<br>')}
            </div>`;
        }
        if (diagnostico_ai.incoherencias?.length) {
            const muestraIncoherencias = diagnostico_ai.incoherencias.slice(0, 5)
                .map(x => `Fila ${x.fila}: ${x.hallazgos.map(escapeHtml).join(' | ')}`)
                .join('<br>');
            html += `<div style="padding:10px;border:1px solid #fdebd0;background:#fffaf3;border-radius:6px;margin-bottom:10px;">
                <strong>Incoherencias detectadas:</strong><br>${muestraIncoherencias}
            </div>`;
        }
    }

    if (errores_formato?.length) {
        html += `<p class="hint" style="color:#e74c3c">${errores_formato.map(escapeHtml).join('<br>')}</p>`;
    }

    // First 10 rows preview
    const rows = filas_preview.slice(0, 10);
    if (rows.length) {
        html += '<h4 style="margin-top:12px;">Vista previa (primeras 10 filas)</h4>';
        html += '<table class="data-table" style="font-size:0.8em;"><thead><tr><th>#</th><th>Acción</th><th>¿Tiene Número?</th><th>Línea</th><th>Cambios</th><th>Campos Mapeados</th></tr></thead><tbody>';
        rows.forEach(r => {
            const color = r.accion === 'nuevo' ? '#2ecc71'
                        : r.accion === 'actualizar' ? '#3498db'
                        : '#95a5a6';
            const numCell = r.tiene_numero === null ? '—'
                          : r.tiene_numero ? '<span style="color:#2ecc71">✓ Sí</span>'
                          : '<span style="color:#e74c3c">✗ No</span>';
            const linePlan = r.plan_linea?.accion || 'sin_dato';
            const lineCell = linePlan === 'sin_cambio' ? '<span style="color:#2ecc71">sin cambio</span>'
                : linePlan === 'conflicto_linea_ocupada' ? '<span style="color:#e67e22">conflicto</span>'
                : linePlan === 'crear_y_asignar' ? '<span style="color:#2980b9">crear+asignar</span>'
                : linePlan === 'reasignar_forzado' ? '<span style="color:#8e44ad">reasignar (forzado)</span>'
                : linePlan === 'liberar_conflicto' ? '<span style="color:#c0392b">liberar conflicto</span>'
                : linePlan === 'reasignar_existente' ? '<span style="color:#16a085">reasignar</span>'
                : '—';

            const cambiosCount = Object.keys(r.cambios_detectados || {}).length;
            const cambiosDetalle = Object.entries(r.cambios_detectados || {})
                .slice(0, 3)
                .map(([field, delta]) => `${escapeHtml(field)}: ${escapeHtml(delta?.actual ?? '')} → ${escapeHtml(delta?.nuevo ?? '')}`)
                .join('<br>');
            const campos = Object.entries(r.datos_mapeados)
                .slice(0, 4)
                .map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(v)}`)
                .join(', ');

            html += `<tr>
                <td>${r.fila}</td>
                <td><span style="color:${color};font-weight:bold">${escapeHtml(r.accion)}</span></td>
                <td>${numCell}</td>
                <td>${lineCell}</td>
                <td>${cambiosCount}${cambiosDetalle ? `<div style="margin-top:4px;color:#2c3e50;">${cambiosDetalle}</div>` : ''}</td>
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
    const confirmEl = document.getElementById('siConfirmExecute');
    const strictModeEl = document.getElementById('siStrictConflictMode');
    const rollbackEl = document.getElementById('siRollbackOnErrors');
    const conflictModeEl = document.getElementById('siResolucionConflictoLinea');
    if (!confirmEl?.checked) {
        statusEl.textContent = 'Debes confirmar la revisión de la vista previa para ejecutar.';
        statusEl.style.color = '#e74c3c';
        return;
    }

    statusEl.textContent = 'Importando…';
    statusEl.style.color = '#4a90d9';

    const mapping = _siGetCurrentMapping();

    const formData = new FormData();
    formData.append('archivo', _siFileContent);
    formData.append('delimitador', delimInput?.value || ',');
    formData.append('mapeo', JSON.stringify(mapping));
    formData.append('header_fila', String(_siAnalysis?.detected_header_row ?? 0));
    formData.append('modo', modeEl?.value || 'insertar');
    formData.append('confirmacion', 'true');
    formData.append('modo_estricto_conflictos', strictModeEl?.checked ? 'true' : 'false');
    formData.append('rollback_si_hay_errores', rollbackEl?.checked ? 'true' : 'false');
    formData.append('resolucion_conflicto_linea', conflictModeEl?.value || 'conservar');

    try {
        const resp = await fetch(`${API_URL}/smart-import/execute`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${authToken}` },
            body: formData,
        });
        const body = await resp.json();

        if (!resp.ok) {
            const detail = body?.detail;
            if (detail && typeof detail === 'object' && detail.mensaje) {
                const conflicts = (detail.conflictos || []).slice(0, 5)
                    .map(c => `Fila ${c.fila}: línea ${c.linea} ocupada por agente ${c.agente_ocupante_id}`)
                    .join(' | ');
                statusEl.textContent = `${detail.mensaje}${conflicts ? ` ${conflicts}` : ''}`;
            } else {
                statusEl.textContent = body.detail || 'Error al importar.';
            }
            statusEl.style.color = '#e74c3c';
            return;
        }

        const d = body.datos;
        if (d.rollback_aplicado) {
            statusEl.innerHTML = `<span style="color:#e67e22">↩ Rollback aplicado:</span>
                Se revirtieron cambios por errores detectados.
                <br>Insertados revertidos: ${d.insertados_revertidos || 0}, actualizados revertidos: ${d.actualizados_revertidos || 0}
                ${d.errores?.length ? `<br><span style="color:#e74c3c">${d.errores.length} error(es): ${d.errores.slice(0,3).join('; ')}</span>` : ''}`;
            return;
        }

        statusEl.innerHTML = `<span style="color:#2ecc71">✓ Completado:</span>
            ${d.insertados} insertado(s), ${d.actualizados} actualizado(s), ${d.omitidos} omitido(s)
            <br>${d.lineas_creadas || 0} línea(s) creada(s), ${d.lineas_reasignadas_forzadas || 0} reasignada(s), ${d.lineas_liberadas_conflicto || 0} liberada(s), ${d.conflictos_linea || 0} conflicto(s) pendiente(s)
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
            const confirmReset = document.getElementById('siConfirmExecute');
            if (confirmReset) confirmReset.checked = false;
            const strictReset = document.getElementById('siStrictConflictMode');
            if (strictReset) strictReset.checked = false;
            const rollbackReset = document.getElementById('siRollbackOnErrors');
            if (rollbackReset) rollbackReset.checked = false;
            const conflictReset = document.getElementById('siResolucionConflictoLinea');
            if (conflictReset) conflictReset.value = 'conservar';
            statusEl.textContent = '';
        }, 4000);
    } catch (err) {
        statusEl.textContent = `Error de red: ${err.message}`;
        statusEl.style.color = '#e74c3c';
    }
}
