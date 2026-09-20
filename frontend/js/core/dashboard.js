const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

let currentShopId = 1;
let currentShopName = 'YPR';
let currentOperationalStatus = 'OPEN';

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', async () => {
    const authed = await initShopProfile();
    if (authed) {
        await Promise.all([loadAnalytics(), renderMenuItems(), renderOrders(), initVendorNotifications(), loadVendorDailySurvey(), loadMorningFoodVotes()]);
    }
});

// Resolve Authoritative Assigned Stall for Vendor
async function initShopProfile() {
    try {
        const authRes = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
        if (!authRes.ok) {
            sessionStorage.removeItem('foodCourtUser');
            window.location.href = 'login.html';
            return false;
        }
        const authData = await authRes.json();
        if (!authData.authenticated || (authData.user.role !== 'vendor' && authData.user.role !== 'admin')) {
            sessionStorage.removeItem('foodCourtUser');
            window.location.href = 'login.html';
            return false;
        }

        const res = await fetch(`${API_BASE_URL}/vendor/shop`, { credentials: 'include' });
        const data = await res.json();
        if (data.success && data.shop) {
            currentShopId = data.shop.id;
            currentShopName = data.shop.name;
            currentOperationalStatus = data.shop.operational_status || 'OPEN';
            updateOpStatusUI(currentOperationalStatus);
        } else {
            // Fallback for admin previewing stall
            await initShopNameFallback();
        }
    } catch (e) {
        await initShopNameFallback();
    }

    const titleEl = document.getElementById('title-shop-name');
    if (titleEl) {
        titleEl.innerText = currentShopName;
    }

    const outletEl = document.getElementById('outlet-name');
    if (outletEl) {
        outletEl.innerText = currentShopName + ' Stall';
    }
    return true;
}

window.handleVendorLogout = async function() {
    try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
    } catch (e) {
        console.error('Logout error', e);
    }
    sessionStorage.removeItem('foodCourtUser');
    localStorage.removeItem('foodCourtUser');
    window.location.href = 'login.html';
};

async function initShopNameFallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const selectedShop = urlParams.get('shop');

    let sessionUser = null;
    try {
        const raw = sessionStorage.getItem('foodCourtUser');
        if (raw) sessionUser = JSON.parse(raw);
    } catch (e) {}

    currentShopName = selectedShop || (sessionUser && sessionUser.shop_name) || 'YPR';

    try {
        const res = await fetch(`${API_BASE_URL}/shops`);
        const data = await res.json();
        if (data.success && data.shops) {
            const match = data.shops.find(s => s.name.toLowerCase() === currentShopName.toLowerCase());
            if (match) {
                currentShopId = match.id;
                currentOperationalStatus = match.operational_status || 'OPEN';
                updateOpStatusUI(currentOperationalStatus);
            }
        }
    } catch (e) {
        console.warn('Could not fetch shops list:', e);
    }
}

function updateOpStatusUI(status) {
    currentOperationalStatus = status;
    const badge = document.getElementById('vendor-op-status-badge');
    const desc = document.getElementById('vendor-op-status-desc');
    const dot = document.getElementById('status-indicator-dot');

    if (!badge) return;

    badge.innerText = status.replace('_', ' ');

    if (status === 'OPEN') {
        badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-black bg-emerald-100 text-emerald-800 uppercase';
        if (desc) desc.innerText = 'Accepting customer pre-orders. When paused or closed, in-flight orders can still be fulfilled.';
        if (dot) dot.className = 'w-3.5 h-3.5 rounded-full bg-emerald-500 animate-pulse';
    } else if (status === 'TEMPORARILY_UNAVAILABLE') {
        badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-black bg-amber-100 text-amber-800 uppercase';
        if (desc) desc.innerText = 'Stall is temporarily paused. New orders are blocked; active kitchen tickets can still be fulfilled.';
        if (dot) dot.className = 'w-3.5 h-3.5 rounded-full bg-amber-500';
    } else {
        badge.className = 'px-2.5 py-0.5 rounded-full text-xs font-black bg-rose-100 text-rose-800 uppercase';
        if (desc) desc.innerText = 'Stall is closed. New customer orders are blocked; active tickets can still be completed.';
        if (dot) dot.className = 'w-3.5 h-3.5 rounded-full bg-rose-500';
    }
}

