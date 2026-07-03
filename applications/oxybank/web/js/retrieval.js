/**
 * retrieval.js — API Test page: show all APIs with docs, curl/python snippets, and inline test
 */
let bankData = null;
let currentApiId = null;

$(function () {
    $(document).on('oxybank:bank-change', function (e, bankId) {
        if (bankId) {
            loadBankAndApis();
        } else {
            $('#apiCards').empty();
            bankData = null;
        }
    });

    // Re-render on language switch — the API cards embed translated strings directly in HTML,
    // so i18n.apply()'s data-i18n scan can't refresh them; we redraw from cached bankData.
    $(document).on('oxybank:lang-change', function () {
        if (bankData) renderAllApis();
    });
});

async function loadBankAndApis() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    try {
        bankData = await api.get(`/banks/${bankId}`);
        renderAllApis();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function getBaseUrl() {
    return window.location.origin;
}

// ---- Render ----

function renderAllApis() {
    const bankId = encodeURIComponent(bankData.name);
    const $c = $('#apiCards');
    $c.empty();

    // 0. list_banks API
    $c.append(renderListBanksApi(bankId));

    // 1. Deposit APIs
    $c.append(renderDepositSingleApi(bankId));
    $c.append(renderDepositBatchApi(bankId));

    // 2. Retrieval APIs
    const apis = bankData.retrieval_apis || [];
    apis.forEach(a => {
        $c.append(renderRetrievalApi(bankId, a));
    });

    // Toggle card body
    $c.off('click', '.api-card-header').on('click', '.api-card-header', function () {
        $(this).next('.api-card-body').toggleClass('open');
    });

    // Copy buttons
    $c.off('click', '.copy-btn').on('click', '.copy-btn', function (e) {
        e.stopPropagation();
        const code = $(this).closest('.code-block').find('code').text();
        navigator.clipboard.writeText(code).then(() => {
            $(this).text('✓');
            setTimeout(() => $(this).text('Copy'), 1500);
        });
    });
}

// ---- list_banks API Card ----

function renderListBanksApi(bankId) {
    const bankUrl = `${getBaseUrl()}/api/banks/${bankId}/list_banks`;

    const curlBank = `curl '${bankUrl}' \\
  -H 'Authorization: Bearer <TOKEN>'`;

    const pySnippet = `import requests

resp = requests.get(
    "${bankUrl}",
    headers={"Authorization": "Bearer <TOKEN>"}
)
tools = resp.json()

# Example: find deposit tool
deposit = next(t for t in tools if t["type"] == "deposit")
print(deposit["name"], deposit["endpoint"])
print(deposit["inputSchema"])`;

    return `
    <div class="api-card">
        <div class="api-card-header">
            <div><span class="api-method get">GET</span><h3 style="display:inline;">${i18n.t('apitest.list_banks')} — /api/banks/{bank_name}/list_banks</h3></div>
            <span style="color:var(--gray-400);font-size:12px;">▼</span>
        </div>
        <div class="api-card-body">
            <p style="font-size:13px;color:var(--gray-600);margin-top:12px;">${i18n.t('apitest.list_banks_desc')}</p>

            <div class="api-section">
                <div class="api-section-title">URL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${bankUrl}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Response</div>
                <table class="param-table">
                    <tr><th>Field</th><th>Type</th><th>Description</th></tr>
                    <tr><td>name</td><td>string</td><td>${i18n.t('apitest.tool_name')}</td></tr>
                    <tr><td>endpoint</td><td>string</td><td>${i18n.t('apitest.tool_endpoint')}</td></tr>
                    <tr><td>method</td><td>string</td><td>POST</td></tr>
                    <tr><td>type</td><td>string</td><td>deposit / retrieve</td></tr>
                    <tr><td>description</td><td>string</td><td>${i18n.t('apitest.tool_desc')}</td></tr>
                    <tr><td>inputSchema</td><td>object</td><td>${i18n.t('apitest.tool_schema')}</td></tr>
                    <tr><td>outputFields</td><td>array</td><td>${i18n.t('apitest.tool_output')} (retrieve only)</td></tr>
                </table>
            </div>

            <div class="api-section">
                <div class="api-section-title">cURL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(curlBank)}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Python</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(pySnippet)}</code></div>
            </div>

            <div class="api-section test-panel">
                <div class="api-section-title">${i18n.t('apitest.try_it')}</div>
                <button class="btn btn-primary btn-sm" onclick="testListBanks('${bankId}')">${i18n.t('apitest.send')}</button>
                <div id="listBanksResult" style="margin-top:8px;"></div>
            </div>
        </div>
    </div>`;
}

async function testListBanks(bankId) {
    try {
        OxyBank.showLoading();
        const url = bankId ? `/banks/${bankId}/list_banks` : '/banks/list_banks';
        const res = await api.get(url);
        const items = Array.isArray(res) ? res : [];
        let html = `<p style="font-size:12px;color:var(--gray-500);margin-bottom:8px;">${items.length} tool(s)</p>`;
        html += '<div class="code-block" style="max-height:400px;overflow-y:auto;"><code>' + esc(JSON.stringify(items, null, 2)) + '</code></div>';
        $('#listBanksResult').html(html);
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    } finally {
        OxyBank.hideLoading();
    }
}

// ---- Deposit Single API Card ----

function renderDepositSingleApi(bankId) {
    const url = `${getBaseUrl()}/api/banks/${bankId}/deposit`;
    const schemaFields = (bankData.schema?.fields || []).map(f => f.name);
    const sampleBody = {};
    schemaFields.forEach(f => { sampleBody[f] = `<${f}>`; });

    const curlSnippet = `curl -X POST '${url}' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify(sampleBody, null, 2)}'`;

    const pySnippet = `import requests

resp = requests.post(
    "${url}",
    json=${JSON.stringify(sampleBody, null, 4)}
)
print(resp.json())`;

    const fieldRows = schemaFields.map(f => `<tr><td>${esc(f)}</td><td>any</td><td></td></tr>`).join('');

    return `
    <div class="api-card">
        <div class="api-card-header">
            <div><span class="api-method post">POST</span><h3 style="display:inline;">${i18n.t('apitest.deposit_single')} — /api/banks/{bank_name}/deposit</h3></div>
            <span style="color:var(--gray-400);font-size:12px;">▼</span>
        </div>
        <div class="api-card-body">
            <p style="font-size:13px;color:var(--gray-600);margin-top:12px;">${i18n.t('apitest.deposit_single_desc')}</p>

            <div class="api-section">
                <div class="api-section-title">URL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${url}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Request Body</div>
                <table class="param-table">
                    <tr><th>Field</th><th>Type</th><th>Description</th></tr>
                    ${fieldRows}
                    <tr><td>sys_status</td><td>string</td><td>${i18n.t('apitest.default_val')}: Imported</td></tr>
                    <tr><td>sys_template</td><td>string</td><td>${i18n.t('apitest.default_val')}: ""</td></tr>
                    <tr><td>sys_priority</td><td>int</td><td>${i18n.t('apitest.default_val')}: 0</td></tr>
                </table>
            </div>

            <div class="api-section">
                <div class="api-section-title">cURL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(curlSnippet)}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Python</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(pySnippet)}</code></div>
            </div>

            <div class="api-section test-panel">
                <div class="api-section-title">${i18n.t('apitest.try_it')}</div>
                <div class="form-group">
                    <textarea class="form-control" id="depositSingleTestData" rows="4">${JSON.stringify(sampleBody, null, 2)}</textarea>
                </div>
                <button class="btn btn-primary btn-sm" onclick="testDepositSingle()">${i18n.t('apitest.send')}</button>
                <div id="depositSingleTestResult" style="margin-top:8px;"></div>
            </div>
        </div>
    </div>`;
}

async function testDepositSingle() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    let body;
    try { body = JSON.parse($('#depositSingleTestData').val()); } catch (e) { OxyBank.showToast('Invalid JSON', 'error'); return; }
    try {
        OxyBank.showLoading();
        const res = await api.post(`/banks/${bankId}/deposit`, body);
        $('#depositSingleTestResult').html(`<div class="code-block"><code>${esc(JSON.stringify(res, null, 2))}</code></div>`);
    } catch (e) { OxyBank.showToast(e.message, 'error'); } finally { OxyBank.hideLoading(); }
}

