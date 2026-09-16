const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

let currentShopId = 1;
let currentShopName = 'YPR';

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', async () => {
    await initShopName();
    await Promise.all([loadAnalytics(), renderMenuItems(), renderOrders()]);
});

// Parse URL or Session for Stall Information
async function initShopName() {
    const urlParams = new URLSearchParams(window.location.search);
    const selectedShop = urlParams.get('shop');

    let sessionUser = null;
    try {
        const raw = sessionStorage.getItem('foodCourtUser');
        if (raw) sessionUser = JSON.parse(raw);
    } catch (e) {}

    currentShopName = selectedShop || (sessionUser && sessionUser.shop_name) || 'YPR';

    const titleEl = document.getElementById('title-shop-name');
    if (titleEl) {
        titleEl.innerText = currentShopName;
    }

    const outletEl = document.getElementById('outlet-name');
    if (outletEl) {
        outletEl.innerText = currentShopName + ' Stall';
    }

    // Resolve shop id
    try {
        const res = await fetch(`${API_BASE_URL}/shops`);
        const data = await res.json();
        if (data.success && data.shops) {
            const match = data.shops.find(s => s.name.toLowerCase() === currentShopName.toLowerCase());
            if (match) {
                currentShopId = match.id;
            }
        }
    } catch (e) {
        console.warn('Could not fetch shops list:', e);
    }
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
    } catch (e) {
        console.error('Analytics load error:', e);
    }
}

// Render Menu Items with Live API
async function renderMenuItems() {
    const container = document.getElementById('menu-items-list');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/menu?shop_id=${currentShopId}`);
        const data = await res.json();
        container.innerHTML = '';

        if (!data.success || !data.items || data.items.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-400 p-4 text-center">No menu items found. Click "+ Add Item" above.</p>';
            return;
        }

        data.items.forEach(item => {
            const itemEl = document.createElement('div');
            itemEl.className = 'bg-slate-50 p-3 rounded-2xl border border-slate-100 flex items-center justify-between gap-2';

            const isOutOfStock = item.quantity <= 0 || !item.is_available;

            itemEl.innerHTML = `
                <div class="flex-grow">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-slate-800">${item.name}</span>
                        <span class="text-xs font-semibold text-blue-600">(₹${parseFloat(item.price).toFixed(2)})</span>
                    </div>
                    <div class="flex items-center gap-2 mt-0.5">
                        <span class="text-[10px] text-slate-400 font-medium">${item.category}</span>
                        ${isOutOfStock ? '<span class="text-[10px] bg-red-100 text-red-600 font-bold px-1.5 py-0.5 rounded-md">Out of Stock</span>' : '<span class="text-[10px] bg-emerald-100 text-emerald-700 font-bold px-1.5 py-0.5 rounded-md">In Stock</span>'}
                    </div>
                </div>

                <!-- Quantity Controls -->
                <div class="flex items-center gap-1.5 bg-white px-2 py-1 rounded-xl border border-slate-200">
                    <button onclick="updateQuantity(${item.id}, ${item.quantity}, -1)" class="w-5 h-5 flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-bold transition-colors">
                        -
                    </button>
                    <span class="text-xs font-extrabold w-6 text-center ${item.quantity < 5 ? 'text-amber-600' : 'text-slate-800'}">
                        ${item.quantity}
                    </span>
                    <button onclick="updateQuantity(${item.id}, ${item.quantity}, 1)" class="w-5 h-5 flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-bold transition-colors">
                        +
                    </button>
                </div>

                <!-- Availability Toggle Switch -->
                <label class="relative inline-flex items-center cursor-pointer ml-1">
                    <input type="checkbox" class="sr-only peer" ${item.is_available && item.quantity > 0 ? 'checked' : ''} onchange="toggleItemAvailability(${item.id}, ${item.is_available ? 'true' : 'false'})">
                    <div class="w-8 h-4 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
            `;
            container.appendChild(itemEl);
        });
    } catch (e) {
        container.innerHTML = '<p class="text-xs text-red-500 p-2">Failed to load menu items.</p>';
    }
}

// Adjust Quantity via API
async function updateQuantity(itemId, currentQty, change) {
    const newQty = Math.max(0, currentQty + change);
    try {
        await fetch(`${API_BASE_URL}/vendor/menu/item/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
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
        const res = await fetch(`${API_BASE_URL}/orders/vendor/${currentShopId}`);
        const data = await res.json();
        container.innerHTML = '';

        if (!data.success || !data.orders || data.orders.length === 0) {
            container.innerHTML = '<p class="text-xs text-slate-400 p-4 text-center">No active kitchen orders right now.</p>';
            return;
        }

        data.orders.forEach(order => {
            const isDone = order.order_status === 'completed' || order.order_status === 'cancelled';
            const orderEl = document.createElement('div');
            orderEl.className = 'bg-slate-50 p-3.5 rounded-2xl border border-slate-100 flex items-center justify-between gap-3';
            orderEl.innerHTML = `
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-blue-900">#${order.order_reference}</span>
                        <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${order.order_status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'} uppercase">
                            ${order.order_status}
                        </span>
                    </div>
                    <p class="text-xs text-slate-700 font-medium mt-0.5">${order.items_summary || 'Meal items'}</p>
                    <p class="text-[10px] text-slate-400 mt-0.5">${order.customer_name || 'Customer'} · OTP: <strong>${order.pickup_otp}</strong></p>
                </div>
                <div class="flex items-center gap-2">
                    ${order.order_status === 'pending' ? `
                        <button onclick="updateOrderStatus(${order.id}, 'preparing')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-colors">
                            Prepare
                        </button>
                    ` : ''}
                    ${order.order_status === 'preparing' ? `
                        <button onclick="updateOrderStatus(${order.id}, 'ready')" class="bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-colors">
                            Ready
                        </button>
                    ` : ''}
                    <button 
                        onclick="completeOrder(${order.id})" 
                        class="${isDone ? 'bg-emerald-600 opacity-60 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-700'} text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-colors"
                        ${isDone ? 'disabled' : ''}>
                        ${isDone ? 'Fulfilled ✓' : 'Complete'}
                    </button>
                </div>
            `;
            container.appendChild(orderEl);
        });
    } catch (e) {
        container.innerHTML = '<p class="text-xs text-red-500 p-2">Failed to load live kitchen orders.</p>';
    }
}

// Complete Order Action
async function completeOrder(orderId) {
    await updateOrderStatus(orderId, 'completed');
}

// Update Order Status Helper
async function updateOrderStatus(orderId, newStatus) {
    try {
        const res = await fetch(`${API_BASE_URL}/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (data.success) {
            await renderOrders();
            await loadAnalytics();
        }
    } catch (e) {
        console.error('Order status update error:', e);
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
    const available = document.getElementById('item-available').checked;

    if (!name || isNaN(price)) return;

    try {
        const res = await fetch(`${API_BASE_URL}/vendor/menu/item`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                shop_id: currentShopId,
                name,
                price,
                quantity,
                category,
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