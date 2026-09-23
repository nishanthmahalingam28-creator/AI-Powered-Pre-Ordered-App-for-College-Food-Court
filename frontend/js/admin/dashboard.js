const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

let cachedShops = [];
let cachedCustomers = [];
let cachedVendors = [];
let cachedAdminCount = 0;
let cachedCustomerCount = null;
const loadedAdminTabs = new Set(['shops']);
let cachedTemporaryAccounts = [];
let adminOrdersRequestController = null;
let adminOrdersRequestSequence = 0;
let adminPaymentsRequestController = null;
let adminPaymentsRequestSequence = 0;
let adminContactRequestController = null;
let adminContactRequestSequence = 0;

document.addEventListener('DOMContentLoaded', async () => {
    const isAdmin = await verifyAdmin();
    if (!isAdmin) return;
    await Promise.all([loadOverview(), loadShops()]);
    document.getElementById('contact-report-status')?.addEventListener('change', loadContactReports);
    let contactSearchTimer;
    document.getElementById('contact-report-search')?.addEventListener('input', function(){ clearTimeout(contactSearchTimer); contactSearchTimer=setTimeout(loadContactReports,400); });
});

async function verifyAdmin() {
    try {
        const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
        if (!res.ok) {
            window.location.href = 'login.html';
            return false;
        }
        const data = await res.json();
        if (!data.authenticated || data.user.role !== 'admin') {
            window.location.href = 'login.html';
            return false;
        }
        return true;
    } catch (e) {
        console.warn('Session verification error:', e);
        window.location.href = 'login.html';
        return false;
    }
}

function switchTab(tabId) {
    const tabs = ['shops', 'vendors', 'customers', 'temporary', 'orders', 'payments', 'audit', 'contacts'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-btn-${t}`);
        const sec = document.getElementById(`section-${t}`);
        if (t === tabId) {
            if (btn) btn.className = 'px-4 py-3 border-b-2 border-purple-600 text-purple-700 flex items-center gap-2 whitespace-nowrap font-bold';
            if (sec) sec.classList.remove('hidden');
        } else {
            if (btn) btn.className = 'px-4 py-3 border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 whitespace-nowrap font-bold';
            if (sec) sec.classList.add('hidden');
        }
    });

    if (!loadedAdminTabs.has(tabId)) {
        loadedAdminTabs.add(tabId);
        if (tabId === 'shops') loadShops();
        else if (tabId === 'vendors') loadVendors();
        else if (tabId === 'customers') loadCustomers();
        else if (tabId === 'temporary') loadTemporaryAccounts();
        else if (tabId === 'orders') loadGlobalOrders();
        else if (tabId === 'payments') loadPayments();
        else if (tabId === 'audit') loadAuditLogs();
        else if (tabId === 'contacts') loadContactReports();
    }
}

function updateAdminCardsFromCache() {
    const activeShops = cachedShops.filter(s => Number(s.is_active) === 1);
    const openShops = activeShops.filter(s => String(s.operational_status || "").toUpperCase() === "OPEN");
    const closedShops = activeShops.filter(s => String(s.operational_status || "").toUpperCase() === "CLOSED");
    const unavailableShops = activeShops.filter(s => String(s.operational_status || "").toUpperCase() === "TEMPORARILY_UNAVAILABLE");

    const shopEl = document.getElementById("stat-shops");
    if (shopEl) shopEl.innerText = `${activeShops.length} Active Stalls`;
    const shopOp = document.getElementById("stat-shops-op");
    if (shopOp) shopOp.innerText = `${openShops.length} Open · ${closedShops.length} Closed · ${unavailableShops.length} Unavail`;

    const vendorCount = cachedVendors.length;
    const usersEl = document.getElementById("stat-users-breakdown");
    if (usersEl) {
        const customerCount = cachedCustomerCount === null ? ((usersEl.innerText.match(/(\\d+) Cust/) || [null, 0])[1]) : cachedCustomerCount;
        usersEl.innerText = `${customerCount} Cust · ${vendorCount} Vendors · ${cachedAdminCount} Admins`;
    }
    const vendorsEl = document.getElementById("stat-vendors");
    if (vendorsEl) vendorsEl.innerText = vendorCount;
}

async function loadOverview() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/overview`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.overview) {
            const o = data.overview;
            cachedAdminCount = Number(o.total_admins || 0);
            const revEl = document.getElementById('stat-turnover');
            if (revEl) revEl.innerText = `₹${o.total_turnover.toFixed(2)}`;

            const colEl = document.getElementById('stat-collected-note');
            if (colEl && o.payments) colEl.innerText = `₹${o.payments.total_collected.toFixed(2)} settled online`;

            const ordEl = document.getElementById('stat-orders');
            if (ordEl) ordEl.innerText = o.total_orders;

            const ordBk = document.getElementById('stat-orders-breakdown');
            if (ordBk) ordBk.innerText = `${o.active_orders} active · ${o.completed_orders} done · ${o.cancelled_orders} cancelled`;

            const shpEl = document.getElementById('stat-shops');
            if (shpEl) shpEl.innerText = `${o.active_shops} Active Stalls`;

            const shpOp = document.getElementById('stat-shops-op');
            if (shpOp) shpOp.innerText = `${o.open_shops} Open · ${o.closed_shops} Closed · ${o.unavailable_shops} Unavail`;

            const usrEl = document.getElementById('stat-users');
            if (usrEl) usrEl.innerText = o.total_users;

            const usrBk = document.getElementById('stat-users-breakdown');
            if (usrBk) usrBk.innerText = `${o.total_customers} Cust · ${o.total_vendors} Vendors · ${o.total_admins} Admins`;
        }
    } catch (e) {
        console.error('Overview fetch error:', e);
    }
}