// Vendor Operational Status Switcher
async function setVendorOperationalStatus(newStatus) {
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/shop/operational-status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ operational_status: newStatus })
        });
        const data = await res.json();
        if (data.success) {
            updateOpStatusUI(newStatus);
            await loadAnalytics();
        } else {
            alert(data.message || 'Failed to update operational status.');
        }
    } catch (e) {
        alert('Failed to connect to server.');
    }
}


async function loadMorningFoodVotes() {
    const wrap = document.getElementById('dashboard-vote-results');
    const totalEl = document.getElementById('dashboard-vote-total');
    if (!wrap) return;
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/daily-survey/vote-results`, { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || 'Unable to load food votes.');
        const total = Number(data.total_votes) || 0;
        const options = data.options || [];
        if (totalEl) totalEl.innerText = `${total} vote${total === 1 ? '' : 's'}`;
        if (!options.length) {
            wrap.innerHTML = '<p class="text-xs text-slate-400 py-4">No morning food survey has been published for today.</p>';
            return;
        }
        wrap.innerHTML = options.map(item => {
            const votes = Number(item.vote_count) || 0;
            const pct = Number(item.percentage) || 0;
            return `<div class="rounded-2xl bg-slate-50 border border-slate-100 p-4">
                <div class="flex items-center justify-between gap-2">
                    <p class="text-xs font-black text-slate-800 truncate">${escapeHtmlDashboard(item.item_name)}</p>
                    <span class="text-xs font-black text-amber-700 whitespace-nowrap">${votes} vote${votes === 1 ? '' : 's'}</span>
                </div>
                <p class="text-[10px] text-slate-400 uppercase mt-1">${escapeHtmlDashboard(item.meal_period || 'food')}</p>
                <div class="h-2 rounded-full bg-slate-200 overflow-hidden mt-3"><div class="h-full bg-amber-500 rounded-full" style="width:${Math.min(100, pct)}%"></div></div>
                <p class="text-[10px] text-slate-400 text-right mt-1">${pct}%</p>
            </div>`;
        }).join('');
    } catch (e) {
        wrap.innerHTML = '<p class="text-xs text-rose-600">Unable to load morning food votes.</p>';
        console.error('Morning food votes:', e);
    }
}
function escapeHtmlDashboard(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// Load Vendor Analytics
async function loadAnalytics() {
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/analytics?shop_id=${currentShopId}&shop=${encodeURIComponent(currentShopName)}`, { credentials: 'include' });
        const data = await res.json();
        if (data.success && data.analytics) {
            const a = data.analytics;
            const revEl = document.getElementById('today-revenue');
            if (revEl) revEl.innerText = `₹${a.today_revenue.toFixed(2)}`;

            const ordEl = document.getElementById('total-orders-count');
            if (ordEl) ordEl.innerText = a.total_orders;

            const actEl = document.getElementById('active-orders-count');
            if (actEl) actEl.innerText = `${a.active_orders} Active`;

            const availEl = document.getElementById('available-dishes-count');
            if (availEl) availEl.innerText = `${a.available_dishes} of ${a.total_dishes} Dishes`;

            const totalStockEl = document.getElementById('total-units-count');
            if (totalStockEl) totalStockEl.innerText = `${a.total_stock} Units`;

            const bar = document.getElementById('stock-progress-bar');
            if (bar && a.total_dishes > 0) {
                const pct = Math.round((a.available_dishes / a.total_dishes) * 100);
                bar.style.width = `${pct}%`;
            }
        }

        // Fetch AI Demand Intelligence
        if (currentShopId) {
            try {
                const aiRes = await fetch(`${API_BASE_URL}/ai/analytics/shop/${currentShopId}`, { credentials: 'include' });
                const aiData = await aiRes.json();
                if (aiData.success) {
                    const topItemsContainer = document.getElementById('ai-top-items-list');
                    const peakSlotBadge = document.getElementById('ai-peak-slot');

                    if (topItemsContainer) {
                        if (aiData.top_selling_items && aiData.top_selling_items.length > 0) {
                            topItemsContainer.innerHTML = aiData.top_selling_items.map(item => `
                                <div class="flex items-center justify-between py-1 border-b border-slate-50 last:border-0">
                                    <span class="font-medium text-slate-700 truncate max-w-[140px]">${item.item_name}</span>
                                    <span class="text-purple-700 font-bold bg-purple-50 px-2 py-0.5 rounded-full text-[10px]">${item.units_sold} sold</span>
                                </div>
                            `).join('');
                        } else {
                            topItemsContainer.innerHTML = '<p class="text-[11px] text-slate-400">No completed orders recorded yet.</p>';
                        }
                    }

                    if (peakSlotBadge && aiData.peak_hours && aiData.peak_hours.length > 0) {
                        peakSlotBadge.innerText = `Peak: ${aiData.peak_hours[0].hour}:00 (${aiData.peak_hours[0].orders_count} orders)`;
                    }
                }
            } catch (aiErr) {
                console.debug('AI analytics optional sync:', aiErr);
            }
        }
    } catch (e) {
        console.error('Analytics load error:', e);
    }
}

