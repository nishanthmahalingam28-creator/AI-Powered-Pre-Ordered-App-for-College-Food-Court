document.addEventListener('DOMContentLoaded', async () => {
    const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';
    const customerCartKey = 'kpriet-food-court-cart';

    // 1. Initialize User Information from real backend session
    async function initUser() {
        let user = null;
        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                if (data.authenticated && data.user) {
                    user = data.user;
                    sessionStorage.setItem('foodCourtUser', JSON.stringify(user));
                }
            }
        } catch (e) {
            try {
                const raw = sessionStorage.getItem('foodCourtUser');
                if (raw) user = JSON.parse(raw);
            } catch (ignore) {}
        }

        if (!user || user.role !== 'customer') {
            window.location.href = '../auth/login.html';
            return;
        }

        const nameEl = document.getElementById('customer-name');
        if (nameEl && user.full_name) nameEl.textContent = user.full_name;

        const badgeEl = document.getElementById('customer-type-badge');
        if (badgeEl && user.customer_type) {
            badgeEl.textContent = user.customer_type.toUpperCase();
        }
    }

    // 2. Fetch AI Recommendations
    async function loadRecommendations() {
        const grid = document.getElementById('ai-recommendations-grid');
        const headingEl = document.getElementById('ai-section-heading');
        const badgeSlot = document.getElementById('meal-slot-badge');

        try {
            const res = await fetch(`${API_BASE_URL}/recommendations`, { credentials: 'include' });
            const data = await res.json();

            if (data.success && data.recommendations) {
                if (headingEl && data.heading) headingEl.textContent = data.heading;
                if (badgeSlot && data.slot) {
                    badgeSlot.innerHTML = `<i class="fa-solid fa-clock text-[10px]"></i> ${data.slot} Session Active`;
                }

                grid.innerHTML = '';
                data.recommendations.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'bg-white rounded-2xl p-5 border border-slate-100 shadow-sm hover:shadow-md transition-all flex flex-col justify-between relative group';
                    card.innerHTML = `
                        <div>
                            <div class="flex items-center justify-between gap-2 mb-2">
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-teal-50 text-teal-700 border border-teal-100">
                                    ${item.shop_name}
                                </span>
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                    <i class="fa-solid fa-sparkles text-[9px] mr-1 text-amber-500"></i>${item.ai_badge}
                                </span>
                            </div>
                            <h3 class="font-bold text-slate-800 text-base group-hover:text-teal-700 transition-colors">${item.name}</h3>
                            <p class="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">${item.description || item.category}</p>
                        </div>
                        <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                            <span class="text-base font-black text-slate-900">₹${item.price.toFixed(2)}</span>
                            <button type="button" class="bg-teal-700 hover:bg-teal-800 text-white font-bold text-xs px-3.5 py-2 rounded-xl transition-all shadow-sm flex items-center gap-1.5"
                                onclick="addQuickCart(${item.id}, '${item.name.replace(/'/g, "\\'")}', '${item.shop_name.replace(/'/g, "\\'")}', ${item.price}, this)">
                                <i class="fa-solid fa-plus text-[10px]"></i> Add
                            </button>
                        </div>
                    `;
                    grid.appendChild(card);
                });
            }
        } catch (e) {
            if (grid) grid.innerHTML = '<p class="text-xs text-slate-400 p-4">Unable to load AI smart recommendations right now.</p>';
        }
    }

    // 3. Fetch Active Orders
    async function loadActiveOrders() {
        const container = document.getElementById('active-orders-container');
        try {
            const res = await fetch(`${API_BASE_URL}/orders/my-orders`, { credentials: 'include' });
            const data = await res.json();

            if (data.success && data.orders && data.orders.length > 0) {
                const active = data.orders.filter(o => ['pending', 'preparing', 'ready'].includes(o.order_status));
                if (active.length > 0) {
                    container.innerHTML = '';
                    active.forEach(order => {
                        const statusColors = {
                            pending: 'bg-amber-100 text-amber-800 border-amber-200',
                            preparing: 'bg-blue-100 text-blue-800 border-blue-200',
                            ready: 'bg-emerald-100 text-emerald-800 border-emerald-200'
                        };
                        const statusBadge = statusColors[order.order_status] || 'bg-slate-100 text-slate-700';

                        const card = document.createElement('div');
                        card.className = 'bg-white rounded-3xl p-5 border-2 border-teal-500/30 shadow-lg shadow-teal-900/5 flex flex-col justify-between gap-4';
                        card.innerHTML = `
                            <div class="flex items-start justify-between">
                                <div>
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs font-black text-slate-400">ORDER #${order.order_reference}</span>
                                        <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider ${statusBadge}">
                                            ${order.order_status.toUpperCase()}
                                        </span>
                                    </div>
                                    <h3 class="font-extrabold text-lg text-slate-800 mt-1">${order.shop_name}</h3>
                                    <p class="text-xs text-slate-500 mt-0.5">${order.items_summary || 'Order Items'}</p>
                                </div>
                                <div class="bg-gradient-to-br from-teal-50 to-emerald-50 p-3 rounded-2xl border border-teal-200 text-center min-w-[110px]">
                                    <span class="text-[10px] font-bold text-teal-800 block uppercase tracking-wider">Pickup OTP</span>
                                    <strong class="text-xl font-black text-teal-900 tracking-widest block mt-0.5">${order.pickup_otp}</strong>
                                    <span class="text-[9px] text-teal-600 font-medium">Show at counter</span>
                                </div>
                            </div>
                            <div class="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                                <span>Total: <strong class="text-slate-800">₹${order.total_amount.toFixed(2)}</strong> (${order.payment_status})</span>
                                <span class="text-[11px] text-slate-400">${order.created_at || 'Today'}</span>
                            </div>
                        `;
                        container.appendChild(card);
                    });
                    return;
                }
            }
        } catch (e) {}
    }

    // 4. Fetch Food Court Stalls
    async function loadStalls() {
        const grid = document.getElementById('stalls-grid');
        try {
            const res = await fetch(`${API_BASE_URL}/shops`);
            const data = await res.json();
            if (data.success && data.shops) {
                grid.innerHTML = '';
                data.shops.forEach(stall => {
                    const card = document.createElement('a');
                    card.href = `menu.html?shop=${encodeURIComponent(stall.name)}`;
                    card.className = 'bg-white rounded-2xl p-5 border border-slate-200 hover:border-teal-500 hover:shadow-lg transition-all group block';
                    card.innerHTML = `
                        <div class="flex items-center gap-3.5 mb-3">
                            <div class="w-12 h-12 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center text-xl font-bold group-hover:bg-teal-700 group-hover:text-white transition-colors">
                                <i class="fa-solid fa-store"></i>
                            </div>
                            <div>
                                <h3 class="font-extrabold text-slate-800 group-hover:text-teal-700 text-base transition-colors">${stall.name}</h3>
                                <span class="text-[11px] text-slate-400 font-semibold">${stall.category || 'Multi-Cuisine'}</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed">${stall.description || 'Fresh food court delicacies.'}</p>
                        <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-teal-700">
                            <span>Browse Menu</span>
                            <i class="fa-solid fa-arrow-right text-[10px] transform group-hover:translate-x-1 transition-transform"></i>
                        </div>
                    `;
                    grid.appendChild(card);
                });
            }
        } catch (e) {
            if (grid) grid.innerHTML = '<p class="text-xs text-slate-400 p-4">Unable to load stall list right now.</p>';
        }
    }

    // Global quick cart add
    window.addQuickCart = function (id, name, shop, price, btn) {
        try {
            const stored = localStorage.getItem(customerCartKey);
            let cart = stored ? JSON.parse(stored) : [];

            // Enforce one cart = one shop policy
            if (cart.length > 0) {
                const existingShop = cart[0].shop || cart[0].shop_name;
                if (existingShop && shop && existingShop.toLowerCase() !== shop.toLowerCase()) {
                    const shouldClear = confirm(
                        `Your cart currently contains items from "${existingShop}".\n\nCampus policy requires orders to be placed from one stall at a time. Would you like to clear your cart to add "${name}" from "${shop}"?`
                    );
                    if (!shouldClear) {
                        return;
                    }
                    cart = [];
                }
            }

            const item = cart.find(c => c.id === id);
            if (item) {
                item.quantity += 1;
            } else {
                cart.push({ id, name, shop, price, quantity: 1 });
            }
            localStorage.setItem(customerCartKey, JSON.stringify(cart));

            if (btn) {
                const prev = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-check text-[10px]"></i> Added!';
                btn.classList.add('bg-emerald-600');
                setTimeout(() => {
                    btn.innerHTML = prev;
                    btn.classList.remove('bg-emerald-600');
                }, 1000);
            }
        } catch (e) {
            console.error('Add cart error:', e);
        }
    };

    await initUser();
    await Promise.all([loadRecommendations(), loadActiveOrders(), loadStalls()]);
});
