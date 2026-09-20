document.addEventListener('DOMContentLoaded', async () => {
    const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

    // Purge legacy financial storage keys to guarantee zero localStorage reliance
    try {
        localStorage.removeItem("expenses");
        localStorage.removeItem("income");
        localStorage.removeItem("budgets");
        localStorage.removeItem("goals");
        localStorage.removeItem("financial_goals");
        localStorage.removeItem("food_court_expenses");
        localStorage.removeItem("food_court_income");
        localStorage.removeItem("food_court_budgets");
        localStorage.removeItem("food_court_goals");
    } catch (e) {
        console.warn("Storage access restricted:", e);
    }
// 1. Initialize User Information from authoritative backend session
    async function initUser() {
        let user = null;
        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
            if (res.ok) {
                const data = await res.json();
                if (data.authenticated && data.user) {
                    user = data.user;
                    sessionStorage.setItem('foodCourtUser', JSON.stringify(user));
                } else {
                    sessionStorage.removeItem('foodCourtUser');
                    window.location.href = '../auth/login.html';
                    return;
                }
            } else {
                sessionStorage.removeItem('foodCourtUser');
                window.location.href = '../auth/login.html';
                return;
            }
        } catch (e) {
            console.warn('Authentication verification check failed:', e);
            sessionStorage.removeItem('foodCourtUser');
            window.location.href = '../auth/login.html';
            return;
        }

        if (!user || user.role !== 'customer') {
            sessionStorage.removeItem('foodCourtUser');
            window.location.href = '../auth/login.html';
            return;
        }

        const nameEl = document.getElementById('customer-name');
        if (nameEl && user.full_name) nameEl.textContent = user.full_name;

        // Student workspace identity
        const displayName = user.full_name || 'Student';
        const sidebarName = document.getElementById('sidebar-user-name');
        const sidebarType = document.getElementById('sidebar-user-type');
        const sidebarAvatar = document.getElementById('sidebar-avatar');
        const topbarAvatar = document.getElementById('topbar-avatar');
        const topbarType = document.getElementById('topbar-customer-type');
        if (sidebarName) sidebarName.textContent = displayName;
        if (sidebarType) sidebarType.textContent = (user.customer_type || 'Student').toUpperCase();
        if (sidebarAvatar) sidebarAvatar.textContent = displayName.charAt(0).toUpperCase();
        if (topbarAvatar) topbarAvatar.textContent = displayName.charAt(0).toUpperCase();
        if (topbarType) topbarType.textContent = (user.customer_type || 'Student').replace(/_/g, ' ');


        const badgeEl = document.getElementById('customer-type-badge');
        if (badgeEl && user.customer_type) {
            badgeEl.textContent = user.customer_type.toUpperCase();
        }

        const rollEl = document.getElementById('customer-roll-badge');
        if (rollEl) {
            const rollNumber = user.roll_number || user.identifier;
            if (rollNumber) {
                rollEl.textContent = rollNumber;
                rollEl.classList.remove('hidden');
            } else {
                rollEl.classList.add('hidden');
            }
        }
    }

    // Load Morning Survey Status for Today
    async function loadMorningSurveyStatus() {
        const bannerBadge = document.getElementById('survey-banner-badge');
        const bannerTitle = document.getElementById('survey-banner-title');
        const bannerSubtitle = document.getElementById('survey-banner-subtitle');
        const bannerBtn = document.getElementById('survey-banner-btn');
        const bannerIcon = document.getElementById('survey-banner-icon');

        try {
            const res = await fetch(`${API_BASE_URL}/customer/survey/today`, { credentials: 'include' });
            if (!res.ok) return;
            const data = await res.json();
            if (data.success) {
                if (data.completed && data.survey) {
                    if (bannerBadge) {
                        bannerBadge.textContent = 'Survey Completed ✓';
                        bannerBadge.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300';
                    }
                    if (bannerTitle) {
                        bannerTitle.textContent = `Today's Choice: ${data.survey.meal_preference || 'Logged'} (${data.survey.dietary_preference || 'Standard'})`;
                    }
                    if (bannerSubtitle) {
                        bannerSubtitle.textContent = `Hunger: ${data.survey.hunger_level || 'Normal'} • Type: ${data.survey.meal_type || 'Lunch'} • AI recommendations personalized!`;
                    }
                    if (bannerBtn) {
                        bannerBtn.href = 'morning-survey.html?edit=1';
                        bannerBtn.innerHTML = `<span>Update Survey</span><i class="fa-solid fa-arrow-right text-xs"></i>`;
                        bannerBtn.className = 'bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl border border-slate-300 transition-all flex items-center gap-2';
                    }
                    if (bannerIcon) {
                        bannerIcon.className = 'w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl font-bold shrink-0';
                        bannerIcon.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
                    }
                } else {
                    if (bannerBadge) {
                        bannerBadge.textContent = 'Not Completed';
                        bannerBadge.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-300';
                    }
                    if (bannerTitle) {
                        bannerTitle.textContent = 'Complete Morning Survey';
                    }
                    if (bannerSubtitle) {
                        bannerSubtitle.textContent = 'Tell us what you are craving today to unlock personalized food court recommendations.';
                    }
                    if (bannerBtn) {
                        bannerBtn.href = 'morning-survey.html';
                        bannerBtn.innerHTML = `<span>Complete Morning Survey</span><i class="fa-solid fa-arrow-right text-xs"></i>`;
                        bannerBtn.className = 'bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 text-white font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl shadow-md transition-all flex items-center gap-2';
                    }
                    if (bannerIcon) {
                        bannerIcon.className = 'w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl font-bold shrink-0';
                        bannerIcon.innerHTML = '<i class="fa-solid fa-sun"></i>';
                    }
                }
            }
        } catch (e) {
            console.warn('Morning survey status check failed:', e);
        }
    }


    // When pickup OTP verification completes an order, refresh the financial cards immediately.
    window.addEventListener('foodcourt:order-status', function (event) {
        const status = String(event.detail?.order_status || '').toLowerCase();
        if (status === 'completed') {
            loadFoodBudgetSnapshot();
        }
    });

    // Global customer logout handler
    window.handleCustomerLogout = async function () {
        try {
            await fetch(`${API_BASE_URL}/auth/logout`, {
                method: 'POST',
                credentials: 'include'
            });
        } catch (e) {
            console.warn('Logout request failed:', e);
        }
        sessionStorage.clear();
        try {
            localStorage.removeItem("expenses");
            localStorage.removeItem("income");
            localStorage.removeItem("budgets");
            localStorage.removeItem("goals");
            localStorage.removeItem("financial_goals");
        } catch (e) {}
        window.location.href = '../auth/login.html';
    };

    // 2. Fetch AI Recommendations
    async function loadRecommendations() {
        const grid = document.getElementById('ai-recommendations-grid');
        const headingEl = document.getElementById('ai-section-heading');
        const badgeSlot = document.getElementById('meal-slot-badge');

        try {
            const res = await fetch(`${API_BASE_URL}/ai/recommendations`, { credentials: 'include' });
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
                                    <i class="fa-solid fa-sparkles text-[9px] mr-1 text-amber-500"></i>${item.reason || item.ai_badge}
                                </span>
                            </div>
                            <h3 class="font-bold text-slate-800 text-base group-hover:text-teal-700 transition-colors">${item.name}</h3>
                            <p class="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">${item.description || item.category}</p>
                        </div>
                        <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                            <span class="text-base font-black text-slate-900">₹${Number(item.price || 0).toFixed(2)}</span>
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

    // 3. Load the authoritative Food Budget/Spent snapshot.
    // The backend calculates spending from completed-order expense records.
    async function loadFoodBudgetSnapshot() {
        try {
            const res = await fetch(`${API_BASE_URL}/customer/financial-summary`, { credentials: 'include' });
            if (!res.ok) return;
            const data = await res.json();
            if (!data.success) return;
            const summary = data.summary || {};
            const budget = Number(summary.total_budget || 0);
            const spent = Number(summary.total_budget_spent || 0);
            const remaining = Math.max(0, budget - spent);
            const money = value => `₹${value.toFixed(2)}`;
            const budgetEl = document.getElementById('dashboard-food-budget');
            const spentEl = document.getElementById('dashboard-food-spent');
            const remainingEl = document.getElementById('dashboard-food-remaining');
            if (budgetEl) budgetEl.textContent = money(budget);
            if (spentEl) spentEl.textContent = money(spent);
            if (remainingEl) remainingEl.textContent = money(remaining);
        } catch (e) {
            console.warn('Food budget snapshot refresh failed:', e);
        }
    }

    // Keep the dashboard financial cards current even if Socket.IO is temporarily unavailable.
    // The refresh is lightweight and reads only the authenticated customer's summary.
    setInterval(loadFoodBudgetSnapshot, 2000);

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
                                <span>Total: <strong class="text-slate-800">₹${Number(order.total_amount || 0).toFixed(2)}</strong> (${order.payment_status})</span>
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
    // Global quick cart add via authoritative backend cart API
    window.addQuickCart = async function (id, name, shop, price, btn) {
        if (btn) btn.disabled = true;

        try {
            let res = await fetch(`${API_BASE_URL}/cart`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ item_id: id, quantity: 1 })
            });

            if (res.status === 401) {
                const shouldLogin = confirm('Please log in to add items to your cart. Would you like to log in now?');
                if (shouldLogin) {
                    window.location.href = '../auth/login.html';
                }
                return;
            }

            let data = await res.json().catch(() => ({}));

            if (res.status === 409 && data.conflict) {
                const shouldClear = confirm(
                    `${data.message}\n\nWould you like to clear your existing cart to start an order from ${shop}?`
                );
                if (!shouldClear) {
                    return;
                }

                res = await fetch(`${API_BASE_URL}/cart`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ item_id: id, quantity: 1, clear_conflicting_stall: true })
                });
                data = await res.json().catch(() => ({}));
            }

            if (res.ok && data.success) {
                if (btn) {
                    const prev = btn.innerHTML;
                    btn.innerHTML = '<i class="fa-solid fa-check text-[10px]"></i> Added!';
                    btn.classList.add('bg-emerald-600');
                    setTimeout(() => {
                        btn.innerHTML = prev;
                        btn.classList.remove('bg-emerald-600');
                    }, 1000);
                }
            } else {
                alert(data.message || 'Unable to add item to cart.');
            }
        } catch (e) {
            console.error('Add cart error:', e);
            alert('Could not connect to the server to update cart.');
        } finally {
            if (btn) btn.disabled = false;
        }
    };
    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
await initUser();
    await Promise.all([
        loadMorningSurveyStatus(),
        loadRecommendations(),
        loadActiveOrders(),
        loadFoodBudgetSnapshot()
    ]);
});