// ============================================================================
// STALLS & OPERATIONS
// ============================================================================

async function loadShops() {
    const tbody = document.getElementById('shops-table-body');
    if (!tbody) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops`, { credentials: 'include' });
        const data = await res.json();
        if (data.success && data.shops) {
            cachedShops = data.shops;
            loadedAdminTabs.add('shops');
            renderShops(cachedShops);
            updateAdminCardsFromCache();
        }
    } catch (e) {
        console.error('Shops fetch error:', e);
    }
}

function renderShops(shops) {
    const tbody = document.getElementById('shops-table-body');
    const countEl = document.getElementById('shops-count');
    if (!tbody) return;
    if (countEl) countEl.innerText = `${shops.length} Stalls Listed`;
    tbody.innerHTML = '';

    shops.forEach(shop => {
        const tr = document.createElement('tr');
        tr.dataset.shopId = shop.id;
        tr.className = 'hover:bg-slate-50 transition-colors';
        let opBadgeClass = 'bg-emerald-100 text-emerald-800';
        if (shop.operational_status === 'CLOSED') opBadgeClass = 'bg-rose-100 text-rose-800';
        else if (shop.operational_status === 'TEMPORARILY_UNAVAILABLE') opBadgeClass = 'bg-amber-100 text-amber-800';

        tr.innerHTML = `
            <td class="p-3"><span class="font-bold text-slate-800 block">${shop.name}</span><span class="text-[10px] text-slate-400 font-mono">${shop.slug}</span></td>
            <td class="p-3 text-slate-500">${shop.category || 'General'}</td>
            <td class="p-3 font-medium text-slate-700">${shop.owner_email ? `<span class="text-blue-700 font-semibold">${shop.owner_email}</span>` : '<span class="text-slate-400 italic">Unassigned</span>'}</td>
            <td class="p-3 font-semibold text-slate-700">${shop.total_items || 0} Dishes</td>
            <td class="p-3"><div class="flex items-center gap-1.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold ${opBadgeClass} uppercase">${String(shop.operational_status || 'OPEN').replace('_', ' ')}</span><select onchange="setOperationalStatus(${shop.id}, this.value)" class="text-[10px] border border-slate-200 rounded-lg p-0.5 bg-white text-slate-700 font-medium"><option value="">Change...</option><option value="OPEN" ${shop.operational_status === 'OPEN' ? 'disabled' : ''}>OPEN</option><option value="TEMPORARILY_UNAVAILABLE" ${shop.operational_status === 'TEMPORARILY_UNAVAILABLE' ? 'disabled' : ''}>TEMPORARILY_UNAVAILABLE</option><option value="CLOSED" ${shop.operational_status === 'CLOSED' ? 'disabled' : ''}>CLOSED</option></select></div></td>
            <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${Number(shop.is_active) ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}">${Number(shop.is_active) ? 'Active' : 'Deactivated'}</span></td>
            <td class="p-3 text-right"><button onclick="toggleShopStatus(${shop.id})" class="px-3 py-1 rounded-lg text-xs font-bold ${Number(shop.is_active) ? 'bg-red-50 text-red-600 hover:bg-red-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'} transition-colors">${Number(shop.is_active) ? 'Deactivate' : 'Activate'}</button><button onclick="deleteShop(${shop.id}, '${String(shop.name).replace(/'/g,"\\'")}')" class="ml-1 px-3 py-1 rounded-lg text-xs font-bold bg-rose-600 text-white hover:bg-rose-700 transition-colors">Delete</button></td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteShop(shopId, shopName) {
    if (!confirm(`Delete stall "${shopName}" permanently? Stalls with order history cannot be deleted.`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops/${shopId}`, { method: 'DELETE', credentials: 'include' });
        const data = await res.json();
        if (data.success) {
            cachedShops = cachedShops.filter(s => Number(s.id) !== Number(shopId));
            renderShops(cachedShops);
            updateAdminCardsFromCache();
        } else alert(data.message || 'Failed to delete stall.');
    } catch (e) { alert('Failed to connect to server while deleting stall.'); }
}

async function setOperationalStatus(shopId, status) {
    if (!status) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops/${shopId}/operational-status`, { method: 'PUT', headers: {'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({operational_status:status}) });
        const data = await res.json();
        if (data.success) {
            const shop = cachedShops.find(s => Number(s.id) === Number(shopId));
            if (shop) shop.operational_status = data.operational_status || status;
            renderShops(cachedShops);
            updateAdminCardsFromCache();
        } else alert(data.message || 'Failed to update operational status.');
    } catch (e) { alert('Failed to connect to server.'); }
}

async function toggleShopStatus(shopId) {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops/${shopId}/status`, {method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include'});
        const data = await res.json();
        if (data.success) {
            const shop = cachedShops.find(s => Number(s.id) === Number(shopId));
            if (shop) shop.is_active = Number(data.is_active);
            renderShops(cachedShops);
            updateAdminCardsFromCache();
        }
    } catch (e) { alert('Failed to update shop status.'); }
}

// ============================================================================
// VENDOR MANAGEMENT & ASSIGNMENTS

// ============================================================================
// VENDOR MANAGEMENT & ASSIGNMENTS
// ============================================================================

async function loadVendors() {
    const tbody = document.getElementById('vendors-table-body');
    if (!tbody) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/vendors`, { credentials: 'include' });
        const data = await res.json();
        if (data.success && data.vendors) {
            loadedAdminTabs.add('vendors');
            cachedVendors = data.vendors;
            renderVendors(cachedVendors);
            updateAdminCardsFromCache();
        }
    } catch (e) { console.error('Vendors fetch error:', e); }
}

