/**
 * templates.js — Template management: list + AI chat + preview/test
 */
let templates = [];
let currentTpl = null;
let currentTplJson = null; // parsed template JSON from AI or selected template
let chatHistory = [];
let testSampleData = {};
let bankSchema = []; // schema fields of the currently selected bank

function emptyTemplateSkeleton() {
    // Starter JSON so the panel is meaningful from the moment the page loads.
    return {
        name: '',
        description: '',
        editable_fields: [],
        field_constraints: {},
        layout: { sections: [] },
    };
}

$(function () {
    // Wire up live JSON editing on the template JSON textarea. Every keystroke
    // re-parses; valid JSON refreshes the preview immediately, invalid JSON
    // shows a small error hint without wiping the preview.
    $('#tplJsonBlock').on('input', onTplJsonEdited);

    $(document).on('oxybank:bank-change', function (e, bankId) {
        if (bankId) {
            initEmptyPanels();
            loadBankSchema();
            loadTemplates();
            loadInitialRandomSample();
        } else {
            $('#tplList').empty();
            resetToEmpty();
            bankSchema = [];
        }
    });

    // Re-render on language switch — list badges and preview headings embed translated
    // strings directly in HTML, so we need to redraw them from cached state.
    $(document).on('oxybank:lang-change', function () {
        renderTplList();
        if (currentTplJson) {
            renderPreview(currentTplJson, testSampleData);
        } else {
            $('#previewRender').html(`<p class="tpl-empty-hint">${i18n.t('templates.preview_empty_hint')}</p>`);
        }
    });

    // If a bank is already selected on first load (e.g., user refreshed), kick things off.
    if (OxyBank.getCurrentBankId()) {
        initEmptyPanels();
        loadBankSchema();
        loadTemplates();
        loadInitialRandomSample();
    } else {
        initEmptyPanels();
    }
});

function initEmptyPanels() {
    // Only initialize the JSON textarea if user hasn't typed anything yet
    // (avoids clobbering their in-progress edits on lang switch etc.).
    if (!$('#tplJsonBlock').val()) {
        currentTplJson = emptyTemplateSkeleton();
        $('#tplJsonBlock').val(JSON.stringify(currentTplJson, null, 2));
    }
    $('#tplJsonError').hide().text('');
    $('#tplJsonBlock').removeClass('invalid');
}

function resetToEmpty() {
    currentTpl = null;
    currentTplJson = emptyTemplateSkeleton();
    testSampleData = {};
    $('#tplJsonBlock').val(JSON.stringify(currentTplJson, null, 2)).removeClass('invalid');
    $('#tplJsonError').hide().text('');
    $('#testDataInput').val('');
    $('#testResult').empty();
    $('#btnDeleteTpl').hide();
    $('#btnSaveTpl').show();
    $('#previewRender').html(`<p class="tpl-empty-hint">${i18n.t('templates.preview_empty_hint')}</p>`);
}

async function loadBankSchema() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) { bankSchema = []; return; }
    try {
        const bank = await api.get(`/banks/${bankId}`);
        const fields = (bank && bank.schema && bank.schema.fields) || [];
        // sys_chunk is a system field but relevant to templates when the bank enables chunking.
        const enriched = fields.map(f => ({ name: f.name, type: f.type, description: f.description || '' }));
        if (bank && bank.has_sys_chunk) {
            enriched.push({ name: 'sys_chunk', type: 'text', description: '文档切分后的文本块 (chunk of the uploaded document)' });
        }
        bankSchema = enriched;
    } catch (e) {
        bankSchema = [];
    }
}

