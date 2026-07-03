/**
 * users.js — User management page
 */
let users = [];

$(function () {
    loadUsers();
});

async function loadUsers() {
    try {
        const data = await api.get('/users');
        users = Array.isArray(data) ? data : (data.items || []);
        renderUsers();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function renderUsers() {
    const $tbody = $('#userTable tbody');
    $tbody.empty();
    if (!users.length) {
        $tbody.append(`<tr><td colspan="5" style="text-align:center;color:var(--gray-400);">${i18n.t('common.empty')}</td></tr>`);
        return;
    }
    users.forEach(u => {
        const isAdmin = u.username === 'admin';
        const roleBadge = u.role === 'admin'
            ? '<span class="badge badge-warning">Admin</span>'
            : '<span class="badge badge-primary">Annotator</span>';
        $tbody.append(`
            <tr>
                <td style="font-family:monospace;">${esc(u.username)}</td>
                <td>${esc(u.display_name || '')}</td>
                <td>${roleBadge}</td>
                <td>${OxyBank.formatDate(u.created_at)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="editUser('${u.id}')">${i18n.t('common.edit')}</button>
                    ${isAdmin ? '' : `<button class="btn btn-sm btn-danger" onclick="deleteUser('${u.id}', '${esc(u.username)}')">${i18n.t('common.delete')}</button>`}
                </td>
            </tr>`);
    });
}

function openAddUser() {
    $('#editUserId').val('');
    $('#userUsername').val('').prop('readonly', false);
    $('#userPassword').val('');
    $('#userDisplayName').val('');
    $('#userRole').val('annotator');
    $('#passwordHint').hide();
    $('#userModalTitle').text(i18n.t('users.add'));
    OxyBank.openModal('#userModal');
}

function editUser(id) {
    const u = users.find(x => x.id === id);
    if (!u) return;
    $('#editUserId').val(id);
    $('#userUsername').val(u.username).prop('readonly', true);
    $('#userPassword').val('');
    $('#userDisplayName').val(u.display_name || '');
    $('#userRole').val(u.role || 'annotator');
    $('#passwordHint').show();
    $('#userModalTitle').text(i18n.t('common.edit'));
    OxyBank.openModal('#userModal');
}

async function submitUser() {
    const editId = $('#editUserId').val();
    const username = $('#userUsername').val().trim();
    const password = $('#userPassword').val();
    const display_name = $('#userDisplayName').val().trim();
    const role = $('#userRole').val();

    if (!username) { OxyBank.showToast(i18n.t('users.username_required'), 'error'); return; }
    if (!editId && !password) { OxyBank.showToast(i18n.t('users.password_required'), 'error'); return; }

    try {
        if (editId) {
            const payload = { display_name, role };
            if (password) payload.password = password;
            await api.put(`/users/${editId}`, payload);
        } else {
            await api.post('/users', { username, password, display_name: display_name || username, role });
        }
        OxyBank.closeModal('#userModal');
        OxyBank.showToast(i18n.t('common.save') + ' OK', 'success');
        loadUsers();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

async function deleteUser(id, username) {
    if (!confirm(i18n.t('users.confirm_delete').replace('{name}', username))) return;
    try {
        await api.del(`/users/${id}`);
        OxyBank.showToast('Deleted', 'success');
        loadUsers();
    } catch (e) {
        OxyBank.showToast(e.message, 'error');
    }
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
