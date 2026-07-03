/**
 * banks.js — Bank management page logic (3-step wizard)
 */
let sceneTemplates = [];
let wizardStep = 1;

$(function () {
    loadBanks();
    loadSceneTemplates();
    initSchemaModeSwitcher();
});

$(document).on('oxybank:lang-change', function () {
    loadBanks();
});

// ---- Load & Render ----

async function loadBanks() {
    try {
        const data = await api.get('/banks');
        const banks = data.items || data;
        renderBanks(banks);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderBanks(banks) {
    const $grid = $('#bankGrid');
    const $empty = $('#emptyState');
    $grid.empty();
    if (!banks || banks.length === 0) {
        $empty.show();
        return;
    }
    $empty.hide();
    banks.forEach(b => {
        const card = `
            <div class="card" onclick="goToBank('${escHtml(b.name)}')">
                <div class="card-title">${escHtml(b.name)}</div>
                <div style="font-size:11px;color:var(--gray-400);font-family:monospace;margin-bottom:6px;user-select:all;">${b.id}</div>
                <div class="card-desc">${escHtml(b.description || '-')}</div>
                <div class="card-meta">
                    <span>${i18n.t('banks.schema_mode.' + (b.schema_mode || 'personalized'))}</span>
                    <span>${b.has_sys_chunk ? '📄 Chunk' : ''}</span>
                    <span>${OxyBank.formatDate(b.created_at)}</span>
                </div>
                <div class="card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-sm btn-danger" onclick="deleteBank('${escHtml(b.name)}')" data-i18n="common.delete">${i18n.t('common.delete')}</button>
                </div>
            </div>`;
        $grid.append(card);
    });
}

function goToBank(name) {
    localStorage.setItem("oxybank-current-bank", name);
    window.location.href = 'data.html';
}

async function deleteBank(name) {
    if (!confirm(i18n.t('banks.confirm_delete'))) return;
    try {
        await api.del(`/banks/${encodeURIComponent(name)}`);
        OxyBank.showToast('Deleted', 'success');
        if (localStorage.getItem("oxybank-current-bank") === name) {
            localStorage.removeItem("oxybank-current-bank");
        }
        loadBanks();
        $('#globalBankSelect').find('option:not(:first)').remove();
        OxyBank.loadBankSelector();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

// ===========================================================================
// Wizard: 3-step create flow
// ===========================================================================

function openCreateModal() {
    resetCreateForm();
    wizardStep = 1;
    updateWizardUI();
    OxyBank.openModal('#createModal');
    setTimeout(() => OxyBank.upgradeSelects(), 50);
}

function resetCreateForm() {
    $('#bankName').val('');
    $('#bankDesc').val('');
    $('#sysChunkCheck').prop('checked', false);
    $('#schemaFields').empty();
    $('#retrievalApis').empty();
    $('#embeddingBackend').val('triton');
    addSchemaField();
}

function updateWizardUI() {
    // Panels
    $('.wizard-panel').hide();
    $(`#step${wizardStep}`).show();
    // Step indicators
    $('.wizard-step').each(function () {
        const s = parseInt($(this).data('step'));
        $(this).removeClass('active done');
        if (s < wizardStep) $(this).addClass('done');
        else if (s === wizardStep) $(this).addClass('active');
    });
    // Buttons
    $('#btnWizardPrev').toggle(wizardStep > 1);
    $('#btnWizardNext').toggle(wizardStep < 3);
    $('#btnWizardSubmit').toggle(wizardStep === 3);
}

function wizardNext() {
    if (wizardStep === 1) {
        const name = $('#bankName').val().trim();
        if (!name) { OxyBank.showToast(i18n.t('banks.name') + ' required', 'error'); return; }
    }
    if (wizardStep === 2) {
        // Entering step 3: rebuild retrieval API dropdowns with finalized schema
        $('#retrievalApis').empty();
    }
    wizardStep++;
    updateWizardUI();
    i18n.apply();
}

function wizardPrev() {
    if (wizardStep > 1) wizardStep--;
    updateWizardUI();
    i18n.apply();
}

// ---- Schema Mode Switcher ----

function initSchemaModeSwitcher() {
    $('#schemaModeSwitch').on('click', 'button', function () {
        $('#schemaModeSwitch button').removeClass('active');
        $(this).addClass('active');
        const mode = $(this).data('mode');
        if (mode === 'personalized') {
            $('#personalizedSchema').show();
            $('#sceneSchema').hide();
        } else {
            $('#personalizedSchema').hide();
            $('#sceneSchema').show();
        }
    });
}

// ---- Schema Fields ----

function addSchemaField(name, type, desc) {
    const types = ['string', 'text', 'integer', 'float', 'boolean', 'date', 'keyword'];
    const typeOptions = types.map(t => `<option value="${t}" ${t === (type || 'string') ? 'selected' : ''}>${t}</option>`).join('');
    const html = `
        <div class="schema-field-row">
            <input type="text" class="form-control" placeholder="${i18n.t('banks.field_name')}" value="${escHtml(name || '')}">
            <select class="form-control" style="max-width:120px;">${typeOptions}</select>
            <input type="text" class="form-control" placeholder="${i18n.t('banks.field_desc')}" value="${escHtml(desc || '')}">
            <button class="btn btn-icon btn-secondary" onclick="$(this).parent().remove()" title="Remove">&times;</button>
        </div>`;
    $('#schemaFields').append(html);
    OxyBank.upgradeSelects();
}

async function parseSchemaFile(input) {
    const file = input.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
        const fields = await api.upload('/banks/parse-schema-file', formData);
        $('#schemaFields').empty();
        (fields || []).forEach(f => addSchemaField(f.name, f.type, f.description));
        OxyBank.showToast('Schema parsed', 'success');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
    input.value = '';
}

// ---- Scene Templates ----

async function loadSceneTemplates() {
    try {
        sceneTemplates = await api.get('/banks/scene-templates');
        const $sel = $('#sceneSelect');
        $sel.empty();
        (sceneTemplates || []).forEach(t => {
            $sel.append(`<option value="${t.id}">${i18n.t('scene.' + t.id) || t.name}</option>`);
        });
        $sel.on('change', previewScene);
        previewScene();
        // Re-upgrade since options were rebuilt
        $sel.removeClass('cs-upgraded');
        $sel.next('.custom-select').remove();
        OxyBank.upgradeSelects();
    } catch (e) {}
}

function previewScene() {
    const id = $('#sceneSelect').val();
    const tpl = sceneTemplates.find(t => t.id === id);
    if (!tpl) { $('#scenePreview').empty(); return; }
    let html = '<table><tr><th>' + i18n.t('banks.field_name') + '</th><th>' + i18n.t('banks.field_type') + '</th><th>' + i18n.t('banks.field_desc') + '</th></tr>';
    (tpl.fields || []).forEach(f => {
        html += `<tr><td>${escHtml(f.name)}</td><td>${f.type}</td><td>${escHtml(f.description || '')}</td></tr>`;
    });
    html += '</table>';
    $('#scenePreview').html(html);
}

// ---- Retrieval API (Step 3) ----

function getAllSchemaFieldNames() {
    const fields = [];
    const sysFields = ['sys_sample_id', 'sys_document_id', 'sys_template', 'sys_priority',
        'sys_status', 'sys_executor', 'sys_overview', 'sys_remarks', 'sys_create_time', 'sys_update_time'];
    sysFields.forEach(f => fields.push(f));
    if ($('#sysChunkCheck').is(':checked')) fields.push('sys_chunk');
    const mode = $('#schemaModeSwitch button.active').data('mode');
    if (mode === 'personalized') {
        $('#schemaFields .schema-field-row').each(function () {
            const fname = $(this).find('input').first().val().trim();
            if (fname) fields.push(fname);
        });
    } else {
        const tplId = $('#sceneSelect').val();
        const tpl = sceneTemplates.find(t => t.id === tplId);
        if (tpl) (tpl.fields || []).forEach(f => fields.push(f.name));
    }
    return fields;
}

function buildFieldOptions(selected) {
    const fields = getAllSchemaFieldNames();
    return fields.map(f => `<option value="${f}" ${f === selected ? 'selected' : ''}>${f}</option>`).join('');
}

function addRetrievalApi() {
    const fields = getAllSchemaFieldNames();
    const outputChips = fields.map(f =>
        `<label class="output-chip">
            <input type="checkbox" class="output-check" value="${f}">
            <span>${f}</span>
        </label>`
    ).join('');
    const html = `
        <div class="retrieval-api-block" style="border:1px solid var(--gray-200);border-radius:8px;padding:12px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <input type="text" class="form-control api-name" placeholder="${i18n.t('banks.api_name')}" style="max-width:200px;">
                <button class="btn btn-icon btn-secondary" onclick="$(this).closest('.retrieval-api-block').remove()">&times;</button>
            </div>
            <div class="api-conditions"></div>
            <button class="btn btn-sm btn-secondary" onclick="addCondition(this)" style="margin-bottom:8px;">${i18n.t('banks.add_condition')}</button>
            <div class="form-group">
                <label style="font-size:12px;">${i18n.t('banks.output_fields')}</label>
                <div class="api-output-checks" style="display:flex;flex-wrap:wrap;gap:4px;">${outputChips}</div>
            </div>
        </div>`;
    $('#retrievalApis').append(html);
}

function _isVectorAllowed(fieldName) {
    // Only sys_chunk and non-sys_ (custom) fields can do vector search.
    if (!fieldName) return true;
    if (fieldName === 'sys_chunk') return true;
    return !fieldName.startsWith('sys_');
}

function _refreshCondModeOptions($modeSelect, fieldName, keepValue) {
    const currentVal = keepValue != null ? keepValue : $modeSelect.val();
    const allowVector = _isVectorAllowed(fieldName);
    const modes = allowVector ? ['vector', 'exact', 'in', 'fuzzy'] : ['exact', 'in', 'fuzzy'];
    const opts = modes.map(m => `<option value="${m}">${i18n.t('mode.' + m)}</option>`).join('');
    $modeSelect.html(opts);
    // If current value is vector but now not allowed, reset to exact
    let nextVal = currentVal;
    if (!allowVector && currentVal === 'vector') nextVal = 'exact';
    $modeSelect.val(nextVal);
    // Re-upgrade the custom select
    $modeSelect.removeClass('cs-upgraded');
    $modeSelect.next('.custom-select').remove();
    if (window.OxyBank && OxyBank.upgradeSelects) OxyBank.upgradeSelects();
}

function addCondition(btn) {
    const fieldOpts = buildFieldOptions('');
    const html = `
        <div class="schema-field-row" style="margin-bottom:6px;">
            <select class="form-control cond-field">${fieldOpts}</select>
            <select class="form-control cond-mode" style="max-width:140px;"></select>
            <button class="btn btn-icon btn-secondary" onclick="$(this).parent().remove()">&times;</button>
        </div>`;
    const $row = $(html);
    $(btn).prev('.api-conditions').append($row);
    const $field = $row.find('.cond-field');
    const $mode = $row.find('.cond-mode');
    _refreshCondModeOptions($mode, $field.val(), 'exact');
    $field.on('change', function () {
        _refreshCondModeOptions($mode, $(this).val());
    });
    OxyBank.upgradeSelects();
}

// ---- Submit ----

async function submitCreateBank() {
    const name = $('#bankName').val().trim();
    if (!name) { OxyBank.showToast('Name required', 'error'); return; }

    const mode = $('#schemaModeSwitch button.active').data('mode');
    let schema_fields = [];
    let has_sys_chunk = false;
    let scene_template_id = '';

    if (mode === 'personalized') {
        has_sys_chunk = $('#sysChunkCheck').is(':checked');
        $('#schemaFields .schema-field-row').each(function () {
            const inputs = $(this).find('input, select');
            const fname = $(inputs[0]).val().trim();
            if (fname) {
                schema_fields.push({
                    name: fname,
                    type: $(inputs[1]).val(),
                    description: $(inputs[2]).val().trim(),
                });
            }
        });
    } else {
        scene_template_id = $('#sceneSelect').val();
        const tpl = sceneTemplates.find(t => t.id === scene_template_id);
        if (tpl) {
            schema_fields = tpl.fields || [];
            has_sys_chunk = tpl.has_sys_chunk || false;
        }
    }

    const retrieval_apis = [];
    $('#retrievalApis .retrieval-api-block').each(function () {
        const apiName = $(this).find('.api-name').val().trim();
        if (!apiName) return;
        const conditions = [];
        $(this).find('.api-conditions .schema-field-row').each(function () {
            const field = $(this).find('.cond-field').val();
            const cmode = $(this).find('.cond-mode').val();
            if (field) conditions.push({ field, mode: cmode });
        });
        const output = [];
        $(this).find('.output-check:checked').each(function () {
            output.push($(this).val());
        });
        retrieval_apis.push({ name: apiName, search_conditions: conditions, output_fields: output });
    });

    const payload = {
        name,
        description: $('#bankDesc').val().trim(),
        schema_mode: mode,
        has_sys_chunk,
        scene_template_id,
        schema_fields,
        retrieval_apis,
        embedding_backend: $('#embeddingBackend').val(),
    };

    try {
        OxyBank.showLoading();
        await api.post('/banks', payload);
        OxyBank.closeModal('#createModal');
        OxyBank.showToast('Bank created', 'success');
        loadBanks();
        // Refresh sidebar bank selector
        $('#globalBankSelect').find('option:not(:first)').remove();
        OxyBank.loadBankSelector();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    } finally {
        OxyBank.hideLoading();
    }
}

// ---- Helpers ----

function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