async function loadInitialRandomSample() {
    // Populate the test-data textarea with a real sample so the annotator can
    // preview immediately. Silent on failure — the panel still works without one.
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        const sample = await api.get(`/banks/${bankId}/samples/random`);
        const filtered = {};
        Object.entries(sample || {}).forEach(([k, v]) => {
            if (k === 'id' || k === '_score') return;
            filtered[k] = v;
        });
        $('#testDataInput').val(JSON.stringify(filtered, null, 2));
        testSampleData = filtered;
        if (currentTplJson) renderPreview(currentTplJson, testSampleData);
    } catch (e) {
        // 404 (no samples yet) is fine — leave test data empty.
    }
}

// ---- Template List (Left Panel) ----

async function loadTemplates() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        const data = await api.get(`/banks/${bankId}/templates`);
        const raw = data.items || data;
        // Templates are global — sort built-ins first, then by name for stable ordering.
        templates = raw.slice().sort((a, b) => {
            const ba = a.is_builtin ? 0 : 1;
            const bb = b.is_builtin ? 0 : 1;
            if (ba !== bb) return ba - bb;
            return String(a.name || '').localeCompare(String(b.name || ''));
        });
        renderTplList();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderTplList() {
    const $list = $('#tplList');
    $list.empty();
    templates.forEach(t => {
        const active = currentTpl && currentTpl.id === t.id ? ' active' : '';
        const badge = t.is_builtin
            ? `<span class="tpl-builtin">${i18n.t('templates.builtin')}</span>`
            : `<span class="tpl-global">${i18n.t('templates.global')}</span>`;
        $list.append(`
            <div class="tpl-item${active}" data-id="${t.id}" onclick="selectTemplate('${t.id}')">
                ${esc(t.name)}${badge}
            </div>`);
    });
}

function selectTemplate(id) {
    const t = templates.find(x => x.id === id);
    if (!t) return;
    currentTpl = t;
    currentTplJson = {
        name: t.name,
        description: t.description || '',
        editable_fields: t.editable_fields || [],
        field_constraints: t.field_constraints || {},
        layout: t.layout || {},
    };
    // Fresh chat context when switching templates so AI doesn't keep talking about
    // the previous one. Rendered messages are cleared in resetChatToIntro().
    chatHistory = [];
    resetChatToIntro();
    renderTplList();
    writeTemplateToPanel(currentTplJson);
    renderPreview(currentTplJson, testSampleData);
    // Built-in templates are read-only on the backend. Hide delete + save; the
    // Clone button remains so users can derive an editable copy.
    $('#btnDeleteTpl').toggle(!t.is_builtin);
    $('#btnSaveTpl').toggle(!t.is_builtin);
}

// ---- New / Clone ----

function newTemplate() {
    // Start from an empty skeleton, clear the panel + chat history so the user has
    // a blank slate. Doesn't hit the backend — save happens via the Save button.
    currentTpl = null;
    currentTplJson = emptyTemplateSkeleton();
    testSampleData = {};
    $('#testDataInput').val('');
    $('#testResult').empty();
    $('#btnDeleteTpl').hide();
    $('#btnSaveTpl').show();
    writeTemplateToPanel(currentTplJson);
    renderPreview(currentTplJson, testSampleData);
    renderTplList();
    chatHistory = [];
    resetChatToIntro();
    // Trigger the random sample fetch so the fresh template can immediately be previewed
    // against real data.
    loadInitialRandomSample();
}

