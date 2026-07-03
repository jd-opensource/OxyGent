/**
 * annotation.js — Annotation workbench: side-panel layout, template-aware rendering, prev/next
 */
let annoPage = 1;
const ANNO_PAGE_SIZE = 50;
let currentSampleList = [];
let currentSampleIndex = -1;
let currentTemplate = null;
let currentBankSchema = null;
// Distinct sys_status values seen in this bank, populated by loadStatuses().
// Drives both the status filter dropdown and the progress-bar segments so any
// custom status the user introduces (via deposit or annotation agent) shows up
// without a code change.
let currentStatuses = [];

$(function () {
    $('#statusFilter').on('change', () => { annoPage = 1; loadAnnotationSamples(); });
    $(document).on('oxybank:bank-change', function (e, bankId) {
        if (bankId) { loadAll(); } else { clearAll(); }
    });
});

function clearAll() {
    $('#sampleListBody').empty();
    $('#progressStats').empty();
    $('#progressTrack').empty();
    currentSampleList = [];
    currentStatuses = [];
    renderStatusFilterOptions('');
    closeDetail();
}

async function loadAll() {
    // loadProgress() calls loadStatuses() internally and re-renders the filter dropdown
    // + progress bar — one entry point keeps them in sync. Sample list loads in parallel.
    loadProgress();
    loadAnnotationSamples();
    // Preload bank schema for template detection
    const bankId = OxyBank.getCurrentBankId();
    if (bankId) {
        try {
            const bank = await api.get(`/banks/${bankId}`);
            currentBankSchema = bank.schema;
        } catch (e) {}
    }
}

// ---- Statuses ----

async function loadStatuses() {
    // Refresh the list of distinct sys_status values (and their counts) that
    // actually exist for this bank + this executor. Populates currentStatuses
    // and re-renders the filter dropdown.
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const userInfo = JSON.parse(localStorage.getItem('oxybank-user') || '{}');
    const params = (userInfo.role !== 'admin' && userInfo.username)
        ? `?executor=${encodeURIComponent(userInfo.username)}`
        : '';
    try {
        const data = await api.get(`/banks/${bankId}/samples/statuses${params}`);
        // Buckets come back as [{key, doc_count}]. Skip empty-string / null keys.
        currentStatuses = (data.items || [])
            .filter(b => b.key)
            .map(b => ({ key: String(b.key), count: b.doc_count || 0 }));
        renderStatusFilterOptions($('#statusFilter').val());
    } catch (e) {
        // Non-fatal — leave the dropdown with just "全部" and let the sample list
        // still load. Progress bar will render zero segments.
        currentStatuses = [];
        renderStatusFilterOptions($('#statusFilter').val());
    }
}

function renderStatusFilterOptions(preserveValue) {
    // Rebuild the <option>s under #statusFilter. Keeps the "全部" head option
    // (which has data-i18n="annotation.all") and restores the previously-selected
    // value if it's still present. If the value has disappeared (e.g. all matching
    // samples were re-annotated), falls back to "" (all) and the caller/change
    // handler will reload the list.
    const $sel = $('#statusFilter');
    $sel.find('option:not(:first)').remove();
    currentStatuses.forEach(s => {
        $sel.append(`<option value="${esc(s.key)}">${esc(s.key)}</option>`);
    });
    if (preserveValue && $sel.find(`option[value="${preserveValue}"]`).length) {
        $sel.val(preserveValue);
    } else {
        // Only trigger a reload if the value actually changed (avoid infinite loops
        // during first-load when preserveValue is already empty).
        if (preserveValue && $sel.val() !== preserveValue) {
            $sel.val('');
            annoPage = 1;
            loadAnnotationSamples();
        } else {
            $sel.val('');
        }
    }
    // OxyBank.upgradeSelects() replaces every .form-control select with a custom
    // <div> that snapshots the options at upgrade time. On this page that upgrade
    // typically fires ~50ms after page load — BEFORE loadStatuses() finishes its
    // async fetch — so the custom widget shows only "全部" until we re-upgrade.
    // Drop the stale wrapper + cs-upgraded flag, then let common.js rebuild it.
    $sel.removeClass('cs-upgraded');
    $sel.next('.custom-select').remove();
    if (window.OxyBank && OxyBank.upgradeSelects) OxyBank.upgradeSelects();
}