// Render Menu Items grouped by Breakfast, Lunch and Dinner
async function renderMenuItems() {
    const container = document.getElementById('menu-items-list');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/menu?shop_id=${currentShopId}`);
        const data = await res.json();

        if (!data.success || !data.items || data.items.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-400 p-4 text-center">No menu items found. Click "+ Add Item" above.</p>';
            return;
        }

        const periods = [
            { key: 'breakfast', title: 'Breakfast', icon: 'fa-sun', tone: 'amber' },
            { key: 'lunch', title: 'Lunch', icon: 'fa-bowl-food', tone: 'emerald' },
            { key: 'dinner', title: 'Dinner', icon: 'fa-moon', tone: 'indigo' }
        ];

        container.innerHTML = periods.map(period => {
            const items = data.items.filter(item => (item.meal_period || 'lunch').toLowerCase() === period.key);

            const itemHtml = items.length ? items.map(item => {
                const isOutOfStock = item.quantity <= 0 || !item.is_available;
                return `
                    <div class="bg-white p-3 rounded-2xl border border-slate-100 flex items-center gap-2 shadow-sm">
                        <div class="flex-grow min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-bold text-slate-800 truncate">${item.name}</span>
                                <span class="text-xs font-semibold text-blue-600 shrink-0">₹${parseFloat(item.price).toFixed(2)}</span>
                            </div>
                            <div class="flex items-center gap-2 mt-1">
                                <span class="text-[10px] text-slate-400 font-medium">${item.category}</span>
                                ${isOutOfStock ? '<span class="text-[10px] bg-red-100 text-red-600 font-bold px-1.5 py-0.5 rounded-md">Out of Stock</span>' : '<span class="text-[10px] bg-emerald-100 text-emerald-700 font-bold px-1.5 py-0.5 rounded-md">In Stock</span>'}
                            </div>
                        </div>

                        <select onchange="changeItemMealPeriod(${item.id}, this.value)" title="Meal period"
                            class="w-24 px-1.5 py-1.5 rounded-lg border border-slate-200 bg-white text-[10px] font-bold text-slate-700 focus:outline-none focus:border-blue-500">
                            <option value="breakfast" ${period.key === 'breakfast' ? 'selected' : ''}>Breakfast</option>
                            <option value="lunch" ${period.key === 'lunch' ? 'selected' : ''}>Lunch</option>
                            <option value="dinner" ${period.key === 'dinner' ? 'selected' : ''}>Dinner</option>
                        </select>

                        <div class="flex items-center gap-1.5 bg-slate-50 px-2 py-1 rounded-xl border border-slate-200">
                            <button onclick="updateQuantity(${item.id}, ${item.quantity}, -1)" class="w-5 h-5 flex items-center justify-center bg-white hover:bg-slate-200 text-slate-700 rounded-md text-xs font-bold">-</button>
                            <span class="text-xs font-extrabold w-6 text-center ${item.quantity < 5 ? 'text-amber-600' : 'text-slate-800'}">${item.quantity}</span>
                            <button onclick="updateQuantity(${item.id}, ${item.quantity}, 1)" class="w-5 h-5 flex items-center justify-center bg-white hover:bg-slate-200 text-slate-700 rounded-md text-xs font-bold">+</button>
                        </div>

                        <button onclick="editItemPrice(${item.id}, ${item.price}, '${item.name.replace(/'/g, "\\'")}')" title="Edit Price" class="w-7 h-7 flex items-center justify-center bg-slate-100 hover:bg-blue-50 hover:text-blue-600 text-slate-500 rounded-lg text-xs">
                            <i class="fa-solid fa-pen-to-square text-[10px]"></i>
                        </button>

                        <button onclick="deleteItem(${item.id}, '${item.name.replace(/'/g, "\\'")}')" title="Delete Item" class="w-7 h-7 flex items-center justify-center bg-slate-100 hover:bg-red-50 hover:text-red-600 text-slate-500 rounded-lg text-xs">
                            <i class="fa-solid fa-trash text-[10px]"></i>
                        </button>

                        <label class="relative inline-flex items-center cursor-pointer ml-1">
                            <input type="checkbox" class="sr-only peer" ${item.is_available && item.quantity > 0 ? 'checked' : ''} onchange="toggleItemAvailability(${item.id}, ${item.is_available ? 'true' : 'false'})">
                            <div class="w-8 h-4 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                    </div>
                `;
            }).join('') : '<p class="text-[11px] text-slate-400 bg-white/70 border border-dashed border-slate-200 rounded-xl p-3 text-center">No dishes in this section.</p>';

            return `
                <section class="rounded-2xl border border-slate-200 overflow-hidden bg-slate-50">
                    <div class="px-4 py-3 flex items-center justify-between bg-${period.tone}-50 border-b border-${period.tone}-100">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-${period.tone}-600">
                                <i class="fa-solid ${period.icon}"></i>
                            </div>
                            <div>
                                <h4 class="text-sm font-black text-slate-800">${period.title}</h4>
                                <p class="text-[10px] text-slate-400">${items.length} dish${items.length === 1 ? '' : 'es'}</p>
                            </div>
                        </div>
                    </div>
                    <div class="p-3 space-y-2">${itemHtml}</div>
                </section>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = '<p class="text-xs text-red-500 p-2">Failed to load menu items.</p>';
    }
}

