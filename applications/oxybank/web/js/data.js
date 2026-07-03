/**
 * data.js — Data Management page logic
 */
let samplePage = 1;
const SAMPLE_PAGE_SIZE = 20;
let bankTemplatesCache = []; // {id, name, is_builtin} — used by the sys_template dropdown

$(function () {
    initFileUpload();
    $(document).on('oxybank:bank-change', function (e, bankId) {
        // Always close the sample panel on bank change — it shows samples belonging
        // to a specific document in the *previous* bank, which are irrelevant (and
        // misleading) once the user has switched to a different bank.
        closeSamples();
        if (bankId) {
            loadDocuments();
            loadBankTemplates();
        } else {
            $('#docTable tbody').empty();
            bankTemplatesCache = [];
        }
    });
});

async function loadBankTemplates() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) { bankTemplatesCache = []; return; }
    try {
        const data = await api.get(`/banks/${bankId}/templates`);
        bankTemplatesCache = (data.items || data || []).map(t => ({
            id: t.id, name: t.name, is_builtin: t.is_builtin || false,
        }));
    } catch (e) {
        bankTemplatesCache = [];
    }
}

// ---- Documents ----

async function loadDocuments() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        const data = await api.get(`/banks/${bankId}/documents`);
        const docs = data.items || data;
        renderDocTable(docs);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderDocTable(docs) {
    const $tbody = $('#docTable tbody');
    $tbody.empty();
    if (!docs.length) {
        $tbody.append(`<tr><td colspan="5" style="text-align:center;color:var(--gray-400);">${i18n.t('common.empty')}</td></tr>`);
        return;
    }

    // Group by filename
    const groups = {};
    docs.forEach(d => {
        const key = d.filename || d.id;
        if (!groups[key]) {
            groups[key] = { filename: key, file_type: d.file_type, sample_count: 0, upload_time: d.upload_time, doc_ids: [] };
        }
        groups[key].sample_count += (d.sample_count || 0);
        groups[key].doc_ids.push(d.id);
        if (d.upload_time > groups[key].upload_time) groups[key].upload_time = d.upload_time;
    });

    Object.values(groups).forEach(g => {
        const docIdsAttr = escHtml(JSON.stringify(g.doc_ids));
        $tbody.append(`
            <tr style="cursor:pointer;" onclick='loadSamplesByGroup(${docIdsAttr})'>
                <td>${escHtml(g.filename)}</td>
                <td><span class="badge badge-primary">${g.file_type || '-'}</span>${g.doc_ids.length > 1 ? ` <span style="font-size:11px;color:var(--gray-400);">(${g.doc_ids.length})</span>` : ''}</td>
                <td>${g.sample_count}</td>
                <td>${OxyBank.formatDate(g.upload_time)}</td>
                <td onclick="event.stopPropagation()"><button class="btn btn-sm btn-danger" onclick='deleteDocGroup(${docIdsAttr})'>${i18n.t('common.delete')}</button></td>
            </tr>`);
    });
}