// ---- Progress ----

async function loadProgress() {
    // Refresh distinct-status buckets first, then render. This makes loadProgress()
    // a single "sync the status view" entry point — callers don't need to remember
    // to call loadStatuses() separately when they know data changed.
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    await loadStatuses();
    const counts = {};
    let total = 0;
    currentStatuses.forEach(s => {
        counts[s.key] = s.count;
        total += s.count;
    });
    renderProgress(total, counts, currentStatuses.map(s => s.key));
}

// Color palette used for progress-bar segments. Recycled in order for unknown
// statuses so custom values still get a distinct color. Well-known statuses
// keep their conventional colors so existing pages don't visually shift.
// Both the canonical English tokens (Imported / Annotated / …) and their
// legacy Chinese equivalents are mapped so historical data still looks right.
const STATUS_COLOR_OVERRIDES = {
    // Canonical English tokens (see CANONICAL_STATUSES in agents.js)
    'Imported':    { bar: 'var(--primary)',   dot: 'var(--primary)' },
    'To Assign':   { bar: '#0ea5e9',          dot: '#0ea5e9' },
    'Assigned':    { bar: '#6366f1',          dot: '#6366f1' },
    'To Annotate': { bar: '#f59e0b',          dot: '#f59e0b' },
    'Annotated':   { bar: 'var(--success)',   dot: 'var(--success)' },
    'Rejected':    { bar: 'var(--danger)',    dot: 'var(--danger)' },
    'Published':   { bar: '#059669',          dot: '#059669' },
    'Ignored':     { bar: 'var(--gray-400)',  dot: 'var(--gray-400)' },
    // Legacy Chinese tokens — kept so historical samples don't visually shift
    '已入库':      { bar: 'var(--primary)',   dot: 'var(--primary)' },
    '已标注':      { bar: 'var(--success)',   dot: 'var(--success)' },
    '已驳回':      { bar: 'var(--danger)',    dot: 'var(--danger)' },
    '已上线':      { bar: '#059669',          dot: '#059669' },
    '已发布':      { bar: '#059669',          dot: '#059669' },
    '已忽略':      { bar: 'var(--gray-400)',  dot: 'var(--gray-400)' },
};
const STATUS_FALLBACK_PALETTE = [
    '#6366f1', '#f59e0b', '#0ea5e9', '#a855f7', '#14b8a6', '#ef4444', '#84cc16', '#ec4899',
];

function statusColor(key, idx) {
    if (STATUS_COLOR_OVERRIDES[key]) return STATUS_COLOR_OVERRIDES[key];
    const c = STATUS_FALLBACK_PALETTE[idx % STATUS_FALLBACK_PALETTE.length];
    return { bar: c, dot: c };
}

// Sample-row status badge class. Custom statuses fall back to badge-primary; a few
// well-known keywords are heuristically routed to success/danger so common cases
// (published / rejected / ignored / etc.) get the expected color.
function statusBadgeClass(status) {
    if (!status) return 'badge-primary';
    const s = String(status);
    if (/已标注|已发布|已上线|已完成|approved|published|annotated|done/i.test(s)) return 'badge-success';
    if (/已驳回|已拒绝|rejected|failed/i.test(s)) return 'badge-danger';
    if (/已忽略|ignored|skipped/i.test(s)) return 'badge-secondary';
    return 'badge-primary';
}

