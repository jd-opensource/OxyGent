/**
 * agents.js — Agent management page: cards, flow visualization, execution logs
 */
let agents = [];
let logPage = 1;
const LOG_PAGE_SIZE = 20;

// Canonical Trigger Status options offered in the picker. Users can add extras
// (custom values entered per-bank) or select existing statuses observed in the
// bank's samples — both merge with this list at open time.
const CANONICAL_STATUSES = [
    'Imported', 'To Assign', 'Assigned', 'Ignored',
    'To Annotate', 'Annotated', 'Rejected', 'Published',
];
// Cache of picker state for the currently-open modal:
//   available: full list of options rendered as chips (order preserved)
//   selected:  subset of `available` that's checked
let statusPickerState = { available: [], selected: [] };

// Bank's writable field list for the set_field step dropdown. Populated when the
// agent modal opens against the current bank. Excludes readonly system fields
// (sample id / document id / prev_* history / created/updated timestamps) since
// writing to them has no effect. Includes:
//   - sys_status / sys_template / sys_priority / sys_executor / sys_overview /
//     sys_remarks / sys_next_status / sys_next_template / sys_next_executor
//   - sys_chunk (only if the bank has has_sys_chunk enabled)
//   - all user-defined schema fields
let writableFieldOptions = [];

// System fields that inline agents may legitimately overwrite. Everything else
// on a sample (sys_sample_id, sys_document_id, sys_prev_*, sys_create_time,
// sys_update_time) is either an identity/audit field the platform manages, so
// we hide it from the dropdown.
const WRITABLE_SYS_FIELDS = [
    'sys_status', 'sys_template', 'sys_priority', 'sys_executor',
    'sys_overview', 'sys_remarks',
    'sys_next_status', 'sys_next_template', 'sys_next_executor',
];

$(function () {
    $(document).on('oxybank:bank-change', function (e, bankId) {
        if (bankId) { loadAll(); } else { clear(); }
    });

    // Redraw on language switch — the three renderers below (renderAgentCards /
    // renderFlow / renderLogs) inline i18n.t() results into their HTML strings,
    // so i18n.apply()'s data-i18n DOM scan can't refresh them. Re-run each from
    // cached state where possible; for logs we re-fetch since renderLogs()
    // signature requires the raw response.
    $(document).on('oxybank:lang-change', function () {
        if (!OxyBank.getCurrentBankId()) return;
        renderAgentCards();
        renderFlow();
        loadLogs();
    });
});

function clear() {
    agents = [];
    $('#agentCards').empty();
    $('#flowGraph').empty();
    $('#logList').empty();
    $('#logAgentFilter').find('option:not(:first)').remove();
}

async function loadAll() {
    await loadAgents();
    renderFlow();
    loadLogs();
}

// ---- Agents CRUD ----

async function loadAgents() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        const data = await api.get(`/banks/${bankId}/agents`);
        agents = data.items || data;
        renderAgentCards();
        updateLogAgentFilter();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderAgentCards() {
    const $c = $('#agentCards');
    $c.empty();
    if (!agents.length) {
        $c.html(`<div class="empty-state"><h3>${i18n.t('common.empty')}</h3><p>${i18n.t('agents.empty_hint')}</p></div>`);
        return;
    }
    agents.forEach(a => {
        const statuses = (a.trigger_statuses || []).map(s => `<span class="badge badge-primary">${esc(s)}</span>`).join(' ');
        // Show either the URL or a short "Inline (N steps)" summary depending on agent kind
        const kind = a.kind || 'url';
        const desc = kind === 'inline'
            ? `<span class="badge badge-secondary">${i18n.t('agents.kind_inline_short')}</span> ${i18n.t('agents.steps_count').replace('{n}', (a.steps || []).length)}`
            : `<span style="color:var(--gray-400);font-family:monospace;font-size:11px;">${esc(a.service_url)}</span>`;
        $c.append(`
            <div class="agent-card">
                <div class="agent-info">
                    <h4>${esc(a.name)}</h4>
                    <div class="agent-meta">${desc}</div>
                    <div style="margin-top:6px;">${i18n.t('agents.trigger_status')}: ${statuses}</div>
                </div>
                <div class="agent-actions">
                    <label class="switch" title="${a.enabled ? 'Enabled' : 'Disabled'}">
                        <input type="checkbox" ${a.enabled ? 'checked' : ''} onchange="toggleAgent('${a.id}', this.checked)">
                        <span class="slider"></span>
                    </label>
                    <button class="btn btn-sm btn-secondary" onclick="editAgent('${a.id}')">${i18n.t('common.edit')}</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteAgent('${a.id}')">${i18n.t('common.delete')}</button>
                </div>
            </div>`);
    });
}