async function cloneCurrentTemplate() {
    // Duplicate the currently-loaded template and immediately persist the copy so
    // it shows up in the list. Users can then select the copy and edit it in place.
    // Name gets a suffix (foo → foo_copy → foo_copy2 ...) to satisfy global uniqueness.
    const raw = $('#tplJsonBlock').val().trim();
    let source;
    try {
        source = raw ? JSON.parse(raw) : (currentTplJson ? JSON.parse(JSON.stringify(currentTplJson)) : null);
    } catch (e) {
        OxyBank.showToast('Invalid template JSON: ' + e.message, 'error');
        return;
    }
    if (!source) source = emptyTemplateSkeleton();

    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;

    const baseName = String(source.name || 'template');
    const newName = _nextAvailableName(baseName);

    try {
        const created = await api.post(`/banks/${bankId}/templates`, {
            name: newName,
            description: source.description || '',
            editable_fields: source.editable_fields || [],
            field_constraints: source.field_constraints || {},
            layout: source.layout || {},
        });
        await loadTemplates();
        // Auto-select the newly-created copy so the user can start editing immediately.
        if (created && created.id) {
            selectTemplate(created.id);
        }
        OxyBank.showToast(i18n.t('templates.cloned'), 'success');
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function _nextAvailableName(baseName) {
    // Pick the shortest suffix that's not taken by any existing template.
    const usedNames = new Set(templates.map(t => t.name));
    // Strip any existing _copyN suffix so cloning a clone doesn't stack them.
    const stripped = baseName.replace(/_copy\d*$/, '');
    let candidate = `${stripped}_copy`;
    if (!usedNames.has(candidate)) return candidate;
    let n = 2;
    while (usedNames.has(`${stripped}_copy${n}`)) n += 1;
    return `${stripped}_copy${n}`;
}

function resetChatToIntro() {
    $('#chatMessages').html(`<div class="chat-bubble assistant">${esc(i18n.t('templates.ai_intro'))}</div>`);
}

function writeTemplateToPanel(tplJson) {
    $('#tplJsonBlock').val(JSON.stringify(tplJson, null, 2)).removeClass('invalid');
    $('#tplJsonError').hide().text('');
}

function onTplJsonEdited() {
    const raw = $('#tplJsonBlock').val();
    if (!raw.trim()) {
        currentTplJson = null;
        $('#tplJsonBlock').removeClass('invalid');
        $('#tplJsonError').hide().text('');
        $('#previewRender').html(`<p class="tpl-empty-hint">${i18n.t('templates.preview_empty_hint')}</p>`);
        return;
    }
    try {
        const parsed = JSON.parse(raw);
        currentTplJson = parsed;
        $('#tplJsonBlock').removeClass('invalid');
        $('#tplJsonError').hide().text('');
        renderPreview(currentTplJson, testSampleData);
    } catch (e) {
        $('#tplJsonBlock').addClass('invalid');
        $('#tplJsonError').text(e.message).show();
        // Keep the last valid currentTplJson so preview doesn't blank out on every keystroke.
    }
}

// ---- AI Chat (Center Panel) ----

function sendChat() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const input = $('#chatInput').val().trim();
    if (!input) return;
    $('#chatInput').val('');

    chatHistory.push({ role: 'user', content: input });
    appendBubble('user', input);

    const $bubble = appendBubble('assistant', '...');
    let fullContent = '';

    // Send the current template JSON so the AI can iterate on it ("add a field",
    // "change these options", "rename this section") instead of always generating
    // a template from scratch. Parse from the textarea in case the user edited it.
    let currentTemplateForAi = null;
    const raw = $('#tplJsonBlock').val().trim();
    if (raw) {
        try {
            const parsed = JSON.parse(raw);
            const hasContent = parsed && (
                parsed.name ||
                (parsed.editable_fields && parsed.editable_fields.length) ||
                (parsed.layout && parsed.layout.sections && parsed.layout.sections.length)
            );
            if (hasContent) currentTemplateForAi = parsed;
        } catch (e) {
            // Invalid JSON — don't send it as context, AI will just generate fresh.
        }
    }

    api.stream(`/banks/${bankId}/templates/generate`, {
        messages: chatHistory,
        bank_schema: bankSchema,
        current_template: currentTemplateForAi,
    }, (chunk) => {
        fullContent += chunk;
        $bubble.text(fullContent);
        scrollChat();
    }, () => {
        if (fullContent) {
            chatHistory.push({ role: 'assistant', content: fullContent });
            // Try to extract JSON from response
            const tplJson = extractJson(fullContent);
            if (tplJson) {
                currentTplJson = tplJson;
                currentTpl = null;
                writeTemplateToPanel(tplJson);
                renderPreview(tplJson, testSampleData);
                $('#btnDeleteTpl').hide();
            }
        }
    });
}

function appendBubble(role, text) {
    const $el = $(`<div class="chat-bubble ${role}"></div>`).text(text);
    $('#chatMessages').append($el);
    scrollChat();
    return $el;
}

function scrollChat() {
    const el = document.getElementById('chatMessages');
    if (el) el.scrollTop = el.scrollHeight;
}

function extractJson(text) {
    // Extract ```json ... ``` block
    const match = text.match(/```json\s*([\s\S]*?)```/);
    if (match) {
        try { return JSON.parse(match[1].trim()); } catch (e) {}
    }
    // Try parsing the whole text as JSON
    try { return JSON.parse(text.trim()); } catch (e) {}
    return null;
}

// ---- Preview (Right Panel: pure rendering) ----

function renderPreview(tplJson, sampleData) {
    const $r = $('#previewRender');
    $r.empty();

    if (!tplJson) {
        $r.html(`<p class="tpl-empty-hint">${i18n.t('templates.preview_empty_hint')}</p>`);
        return;
    }

    // Empty skeleton (freshly initialized) — show hint instead of an empty form.
    const hasFields = (tplJson.editable_fields && tplJson.editable_fields.length) ||
                      (tplJson.layout && tplJson.layout.sections && tplJson.layout.sections.length);
    if (!tplJson.name && !hasFields) {
        $r.html(`<p class="tpl-empty-hint">${i18n.t('templates.preview_empty_hint')}</p>`);
        return;
    }

    // Preview header — kept small since the panel doesn't have a sample-nav bar like
    // annotation does. Content below (sections + fields) uses annotation-scale styles.
    $r.append(`<div style="font-size:15px;font-weight:600;margin-bottom:4px;">${esc(tplJson.name || 'Untitled')}</div>`);
    if (tplJson.description) {
        $r.append(`<div style="font-size:13px;color:var(--gray-500);margin-bottom:16px;">${esc(tplJson.description)}</div>`);
    }

    const layout = tplJson.layout || {};
    const constraints = tplJson.field_constraints || {};

    let html = '<form id="previewForm">';

    if (layout.sections) {
        layout.sections.forEach(sec => {
            html += `<div class="pv-section"><div class="pv-section-title">${esc(sec.title)}</div>`;
            (sec.fields || []).forEach(f => {
                const val = sampleData[f];
                const valStr = (val === null || val === undefined) ? '' : String(val);
                const constraint = constraints[f] || {};
                if (sec.readonly) {
                    // Match annotation.js: show "-" placeholder when sample field is missing.
                    html += `<div class="pv-readonly">${esc(valStr) || '<span style="color:var(--gray-300);">-</span>'}</div>`;
                    html += `<input type="hidden" name="${esc(f)}" value="${esc(valStr)}">`;
                } else {
                    html += renderPreviewField(f, valStr, constraint);
                }
            });
            html += '</div>';
        });
    } else {
        // Flat mode — show editable_fields
        (tplJson.editable_fields || []).forEach(f => {
            const val = sampleData[f] || '';
            const constraint = constraints[f] || {};
            html += renderPreviewField(f, val, constraint);
        });
    }
    html += '</form>';
    $r.append(html);

    // Wire show_when
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

function renderPreviewField(field, value, constraint) {
    // Mirror annotation.js renderConstrainedField exactly so what the user sees in
    // the preview matches the real annotation workbench.
    const type = constraint.type || 'text';
    let html = `<div class="form-group"><label>${esc(field)}</label>`;

    if (type === 'radio') {
        html += '<div class="pv-radio-group">';
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

function loadTestPreview() {
    const raw = $('#testDataInput').val().trim();
    if (!raw) { OxyBank.showToast(i18n.t('templates.test_data_required'), 'error'); return; }
    try {
        testSampleData = JSON.parse(raw);
    } catch (e) {
        OxyBank.showToast('Invalid JSON', 'error');
        return;
    }
    if (currentTplJson) {
        renderPreview(currentTplJson, testSampleData);
    }
}

async function fetchRandomSample() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        const sample = await api.get(`/banks/${bankId}/samples/random`);
        // Show every field so the annotator sees exactly what a real sample looks like.
        // Only strip ES/Vearch internal markers (id/_score) — those aren't real fields.
        const filtered = {};
        Object.entries(sample || {}).forEach(([k, v]) => {
            if (k === 'id' || k === '_score') return;
            filtered[k] = v;
        });
        $('#testDataInput').val(JSON.stringify(filtered, null, 2));
        testSampleData = filtered;
        if (currentTplJson) {
            renderPreview(currentTplJson, testSampleData);
        }
    } catch (e) {
        const msg = (e && e.message) || 'Failed to fetch sample';
        OxyBank.showToast(msg, 'error');
    }
}

function runTest() {
    if (!currentTplJson) return;
    const $form = $('#previewForm');
    const result = Object.assign({}, testSampleData);
    $form.find('input:not([type=hidden]), textarea, select').each(function () {
        if (this.type === 'radio' && !this.checked) return;
        result[this.name] = $(this).val();
    });
    // Also include hidden fields (readonly)
    $form.find('input[type=hidden]').each(function () {
        result[this.name] = $(this).val();
    });
    $('#testResult').html(`<div class="pv-section-title" style="margin-top:8px;">${i18n.t('templates.test_result')}</div><div class="test-result-box">${esc(JSON.stringify(result, null, 2))}</div>`);
}

// ---- Save / Delete ----

async function saveTemplate() {
    // Prefer the live textarea contents so users can edit and save in one gesture.
    const raw = $('#tplJsonBlock').val().trim();
    if (!raw) { OxyBank.showToast('Template JSON is empty', 'error'); return; }
    let tplJson;
    try {
        tplJson = JSON.parse(raw);
    } catch (e) {
        OxyBank.showToast('Invalid template JSON: ' + e.message, 'error');
        return;
    }
    currentTplJson = tplJson;
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const name = tplJson.name || 'Untitled';
    const payload = {
        name: name,
        description: tplJson.description || '',
        editable_fields: tplJson.editable_fields || [],
        field_constraints: tplJson.field_constraints || {},
        layout: tplJson.layout || {},
    };
    // If a template is currently loaded, PUT to update it in place. Otherwise POST
    // a new one. Built-in templates are read-only (backend rejects updates), so
    // block the client-side call early with a clear message.
    const editingExisting = currentTpl && currentTpl.id;
    if (editingExisting && currentTpl.is_builtin) {
        OxyBank.showToast(i18n.t('templates.builtin_readonly'), 'error');
        return;
    }
    try {
        if (editingExisting) {
            await api.put(`/banks/${bankId}/templates/${currentTpl.id}`, payload);
        } else {
            await api.post(`/banks/${bankId}/templates`, payload);
        }
        OxyBank.showToast(i18n.t('templates.saved'), 'success');
        await loadTemplates();
        // Re-select the template we just saved so `currentTpl` reflects DB state
        // (esp. the new UUID for a fresh create) — otherwise the next Save would
        // create yet another duplicate.
        const savedName = name;
        const match = templates.find(t => t.name === savedName);
        if (match) selectTemplate(match.id);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function deleteCurrentTemplate() {
    if (!currentTpl) return;
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    if (!confirm(i18n.t('templates.confirm_delete'))) return;
    try {
        await api.del(`/banks/${bankId}/templates/${currentTpl.id}`);
        OxyBank.showToast(i18n.t('templates.deleted'), 'success');
        resetToEmpty();
        loadTemplates();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