function renderProgress(total, counts, orderedKeys) {
    const $stats = $('#progressStats');
    const $track = $('#progressTrack');
    $stats.empty();
    $track.empty();
    $stats.append(`<div class="ps-item" style="font-weight:600;">${total}</div>`);
    orderedKeys.forEach((key, idx) => {
        const n = counts[key] || 0;
        if (n <= 0) return;
        const c = statusColor(key, idx);
        $stats.append(`<div class="ps-item"><div class="ps-dot" style="background:${c.dot};"></div>${esc(key)} ${n}</div>`);
        if (total > 0) $track.append(`<div class="seg" style="width:${(n/total*100).toFixed(1)}%;background:${c.bar};"></div>`);
    });
}

// ---- Sample List ----

async function loadAnnotationSamples() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const status = $('#statusFilter').val();
    let params = `?page=${annoPage}&size=${ANNO_PAGE_SIZE}`;
    if (status) params += `&status=${encodeURIComponent(status)}`;
    // Annotators only see samples assigned to them
    const userInfo = JSON.parse(localStorage.getItem('oxybank-user') || '{}');
    if (userInfo.role !== 'admin' && userInfo.username) {
        params += `&executor=${encodeURIComponent(userInfo.username)}`;
    }
    try {
        const data = await api.get(`/banks/${bankId}/samples${params}`);
        const items = data.items || [];
        items.sort((a, b) => (a.sys_priority || 0) - (b.sys_priority || 0));
        currentSampleList = items;
        renderSampleList(data);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderSampleList(data) {
    const items = data.items || [];
    const total = data.total || 0;
    const totalPages = Math.ceil(total / ANNO_PAGE_SIZE);
    const $body = $('#sampleListBody');
    $body.empty();
    if (!items.length) {
        $body.html(`<div style="text-align:center;padding:40px;color:var(--gray-400);">${i18n.t('common.empty')}</div>`);
        return;
    }
    items.forEach((s, idx) => {
        const sid = s.sys_sample_id || s.id;
        const statusCls = statusBadgeClass(s.sys_status);
        const overview = s.sys_overview || s.query || s.title || sid.substring(0, 12) + '…';
        const remarks = s.sys_remarks || '';
        const active = idx === currentSampleIndex ? ' active' : '';
        $body.append(`
            <div class="sample-row${active}" data-idx="${idx}" onclick="selectSample(${idx})">
                <div class="sr-priority"><span class="badge ${(s.sys_priority || 0) > 0 ? 'badge-warning' : ''}" style="font-size:11px;">${s.sys_priority || 0}</span></div>
                <div class="sr-status"><span class="badge ${statusCls}" style="font-size:11px;">${esc(s.sys_status || '-')}</span></div>
                <div class="sr-overview">${esc(String(overview).substring(0, 60))}</div>
                ${remarks ? `<div class="sr-remarks" title="${esc(remarks)}">💬 ${esc(remarks.substring(0, 20))}${remarks.length > 20 ? '…' : ''}</div>` : ''}
            </div>`);
    });
    OxyBank.renderPagination('#annotationPagination', annoPage, totalPages, (p) => {
        annoPage = p;
        loadAnnotationSamples();
    });
}

// ---- Detail Panel ----

async function selectSample(index) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    currentSampleIndex = index;
    const s = currentSampleList[index];
    if (!s) return;
    const sampleId = s.sys_sample_id || s.id;

    // Highlight row
    $('.sample-row').removeClass('active');
    $(`.sample-row[data-idx="${index}"]`).addClass('active');

    try {
        const sample = await api.get(`/banks/${bankId}/samples/${sampleId}`);
        currentTemplate = null;
        if (sample.sys_template) {
            try { currentTemplate = await api.get(`/banks/${bankId}/templates/${sample.sys_template}`); } catch (e) {}
        }
        renderDetail(sample);
        openDetail();
        updateNavButtons();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function openDetail() {
    $('#detailPanel').removeClass('collapsed');
}

function closeDetail() {
    $('#detailPanel').addClass('collapsed');
    currentSampleIndex = -1;
    $('.sample-row').removeClass('active');
}

function updateNavButtons() {
    $('#btnPrevSample').prop('disabled', currentSampleIndex <= 0);
    $('#btnNextSample').prop('disabled', currentSampleIndex >= currentSampleList.length - 1);
    $('#sampleCounter').text(`${currentSampleIndex + 1} / ${currentSampleList.length}`);
}

async function navSample(delta) {
    const newIdx = currentSampleIndex + delta;
    if (newIdx < 0 || newIdx >= currentSampleList.length) return;
    await selectSample(newIdx);
}

// ---- Render Detail (template-aware) ----

function renderDetail(sample) {
    const sid = sample.sys_sample_id || sample.id;
    const tpl = currentTemplate;
    const layout = tpl?.layout;
    const constraints = tpl?.field_constraints || {};
    const editableSet = tpl ? new Set(tpl.editable_fields || []) : null;

    let html = `<form id="annoEditForm"><input type="hidden" name="_sample_id" value="${sid}">`;

    if (layout && layout.sections) {
        // Template with sections layout (e.g. QA)
        layout.sections.forEach(sec => {
            html += `<div class="qa-section"><div class="qa-section-title">${esc(sec.title)}</div>`;
            (sec.fields || []).forEach(f => {
                const val = sample[f];
                const valStr = (val === null || val === undefined) ? '' : String(val);
                const constraint = constraints[f] || {};

                if (sec.readonly) {
                    html += `<div class="qa-readonly">${esc(valStr) || '<span style="color:var(--gray-300);">-</span>'}</div>`;
                    html += `<input type="hidden" name="${esc(f)}" value="${esc(valStr)}">`;
                } else {
                    html += renderConstrainedField(f, valStr, constraint);
                }
            });
            html += '</div>';
        });
    } else {
        // Default template: all fields as text inputs
        Object.entries(sample).forEach(([k, v]) => {
            if (k === 'id') return;
            let valStr = (v === null || v === undefined) ? '' : String(v);
            // Timestamp-typed sys_* fields come as ISO strings — render them with
            // the app-wide YYYY-MM-DD HH:mm:ss formatter so they're readable.
            if (valStr && (k === 'sys_create_time' || k === 'sys_update_time')) {
                valStr = OxyBank.formatDate(valStr);
            }
            let editable;
            if (editableSet) {
                editable = editableSet.has(k);
            } else {
                editable = !['sys_sample_id', 'sys_document_id', 'sys_create_time'].includes(k);
            }
            if (editable) {
                const isLong = valStr.length > 80;
                if (isLong) {
                    html += `<div class="form-group"><label>${esc(k)}</label>
                        <textarea class="form-control" name="${esc(k)}" rows="3">${esc(valStr)}</textarea></div>`;
                } else {
                    html += `<div class="form-group"><label>${esc(k)}</label>
                        <input type="text" class="form-control" name="${esc(k)}" value="${esc(valStr)}"></div>`;
                }
            } else {
                html += `<div class="form-group"><label>${esc(k)}</label>
                    <input type="text" class="form-control" name="${esc(k)}" value="${esc(valStr)}" readonly style="background:var(--gray-50);"></div>`;
            }
        });
    }

    html += '</form>';

    // Reject section
    html += `<div id="annoRejectSection" style="display:none;margin-top:12px;border-top:1px solid var(--gray-200);padding-top:12px;">
        <div class="form-group">
            <label>${i18n.t('detail.reject_reason')}</label>
            <textarea class="form-control" id="annoRejectRemarks" rows="2" placeholder="${i18n.t('detail.reject_reason_hint')}"></textarea>
        </div>
        <button class="btn btn-danger btn-sm" onclick="annoConfirmReject()">${i18n.t('detail.confirm_reject')}</button>
        <button class="btn btn-secondary btn-sm" onclick="$('#annoRejectSection').hide()" style="margin-left:4px;">${i18n.t('common.cancel')}</button>
    </div>`;

    $('#annoDetailBody').html(html);

    // Wire up conditional visibility (show_when)
    Object.entries(constraints).forEach(([field, c]) => {
        if (c.show_when) {
            Object.entries(c.show_when).forEach(([depField, depVal]) => {
                const $dep = $(`[name="${depField}"]`);
                const $target = $(`[name="${field}"]`).closest('.form-group');
                function toggle() {
                    const cur = $dep.filter(':checked').val() || $dep.val();
                    const match = Array.isArray(depVal) ? depVal.includes(cur) : cur === depVal;
                    $target.toggle(match);
                }
                $dep.on('change', toggle);
                toggle();
            });
        }
    });
}

function renderConstrainedField(field, value, constraint) {
    const type = constraint.type || 'text';
    let html = `<div class="form-group"><label>${esc(field)}</label>`;

    if (type === 'radio') {
        html += '<div class="qa-radio-group">';
        (constraint.options || []).forEach(opt => {
            const checked = value === opt ? 'checked' : '';
            html += `<label><input type="radio" name="${esc(field)}" value="${esc(opt)}" ${checked}><span>${esc(opt)}</span></label>`;
        });
        html += '</div>';
    } else if (type === 'select') {
        html += `<select class="form-control" name="${esc(field)}">`;
        (constraint.options || []).forEach(opt => {
            html += `<option value="${esc(opt)}" ${value === opt ? 'selected' : ''}>${esc(opt)}</option>`;
        });
        html += '</select>';
    } else if (type === 'textarea') {
        html += `<textarea class="form-control" name="${esc(field)}" rows="3" placeholder="${esc(constraint.placeholder || '')}">${esc(value)}</textarea>`;
    } else {
        html += `<input type="text" class="form-control" name="${esc(field)}" value="${esc(value)}">`;
    }

    html += '</div>';
    return html;
}

// ---- Save / Reject ----

async function annoSaveSample() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const sampleId = $('#annoEditForm [name="_sample_id"]').val();
    const fields = {};
    $('#annoEditForm').find('input:not([readonly]):not([type=hidden]), textarea, select').each(function () {
        if (this.type === 'radio' && !this.checked) return;
        fields[this.name] = $(this).val();
    });
    try {
        const result = await api.put(`/banks/${bankId}/samples/${sampleId}`, { fields });
        const newStatus = result?.sys_status;
        if (newStatus) {
            OxyBank.showToast(`${i18n.t('annotation.submitted')} → ${newStatus}`, 'success');
        } else {
            OxyBank.showToast(i18n.t('annotation.submitted'), 'success');
        }
        if (currentSampleList[currentSampleIndex]) {
            Object.assign(currentSampleList[currentSampleIndex], fields);
            if (newStatus) currentSampleList[currentSampleIndex].sys_status = newStatus;
        }
        if (currentSampleIndex < currentSampleList.length - 1) {
            await navSample(1);
        } else {
            loadAnnotationSamples();
            loadProgress();
        }
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function annoRejectSample() {
    $('#annoRejectSection').show();
    $('#annoRejectRemarks').val('').focus();
}

async function annoConfirmReject() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const sampleId = $('#annoEditForm [name="_sample_id"]').val();
    const remarks = $('#annoRejectRemarks').val().trim();
    if (!remarks) { OxyBank.showToast(i18n.t('detail.reject_reason_required'), 'error'); return; }
    try {
        const result = await api.put(`/banks/${bankId}/samples/${sampleId}/reject`, {
            fields: {},
            remarks: remarks,
        });
        const newStatus = result?.sys_status || i18n.t('detail.rejected');
        OxyBank.showToast(`${i18n.t('detail.rejected')} → ${newStatus}`, 'success');
        if (currentSampleIndex < currentSampleList.length - 1) {
            await navSample(1);
        } else {
            loadAnnotationSamples();
            loadProgress();
        }
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

// ---- History ----

async function showAnnoHistory() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const sampleId = $('#annoEditForm [name="_sample_id"]').val();
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
        $('#annoDetailBody').html(html);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