// Currently-being-edited inline agent's step tree. Kept as a JS array of {type, ...}
// objects; the DOM is rebuilt from this array on every mutation. See renderSteps().
let stepEditorState = [];

function openAddAgent() {
    if (!OxyBank.getCurrentBankId()) return;
    $('#editAgentId').val('');
    // Pre-fill a sensible default name: "<bank>-agent-<next>" using the smallest
    // integer that doesn't already exist on this bank. Users can rename before
    // saving; this saves the common case of a throwaway name.
    $('#agentName').val(_nextDefaultAgentName());
    $('#agentUrl').val('');
    stepEditorState = [];
    setAgentKind('url');
    loadWritableFieldOptions();  // async; step dropdowns re-render when it arrives
    renderSteps();
    openStatusPicker([]);
    $('#agentModalTitle').text(i18n.t('agents.add'));
    OxyBank.openModal('#agentModal');
}

function _nextDefaultAgentName() {
    const bank = OxyBank.getCurrentBankId() || 'agent';
    const prefix = `${bank}-agent-`;
    const used = new Set((agents || []).map(a => a.name));
    let n = 1;
    while (used.has(`${prefix}${n}`)) n += 1;
    return `${prefix}${n}`;
}

function editAgent(id) {
    const a = agents.find(x => x.id === id);
    if (!a) return;
    $('#editAgentId').val(id);
    $('#agentName').val(a.name);
    $('#agentUrl').val(a.service_url || '');
    stepEditorState = JSON.parse(JSON.stringify(a.steps || []));  // deep clone
    setAgentKind(a.kind || 'url');
    loadWritableFieldOptions();
    renderSteps();
    openStatusPicker(a.trigger_statuses || []);
    $('#agentModalTitle').text(i18n.t('common.edit'));
    OxyBank.openModal('#agentModal');
}

// Fetch this bank's schema and populate writableFieldOptions.
// Falls back to just the sys_* whitelist if the fetch fails (e.g. offline).
// Re-renders the step editor once options arrive so any existing dropdowns
// pick up the fresh list without the user having to reopen the modal.
async function loadWritableFieldOptions() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) {
        writableFieldOptions = WRITABLE_SYS_FIELDS.slice();
        return;
    }
    try {
        const bank = await api.get(`/banks/${bankId}`);
        const custom = (bank && bank.schema && bank.schema.fields || []).map(f => f.name).filter(Boolean);
        const list = WRITABLE_SYS_FIELDS.slice();
        if (bank && bank.has_sys_chunk) list.push('sys_chunk');
        custom.forEach(n => { if (!list.includes(n)) list.push(n); });
        writableFieldOptions = list;
    } catch (e) {
        writableFieldOptions = WRITABLE_SYS_FIELDS.slice();
    }
    // Re-render in case the step editor is already open with stale options.
    if (stepEditorState) renderSteps();
}

// ---- Kind switcher (URL / Inline) ----

function setAgentKind(kind) {
    $('#agentKindSwitch button').removeClass('active').filter(`[data-kind="${kind}"]`).addClass('active');
    $('#agentUrlBlock').toggle(kind === 'url');
    $('#agentInlineBlock').toggle(kind === 'inline');
}

$(document).on('click', '#agentKindSwitch button', function () {
    setAgentKind($(this).data('kind'));
});

async function openStatusPicker(preselected) {
    // Build the picker's option list = canonical + bank's live statuses + already-
    // selected values (so we never drop a status that's in use but not canonical).
    const merged = new Set(CANONICAL_STATUSES);
    (preselected || []).forEach(s => merged.add(s));

    // Fetch live statuses from the bank so existing custom values (added via
    // deposit/agents earlier) surface in the picker automatically. Non-fatal.
    const bankId = OxyBank.getCurrentBankId();
    if (bankId) {
        try {
            const data = await api.get(`/banks/${bankId}/samples/statuses`);
            (data.items || []).forEach(b => { if (b.key) merged.add(String(b.key)); });
        } catch (e) {}
    }

    statusPickerState.available = Array.from(merged);
    statusPickerState.selected = (preselected || []).slice();
    renderStatusPicker();
}