function renderVendors(vendors) {
    const tbody = document.getElementById('vendors-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    vendors.forEach(v => {
        const tr = document.createElement('tr');
        tr.dataset.vendorId = v.id;
        tr.className = 'hover:bg-slate-50 transition-colors';
        tr.innerHTML = `
            <td class="p-3 font-bold text-slate-800">${v.email}</td>
            <td class="p-3 font-semibold ${v.assigned_shop_name ? 'text-purple-700' : 'text-slate-400 italic'}">${v.assigned_shop_name || 'Not Assigned'}</td>
            <td class="p-3">${v.assigned_shop_status ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${v.assigned_shop_status === 'OPEN' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">${v.assigned_shop_status}</span>` : '<span class="text-slate-400 text-[10px]">—</span>'}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${v.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}">${v.is_active ? 'Active' : 'Suspended'}</span></td>
            <td class="p-3 text-slate-400">${v.created_at ? v.created_at.split(' ')[0] : '—'}</td>
            <td class="p-3 text-right"><button onclick="openAssignModal(${v.id}, '${v.email}', ${v.assigned_shop_id || 'null'})" class="bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs px-3 py-1 rounded-lg transition-colors">Assign Stall</button><button onclick="deleteVendor(${v.id}, '${v.email}')" class="ml-1 bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold text-xs px-3 py-1 rounded-lg transition-colors">Delete</button></td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteVendor(vendorId, vendorEmail) {
    if (!confirm(`Delete vendor account "${vendorEmail}" permanently? Any assigned stall will become unassigned.`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/vendors/${vendorId}`, {method:'DELETE',credentials:'include'});
        const data = await res.json();
        if (data.success) {
            cachedVendors = cachedVendors.filter(v => Number(v.id) !== Number(vendorId));
            if (data.unassigned_shop_id) {
                const shop = cachedShops.find(s => Number(s.id) === Number(data.unassigned_shop_id));
                if (shop) { shop.owner_user_id = null; shop.owner_email = null; }
                renderShops(cachedShops);
            }
            renderVendors(cachedVendors);
            updateAdminCardsFromCache();
        } else alert(data.message || 'Failed to delete vendor.');
    } catch (e) { alert('Failed to connect to server while deleting vendor.'); }
}

function openAssignModal(vendorId, vendorEmail, currentShopId) {
    const modal = document.getElementById('assign-vendor-modal');
    const idInput = document.getElementById('assign-vendor-id');
    const emailEl = document.getElementById('assign-vendor-email');
    const select = document.getElementById('assign-shop-select');
    if (!modal || !select) return;
    idInput.value = vendorId;
    emailEl.innerText = vendorEmail;
    select.innerHTML = '<option value="">-- Unassign from all stalls --</option>';
    cachedShops.forEach(s => {
        if (Number(s.is_active)) {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.innerText = `${s.name} (${s.category || 'Food'})`;
            if (currentShopId && Number(s.id) === Number(currentShopId)) opt.selected = true;
            select.appendChild(opt);
        }
    });
    toggleAssignModal(true);
}

function toggleAssignModal(show) {
    const modal = document.getElementById('assign-vendor-modal');
    if (modal) show ? modal.classList.remove('hidden') : modal.classList.add('hidden');
}

async function handleAssignVendor(event) {
    event.preventDefault();
    const vendorId = document.getElementById('assign-vendor-id').value;
    const shopId = document.getElementById('assign-shop-select').value || null;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/vendors/${vendorId}/shop`, {method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({shop_id:shopId})});
        const data = await res.json();
        if (data.success) {
            toggleAssignModal(false);
            const vendor = cachedVendors.find(v => Number(v.id) === Number(vendorId));
            if (vendor) {
                vendor.assigned_shop_id = data.shop_id;
                vendor.assigned_shop_name = data.shop_name || null;
                vendor.assigned_shop_status = data.assigned_shop_status || null;
            }
            cachedShops.forEach(s => { if (Number(s.owner_user_id) === Number(vendorId)) { s.owner_user_id = null; s.owner_email = null; } });
            if (data.shop_id) {
                const shop = cachedShops.find(s => Number(s.id) === Number(data.shop_id));
                if (shop) { shop.owner_user_id = Number(vendorId); shop.owner_email = vendor?.email || ''; }
            }
            renderVendors(cachedVendors);
            renderShops(cachedShops);
        } else alert(data.message || 'Failed to assign vendor.');
    } catch (e) { alert('Failed to connect to server.'); }
}

// ============================================================================
// CUSTOMER MANAGEMENT

// ============================================================================
// CUSTOMER MANAGEMENT
// ============================================================================

async function loadCustomers() {
    const tbody = document.getElementById('customers-table-body');
    if (!tbody) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/customers`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.customers) {
            loadedAdminTabs.add('customers');
            cachedCustomers = data.customers;
            cachedCustomerCount = cachedCustomers.length;
            renderCustomers(cachedCustomers);
            updateAdminCardsFromCache();
        }
    } catch (e) {
        console.error('Customers fetch error:', e);
    }
}

function renderCustomers(customers) {
    const tbody = document.getElementById('customers-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (customers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="p-4 text-center text-slate-400">No customers found.</td></tr>';
        return;
    }

    customers.forEach(c => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 transition-colors';

        tr.innerHTML = `
            <td class="p-3">
                <span class="font-bold text-slate-800 block">${c.full_name || 'Customer'}</span>
                <span class="text-[10px] font-mono text-purple-700">${c.identifier || '—'}</span>
            </td>
            <td class="p-3 font-medium text-slate-700">${c.email}</td>
            <td class="p-3">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 uppercase">
                    ${c.customer_type || 'student'}
                </span>
            </td>
            <td class="p-3 font-mono text-slate-500">${c.mobile || '—'}</td>
            <td class="p-3 font-bold text-emerald-700">₹${parseFloat(c.wallet_balance).toFixed(2)}</td>
            <td class="p-3 text-slate-700 font-semibold">${c.total_orders} orders (₹${parseFloat(c.total_spent).toFixed(2)})</td>
            <td class="p-3">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${c.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}">
                    ${c.is_active ? 'Active' : 'Suspended'}
                </span>
            </td>
            <td class="p-3 text-right">
                <button onclick="toggleCustomerStatus(${c.id})" class="px-3 py-1 rounded-lg text-xs font-bold ${c.is_active ? 'bg-slate-100 hover:bg-slate-200 text-slate-600' : 'bg-emerald-50 text-emerald-700'} transition-colors">
                    ${c.is_active ? 'Suspend' : 'Activate'}
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterCustomers() {
    const q = (document.getElementById('customer-search-input')?.value || '').toLowerCase().trim();
    if (!q) {
        renderCustomers(cachedCustomers);
        return;
    }
    const filtered = cachedCustomers.filter(c => 
        (c.full_name && c.full_name.toLowerCase().includes(q)) ||
        (c.email && c.email.toLowerCase().includes(q)) ||
        (c.identifier && c.identifier.toLowerCase().includes(q)) ||
        (c.mobile && c.mobile.includes(q))
    );
    renderCustomers(filtered);
}

async function toggleCustomerStatus(userId) {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/customers/${userId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        const data = await res.json();
        if (data.success) {
            const customer = cachedCustomers.find(c => Number(c.id) === Number(userId));
            if (customer) customer.is_active = Number(data.is_active);
            renderCustomers(cachedCustomers);
            updateAdminCardsFromCache();
        } else {
            alert(data.message || 'Failed to update customer status.');
        }
    } catch (e) {
        alert('Failed to connect to server.');
    }
}

// ============================================================================
// TEMPORARY CUSTOMER ACCOUNTS
// ============================================================================

async function loadTemporaryAccounts() {
    const tbody = document.getElementById('temporary-accounts-table-body');
    if (!tbody) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/customers`, { credentials: 'include' });
        const data = await res.json();
        if (data.success && Array.isArray(data.customers)) {
            cachedTemporaryAccounts = data.customers.filter(c => Number(c.is_temporary) === 1);
            renderTemporaryAccounts();
        }
    } catch (e) { console.error('Temporary accounts fetch error:', e); }
}

function renderTemporaryAccounts() {
    const tbody = document.getElementById('temporary-accounts-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!cachedTemporaryAccounts.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-400">No temporary accounts created.</td></tr>';
        return;
    }
    const now = Date.now();
    cachedTemporaryAccounts.forEach(c => {
        const expires = c.account_expires_at ? new Date(String(c.account_expires_at).replace(' ', 'T')).getTime() : 0;
        const expired = expires && expires <= now;
        const active = Number(c.is_active) === 1 && !expired;
        const status = active ? 'Active' : (expired ? 'Expired' : 'Suspended');
        const statusClass = active ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700';
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 transition-colors';
        tr.innerHTML = `<td class="p-3 font-bold text-slate-800">${c.full_name || 'Temporary User'}</td>
            <td class="p-3 text-slate-600">${c.email}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 uppercase">${c.customer_type || 'guest'}</span></td>
            <td class="p-3 font-mono text-[11px]">${c.account_expires_at || '—'}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${statusClass}">${status}</span></td>
            <td class="p-3 text-right"><button onclick="deleteTemporaryAccount(${c.id}, '${String(c.email).replace(/'/g, "\\'")}')" class="px-3 py-1 rounded-lg text-xs font-bold bg-rose-50 hover:bg-rose-100 text-rose-700">Delete</button></td>`;
        tbody.appendChild(tr);
    });
}