// Change a dish between Breakfast, Lunch and Dinner
async function changeItemMealPeriod(itemId, mealPeriod) {
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/menu/item/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ meal_period: mealPeriod })
        });
        const data = await res.json();
        if (data.success) {
            await renderMenuItems();
        } else {
            alert(data.message || 'Failed to change meal period.');
            await renderMenuItems();
        }
    } catch (e) {
        alert('Failed to connect to the server.');
        await renderMenuItems();
    }
}

// Edit Price via API
async function editItemPrice(itemId, currentPrice, itemName) {
    const newPriceStr = prompt(`Enter new price for "${itemName}" (₹):`, currentPrice);
    if (newPriceStr === null) return;
    const newPrice = parseFloat(newPriceStr.trim());
    if (isNaN(newPrice) || newPrice <= 0) {
        alert('Please enter a valid price greater than ₹0.');
        return;
    }
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/menu/item/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ price: newPrice })
        });
        const data = await res.json();
        if (data.success) {
            await renderMenuItems();
            await loadAnalytics();
        } else {
            alert(data.message || 'Failed to update price.');
        }
    } catch (e) {
        alert('Failed to connect to the server.');
    }
}

// Delete Item via API
async function deleteItem(itemId, itemName) {
    if (!confirm(`Are you sure you want to remove "${itemName}" from your menu?`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/menu/item/${itemId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await res.json();
        if (data.success) {
            await renderMenuItems();
            await loadAnalytics();
        } else {
            alert(data.message || 'Failed to delete item.');
        }
    } catch (e) {
        alert('Failed to connect to the server.');
    }
}

// Adjust Quantity via API
async function updateQuantity(itemId, currentQty, change) {
    const newQty = Math.max(0, currentQty + change);
    try {
        await fetch(`${API_BASE_URL}/vendor/menu/item/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ quantity: newQty, available: newQty > 0 })
        });
        await renderMenuItems();
        await loadAnalytics();
    } catch (e) {
        console.error('Update quantity error:', e);
    }
}

// Toggle Item Availability
async function toggleItemAvailability(itemId, currentlyAvailable) {
    try {
        await fetch(`${API_BASE_URL}/vendor/menu/item/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ available: !currentlyAvailable })
        });
        await renderMenuItems();
        await loadAnalytics();
    } catch (e) {
        console.error('Toggle availability error:', e);
    }
}

