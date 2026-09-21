function formatOrderDateTime(value) {
    const raw = String(value || '').trim();
    if (!raw) return '—';
    let normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) normalized += 'Z';
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return raw;
    return new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    }).format(date);
}

document.addEventListener('DOMContentLoaded', async () => {
    // The shared customer-workspace-mobile.js owns the 0-640px menu
    // on every customer/student workspace page.
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

        const customerType = String(user.customer_type || 'student').toLowerCase();
        const customerTypeLabel = customerType === 'faculty'
            ? 'Faculty'
            : customerType === 'guest'
                ? 'Guest'
                : 'Student';

        const nameEl = document.getElementById('customer-name');
        if (nameEl && user.full_name) nameEl.textContent = user.full_name;

        // Use the same dashboard experience for Student, Faculty, and Guest.
        // Guest accounts do not use the Food Budget feature.
        const foodBudgetSnapshot = document.getElementById('food-budget-snapshot');
        const foodBudgetNav = document.querySelector('[data-workspace-link="budgets.html"]');
        if (customerType === 'guest') {
            if (foodBudgetSnapshot) foodBudgetSnapshot.classList.add('hidden');
            if (foodBudgetNav) foodBudgetNav.remove();
        } else {
            if (foodBudgetSnapshot) foodBudgetSnapshot.classList.remove('hidden');
            if (foodBudgetNav) foodBudgetNav.classList.remove('hidden');
        }

        const workspaceLabel = document.querySelector('.customer-workspace-header-label');
        if (workspaceLabel) workspaceLabel.textContent = customerTypeLabel + ' workspace';

        const pageTitle = document.getElementById('customer-workspace-page-title');
        if (pageTitle) pageTitle.textContent = 'Dashboard';

        // Customer workspace identity
        const displayName = user.full_name || customerTypeLabel;
        const sidebarName = document.getElementById('sidebar-user-name');
        const sidebarType = document.getElementById('sidebar-user-type');
        const sidebarAvatar = document.getElementById('sidebar-avatar');
        const topbarAvatar = document.getElementById('topbar-avatar');
        const topbarType = document.getElementById('topbar-customer-type');
        if (sidebarName) sidebarName.textContent = displayName;
        if (sidebarType) sidebarType.textContent = customerTypeLabel.toUpperCase();
        if (sidebarAvatar) sidebarAvatar.textContent = displayName.charAt(0).toUpperCase();
        if (topbarAvatar) topbarAvatar.textContent = displayName.charAt(0).toUpperCase();
        if (topbarType) topbarType.textContent = customerTypeLabel;


        const badgeEl = document.getElementById('customer-type-badge');
        if (badgeEl && user.customer_type) {
            badgeEl.textContent = customerTypeLabel.toUpperCase();
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

    // Load today's vendor-published Morning Survey status.
    // This uses the same survey source as the Morning Survey page.
    async function loadMorningSurveyStatus() {
        const bannerBadge = document.getElementById('survey-banner-badge');
        const bannerTitle = document.getElementById('survey-banner-title');
        const bannerSubtitle = document.getElementById('survey-banner-subtitle');
        const bannerBtn = document.getElementById('survey-banner-btn');
        const bannerIcon = document.getElementById('survey-banner-icon');

        try {
            const res = await fetch(API_BASE_URL + '/customer/morning-poll/today', { credentials: 'include' });
            if (!res.ok) return;
            const data = await res.json();
            if (!data.success) return;

            const surveys = Array.isArray(data.surveys) ? data.surveys : [];
            const published = surveys.length > 0;
            const completedCount = surveys.filter(s => Boolean(s.voted)).length;
            const completed = published && completedCount === surveys.length;

            if (!published) {
                if (bannerBadge) {
                    bannerBadge.textContent = 'Not Published';
                    bannerBadge.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200';
                }
                if (bannerTitle) bannerTitle.textContent = 'Morning Survey Not Published Yet';
                if (bannerSubtitle) bannerSubtitle.textContent = "Your food-court stalls have not published today's survey yet.";
                if (bannerBtn) {
                    bannerBtn.href = 'morning-survey.html';
                    bannerBtn.innerHTML = '<span>View Morning Survey</span><i class="fa-solid fa-arrow-right text-xs"></i>';
                    bannerBtn.className = 'bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl border border-slate-300 transition-all flex items-center gap-2';
                }
                if (bannerIcon) {
                    bannerIcon.className = 'w-12 h-12 rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center text-xl font-bold shrink-0';
                    bannerIcon.innerHTML = '<i class="fa-solid fa-calendar-day"></i>';
                }
                return;
            }

            if (bannerBadge) {
                bannerBadge.textContent = completed ? 'Survey Completed ✓' : (completedCount + '/' + surveys.length + ' Shops Completed');
                bannerBadge.className = completed
                    ? 'px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : 'px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-300';
            }
            if (bannerTitle) bannerTitle.textContent = completed ? "Today's Morning Survey Completed" : "Complete Today's Morning Survey";
            if (bannerSubtitle) {
                const remaining = surveys.length - completedCount;
                bannerSubtitle.textContent = completed
                    ? 'Your choices from ' + surveys.length + ' published shop surveys are now available to the AI recommendation engine.'
                    : 'Submit your food choice for ' + remaining + ' remaining shop survey' + (remaining === 1 ? '' : 's') + '. Your choices will personalize recommendations.';
            }
            if (bannerBtn) {
                bannerBtn.href = 'morning-survey.html';
                bannerBtn.innerHTML = '<span>' + (completed ? 'Review Survey' : 'Complete Morning Survey') + '</span><i class="fa-solid fa-arrow-right text-xs"></i>';
                bannerBtn.className = completed
                    ? 'bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl border border-slate-300 transition-all flex items-center gap-2'
                    : 'bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 text-white font-bold text-xs uppercase tracking-wider px-5 py-3 rounded-xl shadow-md transition-all flex items-center gap-2';
            }
            if (bannerIcon) {
                bannerIcon.className = completed
                    ? 'w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl font-bold shrink-0'
                    : 'w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl font-bold shrink-0';
                bannerIcon.innerHTML = completed ? '<i class="fa-solid fa-circle-check"></i>' : '<i class="fa-solid fa-sun"></i>';
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

    // 3. Load the same Food Budget/Spent calculation used by the Food Budget page.
    // Dashboard has no period selector, so it mirrors the Food Budget page's
    // default/current Monthly period and only counts Food expenses in this month.
    async function loadFoodBudgetSnapshot() {
        try {
            const [budgetRes, expenseRes] = await Promise.all([
                fetch(`${API_BASE_URL}/budgets`, { credentials: 'include' }),
                fetch(`${API_BASE_URL}/expenses`, { credentials: 'include' })
            ]);

            if (!budgetRes.ok || !expenseRes.ok) return;

            const budgetData = await budgetRes.json();
            const expenseData = await expenseRes.json();
            if (!budgetData.success) return;

            const budgets = Array.isArray(budgetData.budgets) ? budgetData.budgets : [];
            const monthlyBudget = budgets.find(
                b => String(b.period || '').toLowerCase() === 'monthly'
            );
            const budget = Number(monthlyBudget?.amount_limit || 0);

            const now = new Date();
            const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
            const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1);
            const toDate = value => {
                const d = new Date(String(value || '').slice(0, 10) + 'T00:00:00');
                return Number.isNaN(d.getTime()) ? null : d;
            };

            const expenses = Array.isArray(expenseData.expenses) ? expenseData.expenses : [];
            const spent = expenses
                .filter(expense => {
                    const category = String(expense.category || '').trim().toLowerCase();
                    const date = toDate(expense.expense_date || expense.date);
                    return category === 'food' &&
                        date &&
                        date >= monthStart &&
                        date < nextMonthStart;
                })
                .reduce((total, expense) => total + Number(expense.amount || 0), 0);

            const remaining = Math.max(0, budget - spent);
            const money = value => `₹${Number(value || 0).toFixed(2)}`;

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
                                <span class="text-[11px] text-slate-400">Ordered: ${formatOrderDateTime(order.created_at)}</span>
                            </div>
                        `;
                        container.appendChild(card);
                    });
                    return;
                }
            }

            // A completed/cancelled order must disappear from the Active Pre-Order
            // section as soon as the realtime status event refreshes this function.
            if (container) {
                container.innerHTML = `
                    <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm text-center text-slate-400 py-8">
                        <i class="fa-regular fa-clock text-3xl mb-2 text-slate-300"></i>
                        <p class="text-sm font-semibold">No active orders right now.</p>
                        <a href="menu.html" class="inline-block mt-3 text-xs font-bold text-teal-700 hover:underline">Browse stalls to order →</a>
                    </div>
                `;
            }
        } catch (e) {}
    }
    window.refreshRealtimeOrderData = loadActiveOrders;

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