function renderStatusPicker() {
    const $p = $('#agentStatusesPicker');
    $p.empty();
    const selectedSet = new Set(statusPickerState.selected);
    statusPickerState.available.forEach(status => {
        const checked = selectedSet.has(status);
        const $chip = $(`<label class="status-chip${checked ? ' selected' : ''}">
            <input type="checkbox" ${checked ? 'checked' : ''}>
            <span>${esc(status)}</span>
        </label>`);
        $chip.find('input').on('change', function () {
            const isOn = $(this).is(':checked');
            $chip.toggleClass('selected', isOn);
            if (isOn) {
                if (!statusPickerState.selected.includes(status)) statusPickerState.selected.push(status);
            } else {
                statusPickerState.selected = statusPickerState.selected.filter(s => s !== status);
            }
        });
        $p.append($chip);
    });
}

function addCustomStatusOption() {
    // Let users add a status not in the canonical list (e.g. a domain-specific state
    // like "PendingReview"). The typed value is appended to the picker's option list,
    // pre-selected, and the input cleared.
    const $inp = $('#agentStatusCustom');
    const val = ($inp.val() || '').trim();
    if (!val) return;
    if (!statusPickerState.available.includes(val)) statusPickerState.available.push(val);
    if (!statusPickerState.selected.includes(val)) statusPickerState.selected.push(val);
    $inp.val('');
    renderStatusPicker();
}