// Render Orders List with Live Kitchen Tickets
async function renderOrders() {
    const container = document.getElementById('orders-list');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/orders/vendor/${currentShopId}`, { credentials: 'include' });
        const data = await res.json();
        container.innerHTML = '';

        if (!data.success || !data.orders || data.orders.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-400 p-4 text-center">No active kitchen orders right now.</p>';
            return;
        }

        data.orders.forEach(order => {
            const isCompleted = order.order_status === 'completed';
            const isCancelled = order.order_status === 'cancelled';
            const orderEl = document.createElement('div');
            orderEl.className = 'bg-slate-50 p-3.5 rounded-2xl border border-slate-100 flex items-center justify-between gap-3';

            let stClass = 'bg-amber-100 text-amber-800';
            if (order.order_status === 'preparing') stClass = 'bg-blue-100 text-blue-800';
            else if (order.order_status === 'ready') stClass = 'bg-purple-100 text-purple-800';
            else if (isCompleted) stClass = 'bg-emerald-100 text-emerald-800';
            else if (isCancelled) stClass = 'bg-rose-100 text-rose-800';

            let actionHtml = '';
            if (order.order_status === 'pending') {
                actionHtml = `
                    <button onclick="updateOrderStatus(${order.id}, 'preparing')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-colors whitespace-nowrap">
                        Prepare Food
                    </button>
                `;
            } else if (order.order_status === 'preparing') {
                actionHtml = `
                    <button onclick="updateOrderStatus(${order.id}, 'ready')" class="bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-colors whitespace-nowrap">
                        Mark Ready
                    </button>
                `;
            } else if (order.order_status === 'ready') {
                actionHtml = `
                    <span class="text-[11px] font-bold text-purple-700 bg-purple-50 px-2.5 py-1 rounded-xl border border-purple-200 whitespace-nowrap">
                        Awaiting Pickup OTP
                    </span>
                `;
            } else if (isCompleted) {
                actionHtml = `
                    <span class="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-xl border border-emerald-200 whitespace-nowrap">
                        Fulfilled ✓
                    </span>
                `;
            } else if (isCancelled) {
                actionHtml = `
                    <span class="text-[11px] font-bold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-xl border border-rose-200 whitespace-nowrap">
                        Cancelled
                    </span>
                `;
            }

            orderEl.innerHTML = `
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-blue-900 font-mono">#${order.order_reference}</span>
                        <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${stClass} uppercase">
                            ${order.order_status}
                        </span>
                        <span class="text-[10px] font-semibold text-slate-400">₹${parseFloat(order.total_amount).toFixed(2)}</span>
                    </div>
                    <p class="text-xs text-slate-700 font-medium mt-0.5">${order.items_summary || 'Meal items'}</p>
                    <p class="text-[10px] text-slate-400 mt-0.5">${order.customer_name || 'Customer'} · Method: ${order.payment_method} · Status: <strong>${order.payment_status}</strong></p>
                </div>
                <div class="flex items-center gap-2">
                    ${actionHtml}
                </div>
            `;
            container.appendChild(orderEl);
        });
    } catch (e) {
        container.innerHTML = '<p class="text-xs text-red-500 p-2">Failed to load live kitchen orders.</p>';
    }
}

// Update Order Status Helper
async function updateOrderStatus(orderId, newStatus) {
    try {
        const res = await fetch(`${API_BASE_URL}/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (data.success) {
            await renderOrders();
            await loadAnalytics();
        } else {
            alert(data.message || 'Failed to update order status.');
        }
    } catch (e) {
        console.error('Order status update error:', e);
        alert('Connection error while updating order status.');
    }
}