async function deleteDoc(docId) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        await api.del(`/banks/${bankId}/documents/${docId}`);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function deleteDocGroup(docIds) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    if (!confirm('Delete this document group?')) return;
    try {
        for (const id of docIds) {
            await deleteDoc(id);
        }
        OxyBank.showToast('Deleted', 'success');
        loadDocuments();
        closeSamples();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

// ---- File Upload ----

function initFileUpload() {
    $('#fileUpload').on('change', async function () {
        const bankId = OxyBank.getCurrentBankId();
        if (!bankId) { this.value = ''; return; }
        const files = this.files;
        if (!files.length) return;

        const total = files.length;
        for (let i = 0; i < total; i++) {
            const file = files[i];
            const label = total > 1 ? `(${i + 1}/${total}) ${file.name}` : file.name;
            try {
                await uploadFileWithProgress(bankId, file, label);
            } catch (e) {
                OxyBank.showToast(`${file.name}: ${e.message}`, 'error');
            }
        }
        hideUploadProgress();
        OxyBank.showToast('Upload complete', 'success');
        loadDocuments();
        this.value = '';
    });
}

function uploadFileWithProgress(bankId, file, label) {
    return new Promise((resolve, reject) => {
        const form = new FormData();
        form.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/banks/${bankId}/documents/upload`);

        const token = localStorage.getItem('oxybank-token');
        if (token) xhr.setRequestHeader('Authorization', 'Bearer ' + token);

        // Show progress bar
        showUploadProgress(label);

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                // Upload phase: 0-50%
                const pct = Math.round((e.loaded / e.total) * 50);
                updateUploadProgress(pct, i18n.t('data.uploading'));
            }
        });

        xhr.addEventListener('loadend', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                updateUploadProgress(100, i18n.t('data.upload_done'));
                resolve(JSON.parse(xhr.responseText));
            } else {
                let detail = 'Upload failed';
                try { detail = JSON.parse(xhr.responseText).detail || detail; } catch (e) {}
                reject(new Error(detail));
            }
        });

        // After upload finishes, server processes (chunking + embedding) — show indeterminate
        xhr.upload.addEventListener('load', () => {
            updateUploadProgress(50, i18n.t('data.processing'));
            startProcessingAnimation();
        });

        xhr.addEventListener('error', () => reject(new Error('Network error')));
        xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));

        xhr.send(form);
    });
}

let processingTimer = null;

function showUploadProgress(fileName) {
    $('#uploadFileName').text(fileName);
    $('#uploadPercent').text('0%');
    $('#uploadBar').css('width', '0%');
    $('#uploadStatus').text('');
    $('#uploadProgress').show();
}

function updateUploadProgress(pct, status) {
    $('#uploadPercent').text(pct + '%');
    $('#uploadBar').css('width', pct + '%');
    if (status) $('#uploadStatus').text(status);
}

function startProcessingAnimation() {
    let pct = 50;
    clearInterval(processingTimer);
    processingTimer = setInterval(() => {
        // Slowly animate from 50% to 95% to indicate server processing
        pct += (95 - pct) * 0.05;
        updateUploadProgress(Math.round(pct), i18n.t('data.processing'));
    }, 500);
}

function hideUploadProgress() {
    clearInterval(processingTimer);
    processingTimer = null;
    updateUploadProgress(100, '');
    setTimeout(() => { $('#uploadProgress').hide(); }, 1000);
}

// ---- Samples ----

let currentDocIds = [];

async function loadSamples(docId) {
    currentDocIds = [docId];
    samplePage = 1;
    await fetchSamples();
    $('#samplesSection').show();
}

async function loadSamplesByGroup(docIds) {
    currentDocIds = docIds;
    samplePage = 1;
    await fetchSamples();
    $('#samplesSection').show();
}

function closeSamples() {
    $('#samplesSection').hide();
    currentDocIds = [];
}

async function fetchSamples() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        let params = `?page=${samplePage}&size=${SAMPLE_PAGE_SIZE}`;
        if (currentDocIds.length === 1) {
            params += `&document_id=${currentDocIds[0]}`;
        }
        const data = await api.get(`/banks/${bankId}/samples${params}`);
        // Client-side filter if multiple doc IDs
        if (currentDocIds.length > 1) {
            const idSet = new Set(currentDocIds);
            data.items = (data.items || []).filter(s => idSet.has(s.sys_document_id));
        }
        renderSamples(data);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderSamples(data) {
    const items = data.items || [];
    const total = data.total || 0;
    const totalPages = Math.ceil(total / SAMPLE_PAGE_SIZE);

    const $head = $('#sampleHead');
    const $tbody = $('#sampleTable tbody');
    $head.empty();
    $tbody.empty();

    if (!items.length) {
        $tbody.append(`<tr><td colspan="5" style="text-align:center;">${i18n.t('common.empty')}</td></tr>`);
        return;
    }

    // Show all fields from the first item
    const allKeys = Object.keys(items[0]).filter(k => k !== 'id');
    allKeys.forEach(f => $head.append(`<th style="white-space:nowrap;">${f}</th>`));
    $head.append(`<th class="sticky-col" style="white-space:nowrap;">${i18n.t('common.actions')}</th>`);

    items.forEach(s => {
        const sid = s.sys_sample_id || s.id;
        let row = `<tr style="cursor:pointer;" onclick="viewSample('${sid}')">`;
        allKeys.forEach(f => {
            const val = s[f];
            const valStr = (val === null || val === undefined) ? '-' : String(val);
            const display = valStr.length > 80 ? valStr.substring(0, 80) + '…' : valStr;
            row += `<td style="white-space:nowrap;max-width:300px;overflow:hidden;text-overflow:ellipsis;" title="${escHtml(valStr)}">${escHtml(display)}</td>`;
        });
        row += `<td class="sticky-col" style="white-space:nowrap;" onclick="event.stopPropagation()">
            <button class="btn btn-sm btn-danger" onclick="deleteSample('${sid}')">${i18n.t('common.delete')}</button>
        </td>`;
        row += '</tr>';
        $tbody.append(row);
    });

    OxyBank.renderPagination('#samplePagination', samplePage, totalPages, (p) => {
        samplePage = p;
        fetchSamples();
    });
}

async function deleteSample(sampleId) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    if (!confirm(i18n.t('data.confirm_delete_sample'))) return;
    try {
        await api.del(`/banks/${bankId}/samples/${sampleId}`);
        OxyBank.showToast('Deleted', 'success');
        fetchSamples();
        loadDocuments();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function viewSample(sampleId) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        const sample = await api.get(`/banks/${bankId}/samples/${sampleId}`);
        const tplId = sample.sys_template;
        let template = null;
        if (tplId) {
            try { template = await api.get(`/banks/${bankId}/templates/${tplId}`); } catch (e) {}
        }
        renderSampleDetail(sample, template);
        OxyBank.openModal('#sampleModal');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderSampleDetail(sample, template) {
    const sid = sample.sys_sample_id || sample.id;
    const editableSet = template ? new Set(template.editable_fields || []) : null;

    let html = '<form id="sampleEditForm">';
    html += `<input type="hidden" name="_sample_id" value="${sid}">`;

    Object.entries(sample).forEach(([k, v]) => {
        if (k === 'id') return;
        let valStr = (v === null || v === undefined) ? '' : String(v);
        // Timestamp-typed sys_* fields come as ISO strings — render them with the
        // app-wide YYYY-MM-DD HH:mm:ss formatter so they're readable in the form.
        if (valStr && (k === 'sys_create_time' || k === 'sys_update_time')) {
            valStr = OxyBank.formatDate(valStr);
        }
        let editable;
        if (template) {
            editable = editableSet.has(k);
        } else {
            editable = !['sys_sample_id', 'sys_document_id', 'sys_create_time'].includes(k);
        }

        // sys_template gets a special editor: a dropdown of template names for this bank.
        // Value stored on the sample is the template *name*, matched at read time by
        // get_template's name-fallback. Falls back to a plain input if templates
        // haven't loaded yet.
        if (k === 'sys_template' && bankTemplatesCache.length) {
            const currentMatch = bankTemplatesCache.find(t => t.id === valStr || t.name === valStr);
            const displayValue = currentMatch ? currentMatch.name : valStr;
            html += `<div class="form-group">
                <label>${escHtml(k)}</label>
                <select class="form-control" name="${escHtml(k)}">
                    <option value=""${!displayValue ? ' selected' : ''}>—</option>
                    ${bankTemplatesCache.map(t => {
                        const sel = t.name === displayValue ? ' selected' : '';
                        const suffix = t.is_builtin ? ' (' + i18n.t('templates.builtin') + ')' : '';
                        return `<option value="${escHtml(t.name)}"${sel}>${escHtml(t.name)}${suffix}</option>`;
                    }).join('')}
                </select>
            </div>`;
            return;
        }

        const isLong = valStr.length > 80;
        if (editable) {
            if (isLong) {
                html += `<div class="form-group">
                    <label>${escHtml(k)}</label>
                    <textarea class="form-control" name="${escHtml(k)}" rows="3">${escHtml(valStr)}</textarea>
                </div>`;
            } else {
                html += `<div class="form-group">
                    <label>${escHtml(k)}</label>
                    <input type="text" class="form-control" name="${escHtml(k)}" value="${escHtml(valStr)}">
                </div>`;
            }
        } else {
            html += `<div class="form-group">
                <label>${escHtml(k)}</label>
                <input type="text" class="form-control" name="${escHtml(k)}" value="${escHtml(valStr)}" readonly style="background:var(--gray-50);">
            </div>`;
        }
    });
    html += '</form>';

    // Reject section (hidden by default)
    html += `<div id="rejectSection" style="display:none;margin-top:12px;border-top:1px solid var(--gray-200);padding-top:12px;">
        <div class="form-group">
            <label data-i18n="detail.reject_reason">${i18n.t('detail.reject_reason')}</label>
            <textarea class="form-control" id="rejectRemarks" rows="2" placeholder="${i18n.t('detail.reject_reason_hint')}"></textarea>
        </div>
        <button class="btn btn-danger" onclick="confirmReject()">${i18n.t('detail.confirm_reject')}</button>
        <button class="btn btn-secondary" onclick="$('#rejectSection').hide()" style="margin-left:6px;">${i18n.t('common.cancel')}</button>
    </div>`;

    $('#sampleDetail').html(html);
}

async function saveSample() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const sampleId = $('#sampleEditForm [name="_sample_id"]').val();
    const fields = {};
    $('#sampleEditForm').find('input:not([readonly]):not([type=hidden]), textarea, select').each(function () {
        fields[this.name] = $(this).val();
    });
    try {
        await api.put(`/banks/${bankId}/samples/${sampleId}`, { fields });
        OxyBank.showToast(i18n.t('common.save') + ' OK', 'success');
        OxyBank.closeModal('#sampleModal');
        fetchSamples();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function rejectSample() {
    $('#rejectSection').show();
    $('#rejectRemarks').val('').focus();
}

async function confirmReject() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const sampleId = $('#sampleEditForm [name="_sample_id"]').val();
    const remarks = $('#rejectRemarks').val().trim();
    if (!remarks) { OxyBank.showToast(i18n.t('detail.reject_reason_required'), 'error'); return; }
    try {
        await api.put(`/banks/${bankId}/samples/${sampleId}`, {
            fields: { sys_status: 'Rejected', sys_remarks: remarks },
            remarks: remarks,
        });
        OxyBank.showToast(i18n.t('detail.rejected'), 'success');
        OxyBank.closeModal('#sampleModal');
        fetchSamples();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function showSampleHistory() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const sampleId = $('#sampleEditForm [name="_sample_id"]').val();
    if (!sampleId) return;
    try {
        const history = await api.get(`/banks/${bankId}/samples/${sampleId}/history`);
        const items = history.items || history;
        let html = '<h3 style="margin-bottom:12px;">' + i18n.t('detail.history') + '</h3>';
        if (!items.length) { html += '<p>' + i18n.t('common.empty') + '</p>'; }
        items.forEach(h => {
            html += `<div style="border:1px solid var(--gray-200);border-radius:6px;padding:10px;margin-bottom:8px;">
                <div style="font-size:12px;color:var(--gray-400);">v${h.version} | ${h.changed_by || '-'} | ${h.change_source || '-'} | ${OxyBank.formatDate(h.timestamp)}</div>
                <pre style="font-size:12px;margin-top:4px;white-space:pre-wrap;">${JSON.stringify(h.changed_fields, null, 2)}</pre>
            </div>`;
        });
        $('#sampleDetail').html(html);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ---- Deposit (API存储) ----

function openDepositModal() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    $('#depositName').val('');
    $('#depositData').val('');
    OxyBank.openModal('#depositModal');
}

async function submitDeposit() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const raw = $('#depositData').val().trim();
    if (!raw) { OxyBank.showToast('Data is empty', 'error'); return; }
    let samples;
    try {
        samples = JSON.parse(raw);
    } catch (e) {
        OxyBank.showToast('Invalid JSON', 'error');
        return;
    }
    if (!Array.isArray(samples)) {
        samples = [samples];
    }
    if (!samples.length) { OxyBank.showToast('No samples', 'error'); return; }

    try {
        OxyBank.showLoading();
        const result = await api.post(`/banks/${bankId}/deposit_batch`, {
            samples: samples,
            document_name: $('#depositName').val().trim(),
        });
        OxyBank.closeModal('#depositModal');
        OxyBank.showToast(`${i18n.t('data.deposited')}: ${result.sample_count}`, 'success');
        loadDocuments();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    } finally {
        OxyBank.hideLoading();
    }
}
