const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', async () => {
    await verifyAdmin();
    await Promise.all([loadOverview(), loadShops(), loadUsers()]);
});

async function verifyAdmin() {
    try {
        const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
        if (!res.ok) {
            window.location.href = 'login.html';
            return;
        }
        const data = await res.json();
        if (!data.authenticated || data.user.role !== 'admin') {
            window.location.href = 'login.html';
        }
    } catch (e) {
        console.warn('Session verification error:', e);
    }
}

async function loadOverview() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/overview`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.overview) {
            const o = data.overview;
            const rev = document.getElementById('stat-turnover');
            if (rev) rev.innerText = `₹${o.total_turnover.toFixed(2)}`;

            const ord = document.getElementById('stat-orders');
            if (ord) ord.innerText = `${o.total_orders} (${o.completed_orders} Done)`;

            const shp = document.getElementById('stat-shops');
            if (shp) shp.innerText = o.active_shops;

            const usr = document.getElementById('stat-users');
            if (usr) usr.innerText = o.total_users;
        }

        if (data.success && data.recent_orders) {
            const tbody = document.getElementById('orders-table-body');
            if (tbody) {
                tbody.innerHTML = '';
                if (data.recent_orders.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-400">No recent orders yet.</td></tr>';
                } else {
                    data.recent_orders.forEach(order => {
                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-slate-50 transition-colors';
                        tr.innerHTML = `
                            <td class="p-3 font-bold text-blue-900">#${order.order_reference}</td>
                            <td class="p-3 font-medium text-slate-800">${order.customer_name || 'Customer'}</td>
                            <td class="p-3 font-semibold text-purple-700">${order.shop_name}</td>
                            <td class="p-3 font-bold text-slate-900">₹${parseFloat(order.total_amount).toFixed(2)}</td>
                            <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${order.order_status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'} uppercase">${order.order_status}</span></td>
                            <td class="p-3 text-slate-400">${order.created_at || 'Recent'}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            }
        }
    } catch (e) {
        console.error('Overview fetch error:', e);
    }
}

async function loadShops() {
    const tbody = document.getElementById('shops-table-body');
    const countEl = document.getElementById('shops-count');
    if (!tbody) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.shops) {
            if (countEl) countEl.innerText = `${data.shops.length} Stalls Registered`;
            tbody.innerHTML = '';

            data.shops.forEach(shop => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-50 transition-colors';
                tr.innerHTML = `
                    <td class="p-3 font-bold text-slate-800">${shop.name}</td>
                    <td class="p-3 text-slate-500">${shop.category || 'General'}</td>
                    <td class="p-3 font-semibold text-slate-700">${shop.total_items} Dishes</td>
                    <td class="p-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${shop.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-700'}">
                            ${shop.is_active ? 'Active' : 'Disabled'}
                        </span>
                    </td>
                    <td class="p-3 text-right">
                        <button onclick="toggleShopStatus(${shop.id})" class="px-3 py-1 rounded-lg text-xs font-bold ${shop.is_active ? 'bg-red-50 text-red-600 hover:bg-red-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'} transition-colors">
                            ${shop.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error('Shops fetch error:', e);
    }
}

async function toggleShopStatus(shopId) {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops/${shopId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        const data = await res.json();
        if (data.success) {
            await loadShops();
            await loadOverview();
        }
    } catch (e) {
        alert('Failed to update shop status.');
    }
}

async function loadUsers() {
    const tbody = document.getElementById('users-table-body');
    const countEl = document.getElementById('users-count');
    if (!tbody) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/users`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.users) {
            if (countEl) countEl.innerText = `${data.users.length} Users Listed`;
            tbody.innerHTML = '';

            data.users.forEach(user => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-50 transition-colors';
                tr.innerHTML = `
                    <td class="p-3 font-bold text-slate-800">${user.email}</td>
                    <td class="p-3 text-slate-500">${user.full_name || user.shop_name || '-'} ${user.identifier ? '(' + user.identifier + ')' : ''}</td>
                    <td class="p-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${user.role === 'admin' ? 'bg-purple-100 text-purple-800' : (user.role === 'vendor' ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-700')} uppercase">
                            ${user.role}
                        </span>
                    </td>
                    <td class="p-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${user.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-700'}">
                            ${user.is_active ? 'Active' : 'Suspended'}
                        </span>
                    </td>
                    <td class="p-3 text-right">
                        ${user.role !== 'admin' ? `
                            <button onclick="toggleUserStatus(${user.id})" class="px-3 py-1 rounded-lg text-xs font-bold ${user.is_active ? 'bg-slate-100 hover:bg-slate-200 text-slate-600' : 'bg-emerald-50 text-emerald-700'} transition-colors">
                                ${user.is_active ? 'Suspend' : 'Activate'}
                            </button>
                        ` : '<span class="text-slate-300 text-[10px]">Superuser</span>'}
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error('Users fetch error:', e);
    }
}

async function toggleUserStatus(userId) {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        const data = await res.json();
        if (data.success) {
            await loadUsers();
            await loadOverview();
        }
    } catch (e) {
        alert('Failed to update user status.');
    }
}

function toggleShopModal(show) {
    const modal = document.getElementById('add-shop-modal');
    if (modal) {
        if (show) modal.classList.remove('hidden');
        else {
            modal.classList.add('hidden');
            const form = document.getElementById('add-shop-form');
            if (form) form.reset();
        }
    }
}

async function handleAddShop(event) {
    event.preventDefault();
    const name = document.getElementById('stall-name').value.trim();
    const category = document.getElementById('stall-category').value.trim();
    const description = document.getElementById('stall-description').value.trim();

    if (!name) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ name, category, description })
        });
        const data = await res.json();
        if (data.success) {
            toggleShopModal(false);
            await loadShops();
            await loadOverview();
        } else {
            alert(data.message || 'Failed to add stall.');
        }
    } catch (e) {
        alert('Connection error while adding stall.');
    }
}

async function logoutAdmin() {
    try {
        await fetch(`${API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
        sessionStorage.clear();
        window.location.href = 'login.html';
    } catch (e) {
        window.location.href = 'login.html';
    }
}