function toggleTemporaryAccountModal(show) {
    const modal = document.getElementById('temporary-account-modal');
    if (!modal) return;
    if (show) modal.classList.remove('hidden');
    else { modal.classList.add('hidden'); document.getElementById('temporary-account-form')?.reset(); }
}

async function handleCreateTemporaryAccount(event) {
    event.preventDefault();
    const payload = {
        customer_type: document.getElementById('temporary-customer-type').value,
        full_name: document.getElementById('temporary-full-name').value.trim(),
        email: document.getElementById('temporary-email').value.trim(),
        password: document.getElementById('temporary-password').value,
        identifier: document.getElementById('temporary-identifier').value.trim(),
        mobile: document.getElementById('temporary-mobile').value.trim(),
        duration_hours: Number(document.getElementById('temporary-duration').value)
    };
    try {
        const res = await fetch(`${API_BASE_URL}/admin/customers/temporary`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body:JSON.stringify(payload) });
        const data = await res.json();
        if (!data.success) { alert(data.message || 'Failed to create temporary account.'); return; }
        toggleTemporaryAccountModal(false);
        alert(`Temporary ${payload.customer_type} account created.\\n\\nLogin: ${payload.email}\\nPassword: ${payload.password}\\nExpires: ${data.account.account_expires_at}`);
        await loadTemporaryAccounts();
        await loadCustomers();
        await loadOverview();
    } catch (e) { alert('Failed to connect to server while creating the temporary account.'); }
}