// ---- Deposit Batch API Card ----

function renderDepositBatchApi(bankId) {
    const url = `${getBaseUrl()}/api/banks/${bankId}/deposit_batch`;
    const schemaFields = (bankData.schema?.fields || []).map(f => f.name);
    const sampleBody = {};
    schemaFields.forEach(f => { sampleBody[f] = `<${f}>`; });

    const curlSnippet = `curl -X POST '${url}' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify({ samples: [sampleBody], document_name: "batch_001" }, null, 2)}'`;

    const pySnippet = `import requests

resp = requests.post(
    "${url}",
    json={
        "samples": [${JSON.stringify(sampleBody)}],
        "document_name": "batch_001"
    }
)
print(resp.json())`;

    return `
    <div class="api-card">
        <div class="api-card-header">
            <div><span class="api-method post">POST</span><h3 style="display:inline;">${i18n.t('apitest.deposit_batch')} — /api/banks/{bank_name}/deposit_batch</h3></div>
            <span style="color:var(--gray-400);font-size:12px;">▼</span>
        </div>
        <div class="api-card-body">
            <p style="font-size:13px;color:var(--gray-600);margin-top:12px;">${i18n.t('apitest.deposit_batch_desc')}</p>

            <div class="api-section">
                <div class="api-section-title">URL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${url}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Request Body</div>
                <table class="param-table">
                    <tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr>
                    <tr><td>samples</td><td>array[object]</td><td class="required">*</td><td>${i18n.t('apitest.samples_desc')}</td></tr>
                    <tr><td>document_name</td><td>string</td><td></td><td>${i18n.t('apitest.doc_name_desc')}</td></tr>
                </table>
            </div>

            <div class="api-section">
                <div class="api-section-title">cURL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(curlSnippet)}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Python</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(pySnippet)}</code></div>
            </div>

            <div class="api-section test-panel">
                <div class="api-section-title">${i18n.t('apitest.try_it')}</div>
                <div class="form-group">
                    <textarea class="form-control" id="depositBatchTestData" rows="6">${JSON.stringify([sampleBody], null, 2)}</textarea>
                </div>
                <button class="btn btn-primary btn-sm" onclick="testDepositBatch()">${i18n.t('apitest.send')}</button>
                <div id="depositBatchTestResult" style="margin-top:8px;"></div>
            </div>
        </div>
    </div>`;
}