async function submitAgent() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const editId = $('#editAgentId').val();
    const name = $('#agentName').val().trim();
    const trigger_statuses = statusPickerState.selected.slice();
    const kind = $('#agentKindSwitch button.active').data('kind') || 'url';
    if (!name || !trigger_statuses.length) {
        OxyBank.showToast(i18n.t('agents.fields_required'), 'error');
        return;
    }
    let payload;
    if (kind === 'url') {
        const service_url = $('#agentUrl').val().trim();
        if (!service_url) {
            OxyBank.showToast(i18n.t('agents.fields_required'), 'error');
            return;
        }
        payload = { name, kind: 'url', service_url, steps: [], trigger_statuses };
    } else {
        // Read the current step-editor state into raw JSON. Backend will reject
        // if it's empty or contains an unsupported step type.
        const steps = readStepsFromEditor();
        if (!steps.length) {
            OxyBank.showToast(i18n.t('agents.steps_required'), 'error');
            return;
        }
        payload = { name, kind: 'inline', service_url: '', steps, trigger_statuses };
    }
    try {
        if (editId) {
            await api.put(`/banks/${bankId}/agents/${editId}`, payload);
        } else {
            await api.post(`/banks/${bankId}/agents`, payload);
        }
        OxyBank.closeModal('#agentModal');
        OxyBank.showToast(i18n.t('common.save') + ' OK', 'success');
        await loadAgents();
        renderFlow();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

// ---- Inline step editor ----------------------------------------------------
//
// stepEditorState holds the tree (array of step objects; each may have then/else
// which are themselves arrays of step objects). The DOM is rebuilt from scratch
// on every mutation via renderSteps(). Each step's controls .on('input')-write
// back into stepEditorState by walking the same tree path.

function addStep(type, parentPath) {
    // parentPath === undefined → append to top-level list
    // parentPath === [i, 'then'|'else'] → append to that branch of step i (top-level)
    // deeper nesting → same shape, longer path
    const step = _defaultStep(type);
    const target = _resolveList(parentPath);
    target.push(step);
    renderSteps();
}

function removeStep(path) {
    // path = [...ancestor, index]  → remove item at index from parent list
    if (!path || !path.length) return;
    const idx = path[path.length - 1];
    const parent = _resolveList(path.slice(0, -1));
    parent.splice(idx, 1);
    renderSteps();
}

function _defaultStep(type) {
    if (type === 'llm')       return { type: 'llm', name: '', prompt: '' };
    if (type === 'set_field') {
        // Pre-select the first schema field so a newly-added set_field step doesn't
        // land with an empty select (which the disabled placeholder would surface).
        const firstField = writableFieldOptions[0] || '';
        return { type: 'set_field', field: firstField, value: '' };
    }
    if (type === 'if')        return { type: 'if', when: { var: '', op: 'contains', value: '' }, then: [], else: [] };
    return { type };
}

function _resolveList(path) {
    // Walk stepEditorState using [i, branch, i, branch, ...] path pairs.
    if (!path || !path.length) return stepEditorState;
    let list = stepEditorState;
    for (let i = 0; i + 1 < path.length; i += 2) {
        const idx = path[i], branch = path[i + 1];
        list = list[idx][branch] = list[idx][branch] || [];
    }
    return list;
}

function _resolveStep(path) {
    // Walk to the step object at `path`. Path ends with the step's index within its
    // parent list. E.g. [0] = first top-level step; [0, 'then', 1] = 2nd step in
    // .then branch of the first top-level step.
    if (!path || !path.length) return null;
    const listPath = path.slice(0, -1);
    const idx = path[path.length - 1];
    return _resolveList(listPath)[idx];
}

function renderSteps() {
    const $list = $('#agentStepsList');
    $list.empty();
    _appendSteps($list, stepEditorState, []);
    if (!stepEditorState.length) {
        $list.append(`<div style="color:var(--gray-400);font-size:12px;padding:8px 0;">${i18n.t('agents.steps_empty_hint')}</div>`);
    }
    // Every re-render throws away the previously-mounted custom-select wrappers,
    // so we need to reset the cs-upgraded flag on each native <select> we own and
    // ask OxyBank.upgradeSelects() to rebuild them. This gives us the same styled
    // dropdown used elsewhere in the app (schema field row, bank picker, etc.)
    // instead of the browser-default look.
    $list.find('select.form-control').each(function () {
        $(this).removeClass('cs-upgraded');
        $(this).next('.custom-select').remove();
    });
    if (window.OxyBank && OxyBank.upgradeSelects) OxyBank.upgradeSelects();
}

function _appendSteps($container, list, ancestorPath) {
    list.forEach((step, idx) => {
        const path = ancestorPath.concat([idx]);
        const $card = _renderStepCard(step, path);
        $container.append($card);
    });
}

function _renderStepCard(step, path) {
    const $card = $(`<div class="agent-step"></div>`);
    const typeLabel = i18n.t('agents.step_type_' + step.type) || step.type;
    $card.append(`
        <div class="agent-step-head">
            <span class="agent-step-type">${esc(typeLabel)}</span>
            <button type="button" class="btn btn-icon btn-danger" style="font-size:12px;padding:0 6px;height:auto;line-height:1.6;" onclick='removeStep(${JSON.stringify(path)})' title="${i18n.t('common.delete')}">×</button>
        </div>
    `);
    const $body = $(`<div class="agent-step-body"></div>`);
    if (step.type === 'llm') {
        $body.append(_field(i18n.t('agents.step_field_name'), `<input type="text" class="form-control" value="${esc(step.name || '')}" placeholder="e.g. classify">`,
            (v) => { _resolveStep(path).name = v; }));
        $body.append(_field(i18n.t('agents.step_field_prompt'), `<textarea class="form-control" rows="3" placeholder="Prompt for the LLM. Use {{sample.field}} to inject sample values.">${esc(step.prompt || '')}</textarea>`,
            (v) => { _resolveStep(path).prompt = v; }));
    } else if (step.type === 'set_field') {
        // Single inline row: [Field label] [select] [Value label] [input]
        // Field is a dropdown seeded from the bank schema so users can't typo
        // a field name. If the step's saved field isn't in the current schema
        // (e.g. schema changed after the agent was created), include it as an
        // extra option so it stays selected and editable rather than silently
        // reset to the first option.
        const opts = writableFieldOptions.slice();
        if (step.field && !opts.includes(step.field)) opts.unshift(step.field);
        const optionsHtml = opts.length
            ? opts.map(f => `<option value="${esc(f)}"${f === step.field ? ' selected' : ''}>${esc(f)}</option>`).join('')
            : `<option value="">${esc(i18n.t('agents.step_field_field_placeholder'))}</option>`;
        const $row = $(`
            <div class="agent-step-inline">
                <label class="agent-step-inline-label">${esc(i18n.t('agents.step_field_field'))}</label>
                <select class="form-control agent-step-inline-input agent-step-field">${optionsHtml}</select>
                <label class="agent-step-inline-label">${esc(i18n.t('agents.step_field_value'))}</label>
                <input type="text" class="form-control agent-step-inline-input agent-step-value" value="${esc(step.value == null ? '' : String(step.value))}" placeholder='e.g. Published or {{steps.classify.output}}'>
            </div>
        `);
        $row.find('.agent-step-field').on('change', function () { _resolveStep(path).field = $(this).val(); });
        $row.find('.agent-step-value').on('input', function () { _resolveStep(path).value = $(this).val(); });
        $body.append($row);
    } else if (step.type === 'if') {
        // Condition builder: var | op | value
        const opts = ['contains', 'not_contains', 'equals', 'not_equals', 'starts_with', 'ends_with']
            .map(op => `<option value="${op}" ${step.when?.op === op ? 'selected' : ''}>${op}</option>`).join('');
        $body.append(`
            <label>${i18n.t('agents.step_field_when')}</label>
            <div class="agent-step-row">
                <input type="text" class="form-control cond-var" style="flex:2;" value="${esc(step.when?.var || '')}" placeholder="steps.classify.output">
                <select class="form-control cond-op" style="flex:1;">${opts}</select>
                <input type="text" class="form-control cond-val" style="flex:2;" value="${esc(step.when?.value == null ? '' : String(step.when.value))}" placeholder="Yes">
            </div>
        `);
        $body.find('.cond-var').on('input', function () { _resolveStep(path).when.var = $(this).val(); });
        $body.find('.cond-op').on('change', function () { _resolveStep(path).when.op = $(this).val(); });
        $body.find('.cond-val').on('input', function () { _resolveStep(path).when.value = $(this).val(); });

        // Nested THEN / ELSE lists
        const $thenBox = $(`<div class="agent-steps-nested"><div class="agent-steps-nested-label">THEN</div></div>`);
        _appendSteps($thenBox, step.then || [], path.concat(['then']));
        $thenBox.append(_nestedAddRow(path, 'then'));
        $body.append($thenBox);

        const $elseBox = $(`<div class="agent-steps-nested"><div class="agent-steps-nested-label">ELSE</div></div>`);
        _appendSteps($elseBox, step.else || [], path.concat(['else']));
        $elseBox.append(_nestedAddRow(path, 'else'));
        $body.append($elseBox);
    }
    $card.append($body);
    return $card;
}

function _field(label, controlHtml, onInput) {
    const $group = $(`<div><label>${esc(label)}</label>${controlHtml}</div>`);
    $group.find('input, textarea, select').on('input change', function () { onInput($(this).val()); });
    return $group;
}

function _nestedAddRow(parentStepPath, branch) {
    // Mirror the top-level "add step" buttons verbatim (same i18n keys, same labels)
    // so users see one consistent vocabulary. Previously the labels were hand-crafted
    // strings — "+ LLM" / "+ If" were untranslated, and the middle one prepended a
    // literal "+ " to a key that already starts with "+ ", producing "+ + 字段赋值".
    const $row = $(`<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;">
        <button type="button" class="btn btn-sm btn-secondary">${esc(i18n.t('agents.step_add_llm'))}</button>
        <button type="button" class="btn btn-sm btn-secondary">${esc(i18n.t('agents.step_add_set'))}</button>
        <button type="button" class="btn btn-sm btn-secondary">${esc(i18n.t('agents.step_add_if'))}</button>
    </div>`);
    const buttons = $row.find('button');
    buttons.eq(0).on('click', () => addStep('llm', parentStepPath.concat([branch])));
    buttons.eq(1).on('click', () => addStep('set_field', parentStepPath.concat([branch])));
    buttons.eq(2).on('click', () => addStep('if', parentStepPath.concat([branch])));
    return $row;
}

function readStepsFromEditor() {
    // stepEditorState is already the source of truth — nothing to serialize from
    // DOM. Any half-empty steps still get submitted so backend can validate them
    // and surface a clear error message.
    return JSON.parse(JSON.stringify(stepEditorState));
}

async function deleteAgent(id) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    if (!confirm(i18n.t('agents.confirm_delete'))) return;
    try {
        await api.del(`/banks/${bankId}/agents/${id}`);
        OxyBank.showToast('Deleted', 'success');
        await loadAgents();
        renderFlow();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function toggleAgent(id, enabled) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        await api.put(`/banks/${bankId}/agents/${id}`, { enabled });
        await loadAgents();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

// ---- Flow Visualization ----

function renderFlow() {
    const $g = $('#flowGraph');
    $g.empty();
    if (!agents.length) {
        $g.html(`<span style="color:var(--gray-400);font-size:13px;">${i18n.t('agents.no_flow')}</span>`);
        return;
    }

    // Build a directed graph: input_status -> agent -> output_status (inferred)
    // We show: [status] --agent--> [status] --agent--> ...
    // Collect all trigger statuses and build chains
    const edges = []; // { from, agent, to }
    agents.forEach(a => {
        if (!a.enabled) return;
        (a.trigger_statuses || []).forEach(s => {
            // The "to" status is unknown until agent runs, show as "?"
            edges.push({ from: s, agentName: a.name, to: '?' });
        });
    });

    // Collect unique statuses in order. "Imported" is the canonical starting state
    // for a fresh sample; make sure the flow graph always includes it as an anchor
    // (even if no agent triggers on it) so the graph reads left-to-right.
    const allStatuses = new Set();
    allStatuses.add('Imported');
    edges.forEach(e => { allStatuses.add(e.from); allStatuses.add(e.to); });

    // Build a simple left-to-right flow
    // Group edges by "from" status, render each chain
    const byFrom = {};
    edges.forEach(e => {
        if (!byFrom[e.from]) byFrom[e.from] = [];
        byFrom[e.from].push(e);
    });

    // Start with statuses that are triggers, build left-to-right
    const rendered = new Set();
    const statusOrder = ['Imported'];
    // BFS to discover order
    const queue = [...statusOrder];
    while (queue.length) {
        const s = queue.shift();
        if (rendered.has(s)) continue;
        rendered.add(s);
        const outEdges = byFrom[s] || [];
        outEdges.forEach(e => {
            if (!rendered.has(e.to) && e.to !== '?') queue.push(e.to);
        });
    }
    // Add remaining
    allStatuses.forEach(s => { if (!rendered.has(s) && s !== '?') statusOrder.push(s); });

    // Render
    let html = '';
    statusOrder.forEach((status, idx) => {
        html += `<div class="flow-node"><div class="flow-status">${esc(status)}</div></div>`;
        const outEdges = byFrom[status] || [];
        if (outEdges.length) {
            const agentNames = outEdges.map(e => e.agentName).join(', ');
            html += `<div class="flow-arrow">
                <div class="flow-arrow-line">→</div>
                <div class="flow-arrow-label" title="${esc(agentNames)}">${esc(agentNames)}</div>
            </div>`;
            // Add next status node if it's "?"
            if (outEdges.every(e => e.to === '?')) {
                html += `<div class="flow-node"><div class="flow-status" style="background:var(--gray-100);color:var(--gray-400);">…</div></div>`;
            }
        }
    });

    $g.html(html);
}

// ---- Execution Logs ----

function updateLogAgentFilter() {
    const $sel = $('#logAgentFilter');
    $sel.find('option:not(:first)').remove();
    agents.forEach(a => {
        $sel.append(`<option value="${a.id}">${esc(a.name)}</option>`);
    });
}

async function loadLogs() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const agentId = $('#logAgentFilter').val();
    const success = $('#logStatusFilter').val();
    let params = `?page=${logPage}&size=${LOG_PAGE_SIZE}`;
    if (agentId) params += `&agent_id=${agentId}`;
    if (success) params += `&success=${success}`;
    try {
        const data = await api.get(`/banks/${bankId}/agents/logs${params}`);
        renderLogs(data);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderLogs(data) {
    const items = data.items || [];
    const total = data.total || 0;
    const totalPages = Math.ceil(total / LOG_PAGE_SIZE);
    const $list = $('#logList');
    $list.empty();

    if (!items.length) {
        $list.html(`<p style="color:var(--gray-400);font-size:13px;text-align:center;padding:20px;">${i18n.t('common.empty')}</p>`);
        return;
    }

    items.forEach(log => {
        const statusClass = log.success ? 'ok' : 'fail';
        const duration = log.duration_ms != null ? `${log.duration_ms}ms` : '-';
        $list.append(`
            <div class="log-row">
                <div class="log-status ${statusClass}"></div>
                <div style="min-width:120px;font-weight:500;">${esc(log.agent_name)}</div>
                <div style="flex:1;font-family:monospace;font-size:12px;color:var(--gray-500);">${esc(log.sample_id || '').substring(0, 12)}…</div>
                <div><span class="badge badge-primary">${esc(log.input_status)}</span></div>
                <div style="color:var(--gray-400);">→</div>
                <div><span class="badge ${log.success ? 'badge-success' : 'badge-danger'}">${log.success ? esc(log.output_status || '-') : 'ERROR'}</span></div>
                <div style="min-width:60px;text-align:right;color:var(--gray-500);font-size:12px;">${duration}</div>
                <div style="min-width:140px;text-align:right;color:var(--gray-400);font-size:12px;">${OxyBank.formatDate(log.timestamp)}</div>
                ${log.error ? `<div style="width:100%;color:var(--danger);font-size:12px;margin-top:2px;padding-left:20px;">${esc(log.error)}</div>` : ''}
            </div>`);
    });

    OxyBank.renderPagination('#logPagination', logPage, totalPages, (p) => {
        logPage = p;
        loadLogs();
    });
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