async function deleteTemporaryAccount(userId, email) {
    if (!confirm(`Delete temporary account "${email}" permanently?`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/customers/${userId}/temporary`, { method:'DELETE', credentials:'include' });
        const data = await res.json();
        if (!data.success) { alert(data.message || 'Failed to delete temporary account.'); return; }
        await loadTemporaryAccounts();
        await loadCustomers();
        await loadOverview();
    } catch (e) { alert('Failed to connect to server while deleting the temporary account.'); }
}

// ============================================================================
// GLOBAL ORDERS MONITORING
// ============================================================================

async function loadGlobalOrders() {
    const tbody = document.getElementById('global-orders-table-body');
    if (!tbody) return;

    const status = document.getElementById('order-status-filter')?.value || '';
    const q = document.getElementById('order-search-input')?.value || '';

    let url = `${API_BASE_URL}/admin/orders?limit=50`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (q) url += `&q=${encodeURIComponent(q)}`;

    if (adminOrdersRequestController) adminOrdersRequestController.abort();
    const controller = new AbortController();
    adminOrdersRequestController = controller;
    const requestId = ++adminOrdersRequestSequence;

    try {
        const res = await fetch(url, { credentials: 'include', signal: controller.signal });
        const data = await res.json();

        if (requestId !== adminOrdersRequestSequence) return;
        if (data.success && data.orders) {
            tbody.innerHTML = '';
            if (data.orders.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" class="p-4 text-center text-slate-400">No orders match criteria.</td></tr>';
                return;
            }

            data.orders.forEach(o => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-50 transition-colors';

                let stBadge = 'bg-amber-100 text-amber-800';
                if (o.order_status === 'preparing') stBadge = 'bg-blue-100 text-blue-800';
                else if (o.order_status === 'ready') stBadge = 'bg-purple-100 text-purple-800';
                else if (o.order_status === 'completed') stBadge = 'bg-emerald-100 text-emerald-800';
                else if (o.order_status === 'cancelled') stBadge = 'bg-rose-100 text-rose-800';

                tr.innerHTML = `
                    <td class="p-3 font-mono font-bold text-blue-900">#${o.order_reference}</td>
                    <td class="p-3 font-semibold text-purple-700">${o.shop_name}</td>
                    <td class="p-3">
                        <span class="font-bold text-slate-800 block">${o.customer_name || 'Customer'}</span>
                        <span class="text-[10px] text-slate-400 font-mono">${o.customer_email || ''}</span>
                    </td>
                    <td class="p-3 text-slate-700 text-xs">${o.items_summary || 'Meal'}</td>
                    <td class="p-3 font-bold text-slate-900">₹${parseFloat(o.total_amount).toFixed(2)}</td>
                    <td class="p-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${o.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">
                            ${o.payment_status}
                        </span>
                        <span class="text-[10px] text-slate-400 block">${o.payment_method}</span>
                    </td>
                    <td class="p-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${stBadge} uppercase">
                            ${o.order_status}
                        </span>
                    </td>
                    <td class="p-3 font-mono font-black text-slate-700 tracking-wider">${o.pickup_otp}</td>
                    <td class="p-3 text-teal-700 font-bold text-[11px]">${o.pickup_at ? new Date(o.pickup_at.replace(' ', 'T') + (o.pickup_at.includes('Z') ? '' : 'Z')).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true,timeZone:'Asia/Kolkata'}) : '—'}</td>
                    <td class="p-3 text-slate-400 text-[11px]">${o.created_at ? o.created_at.split('.')[0] : '—'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error('Global orders fetch error:', e);
    }
}