async function testDepositBatch() {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    let samples;
    try { samples = JSON.parse($('#depositBatchTestData').val()); } catch (e) { OxyBank.showToast('Invalid JSON', 'error'); return; }
    if (!Array.isArray(samples)) samples = [samples];
    try {
        OxyBank.showLoading();
        const res = await api.post(`/banks/${bankId}/deposit_batch`, { samples, document_name: 'api_test' });
        $('#depositBatchTestResult').html(`<div class="code-block"><code>${esc(JSON.stringify(res, null, 2))}</code></div>`);
    } catch (e) { OxyBank.showToast(e.message, 'error'); } finally { OxyBank.hideLoading(); }
}

// ---- Retrieval API Card ----

function renderRetrievalApi(bankId, apiDef) {
    const isDefault = apiDef.is_default || false;
    const url = isDefault
        ? `${getBaseUrl()}/api/banks/${bankId}/withdraw`
        : `${getBaseUrl()}/api/banks/${bankId}/${apiDef.id}/withdraw`;
    const pathDisplay = isDefault
        ? `/api/banks/{bank_name}/withdraw`
        : `/api/banks/{bank_name}/${esc(apiDef.id)}/withdraw`;
    const conditions = apiDef.search_conditions || [];
    const outputFields = apiDef.output_fields || [];
    // For the built-in default retrieval API, render the name via i18n so it follows the
    // active language and doesn't leak the value stored in ES (which is set at bank-creation time).
    const label = isDefault ? i18n.t('apitest.default_retrieval') : apiDef.name;

    const sampleConditions = {};
    conditions.slice(0, 3).forEach(c => { sampleConditions[c.field] = `<value>`; });

    const curlSnippet = `curl -X POST '${url}' \\
  -H 'Authorization: Bearer <TOKEN>' \\
  -H 'Content-Type: application/json' \\
  -d '${JSON.stringify({ conditions: sampleConditions, page_size: 10, page_number: 1 }, null, 2)}'`;

    const pySnippet = `import requests

resp = requests.post(
    "${url}",
    headers={"Authorization": "Bearer <TOKEN>"},
    json={
        "conditions": ${JSON.stringify(sampleConditions)},
        "page_size": 10,
        "page_number": 1
    }
)
print(resp.json())`;

    const cardId = `api_${apiDef.id}`;

    return `
    <div class="api-card">
        <div class="api-card-header">
            <div><span class="api-method post">POST</span><h3 style="display:inline;">${esc(label)} — ${pathDisplay}</h3></div>
            <span style="color:var(--gray-400);font-size:12px;">▼</span>
        </div>
        <div class="api-card-body">
            <p style="font-size:13px;color:var(--gray-600);margin-top:12px;">
                ${isDefault ? i18n.t('apitest.default_desc') : i18n.t('apitest.custom_desc')}
            </p>

            <div class="api-section">
                <div class="api-section-title">URL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${url}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">${i18n.t('apitest.search_conditions')}</div>
                <table class="param-table">
                    <tr><th>Field</th><th>Mode</th><th>Description</th></tr>
                    ${conditions.map(c => `<tr><td>${esc(c.field)}</td><td><span class="badge badge-primary">${i18n.t('mode.' + c.mode)}</span></td><td>${modeDesc(c.mode)}</td></tr>`).join('')}
                    <tr><td>page_size</td><td>-</td><td>${i18n.t('apitest.page_size_desc')}</td></tr>
                    <tr><td>page_number</td><td>-</td><td>${i18n.t('apitest.page_num_desc')}</td></tr>
                </table>
            </div>

            <div class="api-section">
                <div class="api-section-title">${i18n.t('apitest.output_fields')}</div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">
                    ${outputFields.map(f => `<span class="badge badge-primary">${esc(f)}</span>`).join('')}
                </div>
            </div>

            <div class="api-section">
                <div class="api-section-title">cURL</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(curlSnippet)}</code></div>
            </div>

            <div class="api-section">
                <div class="api-section-title">Python</div>
                <div class="code-block"><button class="copy-btn">Copy</button><code>${esc(pySnippet)}</code></div>
            </div>

            <div class="api-section test-panel">
                <div class="api-section-title">${i18n.t('apitest.try_it')}</div>
                <div class="form-group">
                    <label style="font-size:12px;">Conditions (JSON)</label>
                    <textarea class="form-control test-conditions" rows="4" data-api-id="${esc(apiDef.id)}">${JSON.stringify(sampleConditions, null, 2)}</textarea>
                </div>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    <label style="font-size:13px;">page_size: <input type="number" class="form-control test-page-size" value="10" style="width:60px;display:inline-block;"></label>
                    <label style="font-size:13px;">page: <input type="number" class="form-control test-page-num" value="1" min="1" style="width:60px;display:inline-block;"></label>
                    <button class="btn btn-primary btn-sm" onclick="testRetrieval('${esc(apiDef.id)}', this)">${i18n.t('apitest.send')}</button>
                </div>
                <div class="test-result" data-api-id="${esc(apiDef.id)}" style="margin-top:8px;"></div>
            </div>
        </div>
    </div>`;
}