// Verify Customer Pickup OTP Action
async function handleVerifyOtp() {
    const input = document.getElementById('verify-otp-input');
    const alertEl = document.getElementById('otp-alert');
    if (!input || !alertEl) return;

    const otp = input.value.trim();
    if (!otp) {
        alertEl.className = 'text-xs font-bold px-3 py-1.5 rounded-xl bg-red-100 text-red-700 block';
        alertEl.textContent = 'Please enter the 6-digit customer OTP.';
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/orders/verify-otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ otp, shop_id: currentShopId })
        });
        const data = await res.json();

        if (data.success) {
            alertEl.className = 'text-xs font-bold px-3 py-1.5 rounded-xl bg-emerald-100 text-emerald-800 block';
            alertEl.textContent = `✓ ${data.message}`;
            input.value = '';
            await renderOrders();
            await loadAnalytics();
        } else {
            alertEl.className = 'text-xs font-bold px-3 py-1.5 rounded-xl bg-red-100 text-red-700 block';
            alertEl.textContent = `✗ ${data.message}`;
        }
    } catch (e) {
        alertEl.className = 'text-xs font-bold px-3 py-1.5 rounded-xl bg-red-100 text-red-700 block';
        alertEl.textContent = 'Connection error while verifying OTP.';
    }
}

// Modal Visibility Control
function toggleModal(show) {
    const modal = document.getElementById('add-item-modal');
    if (modal) {
        if (show) {
            modal.classList.remove('hidden');
        } else {
            modal.classList.add('hidden');
            const form = document.getElementById('add-item-form');
            if (form) form.reset();
        }
    }
}

// Handle Form Submission for Adding New Item
async function handleAddItem(event) {
    event.preventDefault();

    const name = document.getElementById('item-name').value.trim();
    const price = parseFloat(document.getElementById('item-price').value);
    const quantity = parseInt(document.getElementById('item-quantity').value) || 0;
    const category = document.getElementById('item-category').value;
    const mealPeriod = document.getElementById('item-meal-period').value;
    const available = document.getElementById('item-available').checked;

    if (!name || isNaN(price)) return;

    try {
        const res = await fetch(`${API_BASE_URL}/vendor/menu/item`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                name,
                price,
                quantity,
                category,
                meal_period: mealPeriod,
                available
            })
        });
        const data = await res.json();
        if (data.success) {
            toggleModal(false);
            await renderMenuItems();
            await loadAnalytics();
        } else {
            alert(data.message || 'Failed to add item.');
        }
    } catch (e) {
        alert('Failed to connect to the server.');
    }
}

// ============================================================================
// VENDOR NOTIFICATIONS & KITCHEN ALERTS (PHASE 7)
// ============================================================================

let vendorNotifPollingTimer = null;

async function initVendorNotifications() {
    await fetchVendorUnreadCount();
    if (vendorNotifPollingTimer) clearInterval(vendorNotifPollingTimer);
    vendorNotifPollingTimer = setInterval(fetchVendorUnreadCount, 10000);
}

window.addEventListener('beforeunload', () => {
    if (vendorNotifPollingTimer) {
        clearInterval(vendorNotifPollingTimer);
        vendorNotifPollingTimer = null;
    }
});

async function fetchVendorUnreadCount() {
    try {
        const res = await fetch(`${API_BASE_URL}/notifications/unread-count`, { credentials: 'include' });
        if (!res.ok) {
            if (res.status === 401 && vendorNotifPollingTimer) {
                clearInterval(vendorNotifPollingTimer);
            }
            return;
        }
        const data = await res.json();
        if (data.success) {
            const badge = document.getElementById('vendor-notif-badge');
            if (badge) {
                const count = data.unread_count || 0;
                if (count > 0) {
                    badge.textContent = count > 99 ? '99+' : count;
                    badge.classList.remove('hidden');
                } else {
                    badge.textContent = '0';
                    badge.classList.add('hidden');
                }
            }
        }
    } catch (e) {
        console.debug('Vendor notification count error:', e);
    }
}

