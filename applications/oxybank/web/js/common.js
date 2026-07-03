/**
 * common.js — Shared utilities, auth check, nav, toast, sidebar
 */
(function (global) {
    // Auth check
    function checkAuth() {
        const token = localStorage.getItem('oxybank-token');
        const page = window.location.pathname;
        if (!token && !page.includes('login.html')) {
            // Check if auth is disabled by trying a quick API call
            fetch('/api/banks', { method: 'GET' }).then(resp => {
                if (resp.status === 401) {
                    window.location.href = '/login.html';
                }
            }).catch(() => {});
        }
        return true;
    }

    // Toast notifications
    function showToast(msg, type) {
        type = type || 'info';
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.textContent = msg;
        container.appendChild(toast);
        setTimeout(() => { toast.remove(); }, 3500);
    }

    // Modal helpers
    function openModal(selector) {
        $(selector).addClass('active');
    }

    function closeModal(selector) {
        $(selector).removeClass('active');
    }

    // Format an ISO/UTC timestamp for display. Fixed format across the app:
    // "YYYY-MM-DD HH:mm:ss" in the user's local timezone. We roll our own instead
    // of toLocaleString() so all environments (Chrome / Safari / different
    // system locales) render identically — locale-driven formatting has landed
    // us with mixed "2026/7/2 下午4:19" and "7/2/2026, 4:19:56 PM" outputs.
    function formatDate(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return String(dateStr);
        const pad = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} `
             + `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    }

    // Loading overlay
    function showLoading() {
        if (!document.querySelector('.loading-overlay')) {
            const el = document.createElement('div');
            el.className = 'loading-overlay';
            el.innerHTML = '<div class="spinner"></div>';
            document.body.appendChild(el);
        }
    }

    function hideLoading() {
        const el = document.querySelector('.loading-overlay');
        if (el) el.remove();
    }

    // Lang toggle
    function initLangToggle() {
        $('.sidebar-footer-actions').on('click', '.lang-btn', function () {
            const lang = $(this).data('lang');
            i18n.setLang(lang);
            $('.lang-btn').removeClass('active');
            $(this).addClass('active');
        });
        // Highlight current lang
        const currentLang = localStorage.getItem('oxybank-lang') || 'zh';
        $(`.lang-btn[data-lang="${currentLang}"]`).addClass('active');
    }

    // Logout
    function logout() {
        localStorage.removeItem('oxybank-token');
        localStorage.removeItem('oxybank-user');
        // Note: oxybank-current-bank is intentionally kept — it's a UX preference,
        // not an auth secret. The next login (same user or a different one on this
        // browser) inherits the last-selected bank rather than reverting to the
        // list's first item.
        window.location.href = '/login.html';
    }

    // Pagination renderer
    function renderPagination(container, page, totalPages, onChange) {
        const $c = $(container);
        $c.empty();
        if (totalPages <= 1) return;
        $c.append(`<button ${page <= 1 ? 'disabled' : ''} data-page="${page - 1}">${i18n.t('common.prev')}</button>`);
        for (let i = 1; i <= totalPages; i++) {
            if (totalPages > 7 && i > 3 && i < totalPages - 2 && Math.abs(i - page) > 1) {
                if (i === 4 || i === totalPages - 3) $c.append('<span>...</span>');
                continue;
            }
            $c.append(`<button class="${i === page ? 'active' : ''}" data-page="${i}">${i}</button>`);
        }
        $c.append(`<button ${page >= totalPages ? 'disabled' : ''} data-page="${page + 1}">${i18n.t('common.next')}</button>`);
        $c.off('click', 'button').on('click', 'button', function () {
            const p = parseInt($(this).data('page'));
            if (p && p >= 1 && p <= totalPages) onChange(p);
        });
    }

    // ---- Sidebar ----

    function initSidebar(activePage) {
        // Route annotators away from admin-only pages: only annotation and help are allowed.
        const _userInfo = JSON.parse(localStorage.getItem('oxybank-user') || '{}');
        if (_userInfo.role === 'annotator' && activePage !== 'annotation' && activePage !== 'help') {
            window.location.replace('./annotation.html');
            return;
        }

        const sidebarHtml = `
            <div class="logo">
                <span class="logo-text">Oxy<span>Bank</span></span>
                <button class="sidebar-collapse-btn" onclick="OxyBank.toggleSidebar()" title="Toggle sidebar">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 3L5 8L10 13"/></svg>
                </button>
            </div>
            <div class="sidebar-section sidebar-bank-select" style="padding:12px 16px;">
                <select class="form-control sidebar-select" id="globalBankSelect">
                    <option value="">-- ${i18n.t('nav.select_bank')} --</option>
                </select>
            </div>
            <nav>
                <a href="./index.html" data-page="index" data-role="admin"><span class="nav-icon">📦</span><span class="nav-label" data-i18n="nav.banks">${i18n.t('nav.banks')}</span></a>
                <a href="./data.html" data-page="data" data-needs-bank="true" data-role="admin"><span class="nav-icon">📂</span><span class="nav-label" data-i18n="nav.data">${i18n.t('nav.data')}</span></a>
                <a href="./annotation.html" data-page="annotation" data-needs-bank="true"><span class="nav-icon">✏️</span><span class="nav-label" data-i18n="nav.annotation">${i18n.t('nav.annotation')}</span></a>
                <a href="./agents.html" data-page="agents" data-needs-bank="true" data-role="admin"><span class="nav-icon">🤖</span><span class="nav-label" data-i18n="nav.agents">${i18n.t('nav.agents')}</span></a>
                <a href="./retrieval.html" data-page="retrieval" data-needs-bank="true" data-role="admin"><span class="nav-icon">🔌</span><span class="nav-label" data-i18n="nav.retrieval">${i18n.t('nav.retrieval')}</span></a>
                <a href="./templates.html" data-page="templates" data-needs-bank="true" data-role="admin"><span class="nav-icon">📋</span><span class="nav-label" data-i18n="nav.templates">${i18n.t('nav.templates')}</span></a>
                <a href="./users.html" data-page="users" data-role="admin"><span class="nav-icon">👥</span><span class="nav-label" data-i18n="nav.users">${i18n.t('nav.users')}</span></a>
                <a href="./config.html" data-page="config" data-role="admin"><span class="nav-icon">⚙️</span><span class="nav-label" data-i18n="nav.config">${i18n.t('nav.config')}</span></a>
                <a href="./help.html" data-page="help"><span class="nav-icon">❓</span><span class="nav-label" data-i18n="nav.help">${i18n.t('nav.help')}</span></a>
            </nav>
            <div class="sidebar-footer">
                <div class="user-block">
                    <div class="user-avatar"></div>
                    <span class="user-display-name"></span>
                </div>
                <div class="sidebar-footer-actions">
                    <div class="lang-switch">
                        <button data-lang="zh" class="lang-btn">中</button>
                        <button data-lang="en" class="lang-btn">EN</button>
                    </div>
                    <button class="logout-btn" onclick="OxyBank.logout()" title="Logout">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                    </button>
                </div>
                </div>
            </div>`;
        $('.app-sidebar').html(sidebarHtml);

        // Hide admin-only nav for non-admin users
        const userInfo = JSON.parse(localStorage.getItem('oxybank-user') || '{}');
        const userRole = userInfo.role || 'user';
        const displayName = userInfo.display_name || userInfo.username || '';
        $('.user-display-name').text(displayName);
        $('.user-avatar').text(displayName ? displayName.charAt(0).toUpperCase() : '?');
        if (userRole !== 'admin') {
            $('.app-sidebar nav a[data-role="admin"]').hide();
        }

        // Highlight active page
        $(`.app-sidebar nav a[data-page="${activePage}"]`).addClass('active');

        // Set tooltip for collapsed mode
        $('.app-sidebar nav a').each(function () {
            $(this).attr('data-tooltip', $(this).find('.nav-label').text());
        });

        // Intercept clicks on pages that need a bank
        $('.app-sidebar nav a[data-needs-bank]').on('click', function (e) {
            if (!localStorage.getItem("oxybank-current-bank")) {
                e.preventDefault();
                showToast(i18n.t('nav.select_bank_first'), 'error');
            }
        });

        // Load banks into selector. Upgrade the native select to its custom-select
        // sibling first so the sidebar's final layout is committed synchronously —
        // otherwise loadBankSelector()'s async fetch delays the upgrade, and when the
        // custom-select div finally mounts it pushes the nav items down. Since the
        // <select> already carries a placeholder <option>, the upgraded trigger
        // renders as "-- Select Bank --" and the fetch just patches in real options.
        _upgradeBankSelect($('#globalBankSelect'));
        loadBankSelector();

        // Bank change handler
        $('#globalBankSelect').on('change', function () {
            const bankId = $(this).val();
            if (bankId) {
                localStorage.setItem("oxybank-current-bank", bankId);
            } else {
                localStorage.removeItem("oxybank-current-bank");
            }
            $(document).trigger('oxybank:bank-change', [bankId]);
        });

        // Init lang toggle and apply i18n
        initLangToggle();
        i18n.apply();

        // Restore collapsed state instantly (no animation on page load)
        if (localStorage.getItem('oxybank-sidebar-collapsed') === '1') {
            $('body').addClass('no-transition sidebar-collapsed');
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    $('body').removeClass('no-transition');
                });
            });
        }

        // Upgrade native selects to custom dropdowns
        setTimeout(() => upgradeSelects(), 50);

        // Reveal sidebar content
        requestAnimationFrame(() => $('.app-sidebar').addClass('ready'));
    }

    function toggleSidebar() {
        $('body').toggleClass('sidebar-collapsed');
        const collapsed = $('body').hasClass('sidebar-collapsed');
        localStorage.setItem('oxybank-sidebar-collapsed', collapsed ? '1' : '0');
    }

    async function loadBankSelector() {
        try {
            const token = localStorage.getItem('oxybank-token');
            const fetchHeaders = {};
            if (token) fetchHeaders['Authorization'] = 'Bearer ' + token;
            const resp = await fetch('/api/banks', { headers: fetchHeaders });
            if (!resp.ok) return;
            const data = await resp.json();
            const banks = data.items || data;
            const $sel = $('#globalBankSelect');
            let saved = localStorage.getItem("oxybank-current-bank");

            // Clear stale UUID-style values from before bank_name migration
            if (saved && /^[0-9a-f]{8}-/.test(saved)) {
                localStorage.removeItem("oxybank-current-bank");
                saved = null;
            }

            const bankNames = new Set();
            banks.forEach(b => {
                bankNames.add(b.name);
                $sel.append(`<option value="${b.name}">${b.name}</option>`);
            });

            // If saved bank no longer exists, clear it
            if (saved && !bankNames.has(saved)) {
                localStorage.removeItem("oxybank-current-bank");
                saved = null;
            }

            // Explicitly set the underlying <select>'s value to the remembered bank.
            // We previously relied on adding the `selected` attribute via appended HTML,
            // but the placeholder <option value=""> is already in the DOM as the first
            // option — some browsers keep it selected even after appending others with
            // the selected attribute. Setting .val() explicitly forces the correct
            // choice, which then propagates through rebuild() into the custom-select UI.
            if (saved) {
                $sel.val(saved);
            }

            const currentVal = $sel.val();
            if (currentVal) {
                localStorage.setItem("oxybank-current-bank", currentVal);
                $(document).trigger('oxybank:bank-change', [currentVal]);
            }

            // The custom-select wrapper was already mounted synchronously by
            // initSidebar (see call to _upgradeBankSelect there). Now that the
            // native <select> has real <option>s, ask the wrapper to re-render
            // its .cs-option list. If the upgrade somehow didn't happen (e.g.
            // this function is called from a page without initSidebar), fall
            // back to running the full upgrade.
            const rebuild = $sel.data('cs-rebuild');
            if (rebuild) rebuild();
            else _upgradeBankSelect($sel);
        } catch (e) {}
    }

    function _upgradeBankSelect($sel) {
        if ($sel.data('cs-done')) return;
        $sel.data('cs-done', true).hide();
        const $wrap = $('<div class="custom-select sidebar-select-wrapper"></div>');
        const $trigger = $(`<div class="custom-select-trigger">
            <span class="cs-text cs-placeholder"></span>
            <svg class="cs-arrow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6l4 4 4-4"/></svg>
        </div>`);
        const $dropdown = $('<div class="custom-select-dropdown"></div>');

        function rebuild() {
            $dropdown.empty();
            if ($sel.find('option').length > 6) {
                $dropdown.append('<div class="cs-search"><input type="text" placeholder="Search..."></div>');
            }
            let selText = '';
            $sel.find('option').each(function () {
                const v = $(this).val(), t = $(this).text(), s = $(this).is(':selected');
                $dropdown.append(`<div class="cs-option ${s ? 'selected' : ''}" data-value="${v}">${t}</div>`);
                if (s && v) selText = t;
            });
            $trigger.find('.cs-text').text(selText || $sel.find('option:first').text());
            if (!selText) $trigger.find('.cs-text').addClass('cs-placeholder');
            else $trigger.find('.cs-text').removeClass('cs-placeholder');
        }
        rebuild();
        // Expose rebuild so loadBankSelector can refresh the dropdown after fetching
        // banks — this way the trigger DOM is mounted immediately (no jump), and we
        // only patch in the options once they arrive.
        $sel.data('cs-rebuild', rebuild);

        $wrap.append($trigger).append($dropdown);
        $sel.after($wrap);

        $trigger.on('click', function (e) {
            e.stopPropagation();
            $('.custom-select-dropdown.open').not($dropdown).removeClass('open');
            $('.custom-select-trigger.open').not($trigger).removeClass('open');
            $trigger.toggleClass('open');
            $dropdown.toggleClass('open');
            if ($dropdown.hasClass('open')) $dropdown.find('.cs-search input').focus();
        });

        $dropdown.on('click', '.cs-option', function () {
            const val = $(this).data('value');
            $sel.val(val).trigger('change');
            $dropdown.find('.cs-option').removeClass('selected');
            $(this).addClass('selected');
            $trigger.find('.cs-text').text($(this).text()).removeClass('cs-placeholder');
            if (!val) $trigger.find('.cs-text').addClass('cs-placeholder');
            $trigger.removeClass('open');
            $dropdown.removeClass('open');
        });

        $dropdown.on('input', '.cs-search input', function () {
            const q = $(this).val().toLowerCase();
            $dropdown.find('.cs-option').each(function () {
                $(this).toggle($(this).text().toLowerCase().includes(q));
            });
        });
    }

    function getCurrentBankId() {
        const name = localStorage.getItem("oxybank-current-bank") || $('#globalBankSelect').val();
        if (!name) {
            showToast(i18n.t('nav.select_bank_first'), 'error');
            return null;
        }
        return encodeURIComponent(name);
    }

    // ---- Custom Select Component ----
    function upgradeSelects() {
        $('select.form-control').not('.cs-upgraded').not('.sidebar-select').not('#globalBankSelect').each(function () {
            const $sel = $(this);
            $sel.addClass('cs-upgraded').hide();
            const isDark = $sel.closest('.app-sidebar').length > 0;
            const inFieldRow = $sel.closest('.schema-field-row').length > 0;
            const hasInlineMaxWidth = ($sel.attr('style') || '').includes('max-width');
            let wrapCls = isDark ? 'custom-select sidebar-select-wrapper' : 'custom-select';
            if (inFieldRow && !hasInlineMaxWidth) wrapCls += ' cs-flex';
            const $wrap = $(`<div class="${wrapCls}"></div>`);
            const $trigger = $(`<div class="custom-select-trigger">
                <span class="cs-text cs-placeholder"></span>
                <svg class="cs-arrow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6l4 4 4-4"/></svg>
            </div>`);
            const $dropdown = $('<div class="custom-select-dropdown"></div>');

            const options = [];
            $sel.find('option').each(function () {
                options.push({ value: $(this).val(), text: $(this).text(), selected: $(this).is(':selected') });
            });

            if (options.length > 8) {
                $dropdown.append('<div class="cs-search"><input type="text" placeholder="Search..."></div>');
            }

            let selectedText = '';
            options.forEach(opt => {
                const cls = opt.selected ? 'cs-option selected' : 'cs-option';
                $dropdown.append(`<div class="${cls}" data-value="${opt.value}">${opt.text}</div>`);
                if (opt.selected && opt.value) selectedText = opt.text;
            });

            const placeholder = options.length ? options[0].text : '';
            $trigger.find('.cs-text').text(selectedText || placeholder);
            if (!selectedText) $trigger.find('.cs-text').addClass('cs-placeholder');
            else $trigger.find('.cs-text').removeClass('cs-placeholder');

            $wrap.append($trigger).append($dropdown);
            $sel.after($wrap);

            $trigger.on('click', function (e) {
                e.stopPropagation();
                $('.custom-select-dropdown.open').not($dropdown).removeClass('open');
                $('.custom-select-trigger.open').not($trigger).removeClass('open');
                $trigger.toggleClass('open');
                $dropdown.toggleClass('open');
                if ($dropdown.hasClass('open')) {
                    $dropdown.find('.cs-search input').focus();
                }
            });

            $dropdown.on('click', '.cs-option', function () {
                const val = $(this).data('value');
                const text = $(this).text();
                $sel.val(val).trigger('change');
                $dropdown.find('.cs-option').removeClass('selected');
                $(this).addClass('selected');
                $trigger.find('.cs-text').text(text).removeClass('cs-placeholder');
                $trigger.removeClass('open');
                $dropdown.removeClass('open');
            });

            $dropdown.on('input', '.cs-search input', function () {
                const q = $(this).val().toLowerCase();
                $dropdown.find('.cs-option').each(function () {
                    $(this).toggle($(this).text().toLowerCase().includes(q));
                });
            });
        });
    }

    $(document).on('click', function () {
        $('.custom-select-dropdown.open').removeClass('open');
        $('.custom-select-trigger.open').removeClass('open');
    });

    // Init on document ready
    $(function () {
        checkAuth();
    });

    global.OxyBank = {
        checkAuth, showToast, openModal, closeModal, formatDate,
        showLoading, hideLoading, logout, renderPagination,
        initSidebar, getCurrentBankId, loadBankSelector, toggleSidebar,
        upgradeSelects,
    };
})(window);