async function testRetrieval(apiId, btn) {
    const bankId = OxyBank.getCurrentBankId();
    if (!bankId) return;
    const $card = $(btn).closest('.api-card-body');
    const condStr = $card.find('.test-conditions').val().trim();
    let conditions = {};
    try { conditions = JSON.parse(condStr || '{}'); } catch (e) { OxyBank.showToast('Invalid JSON', 'error'); return; }
    const pageSize = parseInt($card.find('.test-page-size').val()) || 10;
    const pageNum = parseInt($card.find('.test-page-num').val()) || 1;

    try {
        OxyBank.showLoading();
        const queryUrl = apiId === 'default'
            ? `/banks/${bankId}/withdraw`
            : `/banks/${bankId}/${apiId}/withdraw`;
        const res = await api.post(queryUrl, {
            conditions, page_size: pageSize, page_number: pageNum,
        });
        const $result = $(`.test-result[data-api-id="${apiId}"]`);
        if (res.items && res.items.length) {
            let html = `<p style="font-size:12px;color:var(--gray-500);">Total: ${res.total}, Page ${res.page_number}/${Math.ceil(res.total / res.page_size)}</p>`;
            html += '<div style="overflow-x:auto;"><table>';
            const keys = Object.keys(res.items[0]);
            html += '<thead><tr>' + keys.map(k => `<th>${esc(k)}</th>`).join('') + '</tr></thead><tbody>';
            res.items.forEach(item => {
                html += '<tr>' + keys.map(k => `<td>${esc(String(item[k] || '').substring(0, 80))}</td>`).join('') + '</tr>';
            });
            html += '</tbody></table></div>';
            $result.html(html);
        } else {
            $result.html(`<div class="code-block"><code>${esc(JSON.stringify(res, null, 2))}</code></div>`);
        }
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    } finally {
        OxyBank.hideLoading();
    }
}

// ---- Helpers ----

function modeDesc(mode) {
    const map = {
        vector: 'Vector similarity search',
        exact: 'Exact match (==)',
        in: 'IN match (value is array)',
        fuzzy: 'Fuzzy text match',
    };
    return map[mode] || mode;
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