async function toggleVendorNotifDrawer(show) {
    const drawer = document.getElementById('vendor-notif-drawer');
    const backdrop = document.getElementById('vendor-notif-backdrop');
    if (!drawer || !backdrop) return;

    if (show) {
        drawer.classList.remove('translate-x-full');
        backdrop.classList.remove('hidden');
        await loadVendorNotifications();
    } else {
        drawer.classList.add('translate-x-full');
        backdrop.classList.add('hidden');
    }
}

async function loadVendorNotifications() {
    const container = document.getElementById('vendor-notif-items');
    if (!container) return;

    container.innerHTML = `
        <div class="py-8 text-center text-slate-400">
            <i class="fa-solid fa-spinner fa-spin text-xl mb-2 text-blue-600"></i>
            <p class="text-xs font-semibold">Loading kitchen alerts...</p>
        </div>
    `;

    try {
        const res = await fetch(`${API_BASE_URL}/notifications?limit=30`, { credentials: 'include' });
        const data = await res.json();

        if (!data.success || !data.notifications || data.notifications.length === 0) {
            container.innerHTML = `
                <div class="py-10 text-center text-slate-400">
                    <i class="fa-regular fa-bell-slash text-2xl mb-2 text-slate-300"></i>
                    <p class="text-xs font-bold text-slate-600">No active alerts</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">New orders and kitchen events will appear here.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        data.notifications.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.className = `p-3.5 rounded-2xl border text-xs flex items-start gap-3 transition-colors ${
                item.is_read ? 'bg-white border-slate-100' : 'bg-blue-50/50 border-blue-200'
            }`;
            itemDiv.innerHTML = `
                <div class="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 text-sm">
                    <i class="fa-solid ${item.type === 'ORDER_CANCELLED' ? 'fa-ban text-rose-500' : 'fa-receipt'}"></i>
                </div>
                <div class="flex-grow min-w-0">
                    <div class="flex items-center justify-between gap-1 mb-0.5">
                        <span class="font-black text-slate-900 truncate">${item.title}</span>
                        <span class="text-[10px] text-slate-400 shrink-0">${item.created_at ? item.created_at.split(' ')[1] || '' : ''}</span>
                    </div>
                    <p class="text-slate-600 text-[11px] leading-relaxed">${item.message}</p>
                </div>
            `;
            container.appendChild(itemDiv);
        });
    } catch (e) {
        container.innerHTML = `<div class="p-4 text-center text-xs text-rose-500 font-bold">Failed to load alerts.</div>`;
    }
}

async function markAllVendorNotifsRead() {
    try {
        const res = await fetch(`${API_BASE_URL}/notifications/read-all`, {
            method: 'PUT',
            credentials: 'include'
        });
        if (res.ok) {
            const badge = document.getElementById('vendor-notif-badge');
            if (badge) badge.classList.add('hidden');
            await loadVendorNotifications();
        }
    } catch (e) {
        console.error('Failed to mark all vendor notifications read:', e);
    }
}
// ============================================================================
// VENDOR DAILY MORNING MENU SURVEY
// ============================================================================

let vendorDailyMenuCatalog = [];

async function loadVendorDailySurvey() {
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/daily-survey/today`, { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.success) { showDailySurveyMessage(data.message || 'Unable to load today\'s menu survey.', false); return; }
        vendorDailyMenuCatalog = data.menu_catalog || [];
        const servingToggle = document.getElementById('daily-serving-today');
        if (servingToggle) servingToggle.checked = data.survey ? data.survey.is_serving_today !== false : true;
        renderDailyMealOptions('breakfast', data.selected && data.selected.breakfast ? data.selected.breakfast : []);
        renderDailyMealOptions('lunch', data.selected && data.selected.lunch ? data.selected.lunch : []);
        renderDailyMealOptions('dinner', data.selected && data.selected.dinner ? data.selected.dinner : []);
        const status = document.getElementById('daily-survey-status');
        if (status) {
            status.textContent = data.survey && data.survey.submitted ? 'Submitted Today' : 'Not Submitted';
            status.className = data.survey && data.survey.submitted ? 'text-[10px] font-black uppercase px-3 py-1.5 rounded-full bg-emerald-100 text-emerald-700' : 'text-[10px] font-black uppercase px-3 py-1.5 rounded-full bg-slate-100 text-slate-600';
        }
    } catch (e) { console.error('Daily survey load error:', e); showDailySurveyMessage('Unable to load today\'s menu survey.', false); }
}

function renderDailyMealOptions(period, selectedRows) {
    const container = document.getElementById(`daily-${period}-items`);
    if (!container) return;
    const selectedMap = {};
    selectedRows.forEach(row => { selectedMap[String(row.menu_item_id)] = row; });
    if (!vendorDailyMenuCatalog.length) { container.innerHTML = '<p class="text-[11px] text-slate-400">No permanent menu items yet. Add dishes below in Update Menu first.</p>'; return; }
    const periodItems = vendorDailyMenuCatalog.filter(item => (item.meal_period || 'lunch').toLowerCase() === period);
    if (!periodItems.length) { container.innerHTML = '<p class="text-[11px] text-slate-400">No dishes assigned to this meal section. Use Update Menu to assign dishes.</p>'; return; }
    container.innerHTML = periodItems.map(item => {
        const selected = selectedMap[String(item.id)];
        const qty = selected ? selected.quantity : item.stock_quantity;
        return '<label class="block bg-white rounded-xl border border-slate-100 p-2.5 cursor-pointer hover:border-amber-300 transition-colors">' +
            '<div class="flex items-center gap-2"><input type="checkbox" class="daily-menu-check accent-amber-600 w-4 h-4" data-period="' + period + '" data-item-id="' + item.id + '" ' + (selected ? 'checked' : '') + '>' +
            '<span class="text-xs font-bold text-slate-800 truncate flex-grow">' + item.name + '</span><span class="text-[10px] font-bold text-slate-500">₹' + Number(item.price).toFixed(2) + '</span></div>' +
            '<div class="flex items-center justify-between gap-2 mt-2 ml-6"><span class="text-[10px] text-slate-400">' + item.category + '</span>' +
            '<input type="number" min="0" max="100000" value="' + Math.max(0, qty) + '" data-qty-period="' + period + '" data-qty-item-id="' + item.id + '" class="w-20 px-2 py-1 rounded-lg border border-slate-200 text-[10px] font-bold text-right focus:outline-none focus:border-amber-400"></div></label>';
    }).join('');
}

function showDailySurveyMessage(message, success) {
    const el = document.getElementById('daily-survey-message');
    if (!el) return;
    el.className = 'mt-4 p-3 rounded-xl text-xs font-bold ' + (success ? 'bg-emerald-50 border border-emerald-200 text-emerald-800' : 'bg-rose-50 border border-rose-200 text-rose-800');
    el.textContent = message; el.classList.remove('hidden');
}

async function saveVendorDailySurvey() {
    const button = document.getElementById('save-daily-survey-btn');
    const serving = document.getElementById('daily-serving-today');
    const meals = { breakfast: [], lunch: [], dinner: [] };
    document.querySelectorAll('.daily-menu-check:checked').forEach(check => {
        const period = check.dataset.period; const itemId = Number(check.dataset.itemId);
        const qtyInput = document.querySelector('[data-qty-period="' + period + '"][data-qty-item-id="' + itemId + '"]');
        const quantity = qtyInput ? Math.max(0, Number.parseInt(qtyInput.value || '0', 10)) : 0;
        if (meals[period]) meals[period].push({ menu_item_id: itemId, quantity });
    });
    if (button) { button.disabled = true; button.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1.5"></i> Publishing...'; }
    try {
        const res = await fetch(`${API_BASE_URL}/vendor/daily-survey`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ is_serving_today: serving ? serving.checked : true, meals }) });
        const data = await res.json();
        if (data.success) { showDailySurveyMessage('✓ Today\'s breakfast, lunch and dinner menu has been published.', true); await loadVendorDailySurvey(); }
        else showDailySurveyMessage(data.message || 'Unable to save today\'s menu survey.', false);
    } catch (e) { console.error('Daily survey save error:', e); showDailySurveyMessage('Connection error while publishing today\'s menu.', false); }
    finally { if (button) { button.disabled = false; button.innerHTML = '<i class="fa-solid fa-cloud-arrow-up mr-1.5"></i> Publish Today\'s Menu'; } }
}