// ============================================================================
// PAYMENT MONITORING
// ============================================================================

async function loadPayments() {
    const tbody = document.getElementById('payments-table-body');
    if (!tbody) return;

    const status = document.getElementById('payment-status-filter')?.value || '';
    let url = `${API_BASE_URL}/admin/payments?limit=50`;
    if (status) url += `&status=${encodeURIComponent(status)}`;

    if (adminPaymentsRequestController) adminPaymentsRequestController.abort();
    const controller = new AbortController();
    adminPaymentsRequestController = controller;
    const requestId = ++adminPaymentsRequestSequence;

    try {
        const res = await fetch(url, { credentials: 'include', signal: controller.signal });
        const data = await res.json();

        if (requestId !== adminPaymentsRequestSequence) return;
        if (data.success && data.payments) {
            tbody.innerHTML = '';
            if (data.payments.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="p-4 text-center text-slate-400">No payment records found.</td></tr>';
                return;
            }

            data.payments.forEach(p => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-50 transition-colors';

                let stClass = 'bg-amber-100 text-amber-800';
                if (p.status === 'successful') stClass = 'bg-emerald-100 text-emerald-800';
                else if (p.status === 'failed') stClass = 'bg-red-100 text-red-800';
                else if (p.status === 'refunded') stClass = 'bg-purple-100 text-purple-800';

                tr.innerHTML = `
                    <td class="p-3 font-mono text-slate-800 font-bold">${p.transaction_ref}</td>
                    <td class="p-3 font-mono text-blue-700 font-semibold">#${p.order_reference}</td>
                    <td class="p-3 text-slate-800 font-medium">${p.shop_name}</td>
                    <td class="p-3 text-slate-600 text-xs">${p.customer_email || '—'}</td>
                    <td class="p-3">
                        <span class="font-bold text-slate-700">${p.method}</span>
                        <span class="text-[10px] text-slate-400 block uppercase font-mono">${p.provider}</span>
                    </td>
                    <td class="p-3 font-black text-slate-900">₹${parseFloat(p.amount).toFixed(2)}</td>
                    <td class="p-3 font-mono text-slate-500 text-[10px]">${p.gateway_order_id || '—'}</td>
                    <td class="p-3">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-black ${stClass} uppercase">
                            ${p.status}
                        </span>
                    </td>
                    <td class="p-3 text-slate-400 text-[11px]">${p.created_at ? p.created_at.split('.')[0] : '—'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        if (e.name !== 'AbortError') console.error('Payments fetch error:', e);
    } finally {
        if (adminPaymentsRequestController === controller) adminPaymentsRequestController = null;
    }
}

// ============================================================================
// CONTACT REPORTS
// ============================================================================
async function loadContactReports() {
    const list = document.getElementById('contact-reports-list');
    if (!list) return;
    const status = document.getElementById('contact-report-status')?.value || '';
    const q = document.getElementById('contact-report-search')?.value.trim() || '';
    if (adminContactRequestController) adminContactRequestController.abort();
    const controller = new AbortController();
    adminContactRequestController = controller;
    const requestId = ++adminContactRequestSequence;

    list.innerHTML = '<div class="p-8 text-center text-sm text-slate-400">Loading contact reports...</div>';
    try {
        const params = new URLSearchParams(); if (status) params.set('status', status); if (q) params.set('q', q);
        const res = await fetch(API_BASE_URL + '/contact/admin?' + params.toString(), { credentials: 'include', signal: controller.signal });
        const data = await res.json().catch(function(){ return {}; });
        if (requestId !== adminContactRequestSequence) return;
        if (!res.ok || !data.success) {
            throw new Error(data.message || ('Contact Reports API returned HTTP ' + res.status));
        }
        const rows = Array.isArray(data.messages) ? data.messages : [];
        if (!rows.length) { list.innerHTML = '<div class="p-8 text-center text-sm text-slate-400">No contact reports found.</div>'; return; }
        list.innerHTML = rows.map(function(m) {
            const statusClass = m.status === 'new' ? 'bg-amber-100 text-amber-800' : m.status === 'resolved' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800';
            return '<article class="p-5 hover:bg-slate-50"><div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3"><div class="min-w-0"><div class="flex flex-wrap items-center gap-2"><span class="font-black text-slate-800">' + escapeHtml(m.subject) + '</span><span class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase ' + statusClass + '">' + escapeHtml(m.status) + '</span></div><p class="text-xs text-slate-500 mt-1">' + escapeHtml(m.full_name) + ' · <a class="text-blue-700 font-semibold" href="mailto:' + escapeHtml(m.email) + '">' + escapeHtml(m.email) + '</a> · ' + escapeHtml(formatAdminDate(m.created_at)) + '</p><p class="mt-3 text-sm text-slate-700 whitespace-pre-wrap break-words">' + escapeHtml(m.message) + '</p></div><div class="flex gap-2 shrink-0"><button onclick="updateContactReportStatus(' + m.id + ', \'read\')" class="px-3 py-2 rounded-lg text-xs font-bold bg-blue-50 text-blue-700 hover:bg-blue-100">Mark Read</button><button onclick="updateContactReportStatus(' + m.id + ', \'resolved\')" class="px-3 py-2 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 hover:bg-emerald-100">Resolve</button></div></div></article>';
        }).join('');
    } catch (e) {
        if (e.name !== 'AbortError') list.innerHTML = '<div class="p-8 text-center text-sm text-rose-600 font-semibold">Unable to load contact reports. Please refresh.</div>';
    } finally {
        if (adminContactRequestController === controller) adminContactRequestController = null;
    }
}
function formatAdminDate(v) { if (!v) return '—'; const d = new Date(String(v).includes('T') ? v : String(v).replace(' ', 'T') + 'Z'); return Number.isNaN(d.getTime()) ? String(v) : new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}).format(d); }
async function updateContactReportStatus(id, status) { try { const res=await fetch(API_BASE_URL+'/contact/admin/'+id+'/status',{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({status})}); const data=await res.json(); if(!res.ok||!data.success) throw new Error(data.message||'Failed'); await loadContactReports(); } catch(e){ alert(e.message||'Unable to update contact report.'); } }
// ============================================================================
// AUDIT LOGS
// ============================================================================

async function loadAuditLogs() {
    const tbody = document.getElementById('audit-table-body');
    if (!tbody) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/audit-logs?limit=50`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.audit_logs) {
            tbody.innerHTML = '';
            if (data.audit_logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-slate-400 font-sans">No audit events recorded yet.</td></tr>';
                return;
            }

            data.audit_logs.forEach(a => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-50 transition-colors';

                tr.innerHTML = `
                    <td class="p-3 text-slate-500 whitespace-nowrap">${a.created_at || '—'}</td>
                    <td class="p-3 font-bold text-slate-800">${a.actor_email || `User #${a.actor_id}`}</td>
                    <td class="p-3"><span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 uppercase font-sans text-[9px] font-bold">${a.actor_role || 'SYSTEM'}</span></td>
                    <td class="p-3 font-bold text-purple-700">${a.action}</td>
                    <td class="p-3 text-slate-600">${a.entity_type}</td>
                    <td class="p-3 text-slate-500">#${a.entity_id || '—'}</td>
                    <td class="p-3 text-slate-700 max-w-xs truncate" title="${a.details || ''}">${a.details || '—'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error('Audit logs fetch error:', e);
    }
}

// ============================================================================
// MODALS & EVENT HANDLERS
// ============================================================================

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
    const operational_status = document.getElementById('stall-operational-status').value;
    const description = document.getElementById('stall-description').value.trim();

    if (!name) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/shops`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ name, category, operational_status, description })
        });
        const data = await res.json();
        if (data.success) {
            toggleShopModal(false);
            cachedShops.push(data.shop || {id:data.shop_id,name,slug:name.toLowerCase().replace(/\s+/g,'-'),category,description,is_active:1,operational_status:operational_status,total_items:0});
            renderShops(cachedShops);
            updateAdminCardsFromCache();
        } else {
            alert(data.message || 'Failed to add stall.');
        }
    } catch (e) {
        alert('Connection error while adding stall.');
    }
}

function toggleVendorModal(show) {
    const modal = document.getElementById('create-vendor-modal');
    const select = document.getElementById('vendor-shop-select');
    if (modal) {
        if (show) {
            modal.classList.remove('hidden');
            if (select) {
                select.innerHTML = '<option value="">-- Unassigned --</option>';
                cachedShops.forEach(s => {
                    if (s.is_active) {
                        const opt = document.createElement('option');
                        opt.value = s.id;
                        opt.innerText = `${s.name} (${s.category || 'Food'})`;
                        select.appendChild(opt);
                    }
                });
            }
        } else {
            modal.classList.add('hidden');
            const form = document.getElementById('create-vendor-form');
            if (form) form.reset();
        }
    }
}

async function handleCreateVendor(event) {
    event.preventDefault();
    const email = document.getElementById('vendor-email').value.trim();
    const password = document.getElementById('vendor-password').value;
    const shop_id = document.getElementById('vendor-shop-select').value || null;

    if (!email || !password) return;

    try {
        const res = await fetch(`${API_BASE_URL}/admin/vendors`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password, shop_id })
        });
        const data = await res.json();
        if (data.success) {
            toggleVendorModal(false);
            cachedVendors.unshift(data.vendor || {id:data.user_id,email,role:'vendor',is_active:1,assigned_shop_id:shop_id,assigned_shop_name:data.assigned_shop_name});
            if (shop_id) {
                const shop = cachedShops.find(s => Number(s.id) === Number(shop_id));
                if (shop) { shop.owner_user_id = Number(data.user_id); shop.owner_email = email; }
            }
            renderVendors(cachedVendors);
            renderShops(cachedShops);
            updateAdminCardsFromCache();
        } else {
            alert(data.message || 'Failed to create vendor account.');
        }
    } catch (e) {
        alert('Connection error while creating vendor.');
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
