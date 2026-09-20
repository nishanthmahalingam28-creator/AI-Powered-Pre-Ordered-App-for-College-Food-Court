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

    let cashFlowChartInstance = null;
    let categoryChartInstance = null;

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

    // =============================================================
    // 5. Fetch Live Financial Intelligence & Spending Overview
    // =============================================================
    async function loadFinancialSummary() {
        const skeleton = document.getElementById('financial-loading-skeleton');
        const container = document.getElementById('financial-content-container');
        const errorBanner = document.getElementById('financial-error-banner');
        const errorText = document.getElementById('financial-error-text');
        const refreshIcon = document.getElementById('refresh-financials-icon');

        if (skeleton) skeleton.classList.remove('hidden');
        if (container) container.classList.add('hidden');
        if (errorBanner) errorBanner.classList.add('hidden');
        if (refreshIcon) refreshIcon.classList.add('animate-spin');

        try {
            const res = await fetch(`${API_BASE_URL}/customer/financial-summary`, {
                credentials: 'include'
            });

            if (res.status === 401) {
                sessionStorage.removeItem('foodCourtUser');
                window.location.href = '../auth/login.html';
                return;
            }

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || 'Failed to retrieve financial summary.');
            }

            const summary = data.summary || {};
            const budgets = data.budgets || [];
            const goals = data.goals || [];
            const recentTransactions = data.recent_transactions || [];
            const categoryBreakdown = data.category_breakdown || [];

            // 1. Update Core Metric Cards
            const incomeEl = document.getElementById('stat-dash-income');
            const expensesEl = document.getElementById('stat-dash-expenses');
            const balanceEl = document.getElementById('stat-dash-balance');
            const budgetEl = document.getElementById('stat-dash-budget');
            const budgetConsumedEl = document.getElementById('dash-budget-consumed-text');
            const incCountEl = document.getElementById('dash-income-count');
            const expCountEl = document.getElementById('dash-expense-count');
            const walletEl = document.getElementById('stat-dash-wallet');
            const savingsRateEl = document.getElementById('stat-dash-savings-rate');

            if (incomeEl) incomeEl.textContent = `₹${(summary.total_income || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (expensesEl) expensesEl.textContent = `₹${(summary.total_expenses || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (balanceEl) {
                const bal = summary.net_balance || 0;
                balanceEl.textContent = `₹${bal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                if (bal < 0) {
                    balanceEl.className = "text-2xl font-black text-rose-600 mt-0.5 block";
                } else {
                    balanceEl.className = "text-2xl font-black text-slate-900 mt-0.5 block";
                }
            }
            if (walletEl) {
                const wallet = summary.wallet_balance || 0;
                walletEl.textContent = `₹${wallet.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
            if (budgetEl) budgetEl.textContent = `₹${(summary.total_budget || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (budgetConsumedEl) {
                const pct = summary.budget_percent_spent || 0;
                const spent = (summary.total_budget_spent || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                budgetConsumedEl.textContent = `${pct}% allocated spent (₹${spent})`;
            }
            if (savingsRateEl) {
                const rate = summary.savings_rate !== undefined ? summary.savings_rate : 0;
                savingsRateEl.textContent = `${rate}%`;
                if (rate > 20) {
                    savingsRateEl.className = "text-2xl font-black text-emerald-600 mt-0.5 block";
                } else if (rate < 0) {
                    savingsRateEl.className = "text-2xl font-black text-rose-600 mt-0.5 block";
                } else {
                    savingsRateEl.className = "text-2xl font-black text-slate-900 mt-0.5 block";
                }
            }
            if (incCountEl) incCountEl.textContent = summary.counts?.income_entries ?? 0;
            if (expCountEl) expCountEl.textContent = summary.counts?.expense_entries ?? 0;

            // 2. Render Chart 1: Cash Flow Comparison
            const flowCanvas = document.getElementById('cashFlowChart');
            const flowEmpty = document.getElementById('cash-flow-empty');

            if (flowCanvas && typeof Chart !== 'undefined') {
                if (summary.total_income === 0 && summary.total_expenses === 0) {
                    flowCanvas.classList.add('hidden');
                    if (flowEmpty) flowEmpty.classList.remove('hidden');
                } else {
                    if (flowEmpty) flowEmpty.classList.add('hidden');
                    flowCanvas.classList.remove('hidden');

                    if (cashFlowChartInstance) {
                        cashFlowChartInstance.destroy();
                    }

                    const ctxFlow = flowCanvas.getContext('2d');
                    cashFlowChartInstance = new Chart(ctxFlow, {
                        type: 'bar',
                        data: {
                            labels: ['Total Income', 'Total Expenses', 'Net Balance'],
                            datasets: [{
                                data: [summary.total_income, summary.total_expenses, summary.net_balance],
                                backgroundColor: [
                                    'rgba(16, 185, 129, 0.85)',
                                    'rgba(244, 63, 94, 0.85)',
                                    'rgba(14, 165, 233, 0.85)'
                                ],
                                borderRadius: 8,
                                borderSkipped: false
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: {
                                    callbacks: {
                                        label: (ctx) => ` ₹${Number(ctx.raw).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: { callback: (val) => '₹' + val },
                                    grid: { color: 'rgba(226, 232, 240, 0.6)' }
                                },
                                x: { grid: { display: false } }
                            }
                        }
                    });
                }
            }

            // 3. Render Chart 2: Category Expense Breakdown
            const catCanvas = document.getElementById('categoryChart');
            const catEmpty = document.getElementById('category-chart-empty');

            if (catCanvas && typeof Chart !== 'undefined') {
                if (!categoryBreakdown || categoryBreakdown.length === 0) {
                    catCanvas.classList.add('hidden');
                    if (catEmpty) catEmpty.classList.remove('hidden');
                } else {
                    if (catEmpty) catEmpty.classList.add('hidden');
                    catCanvas.classList.remove('hidden');

                    if (categoryChartInstance) {
                        categoryChartInstance.destroy();
                    }

                    const ctxCat = catCanvas.getContext('2d');
                    categoryChartInstance = new Chart(ctxCat, {
                        type: 'doughnut',
                        data: {
                            labels: categoryBreakdown.map(c => c.category),
                            datasets: [{
                                data: categoryBreakdown.map(c => c.amount),
                                backgroundColor: [
                                    '#0d9488', '#06b6d4', '#3b82f6', '#8b5cf6',
                                    '#ec4899', '#f59e0b', '#10b981', '#64748b'
                                ],
                                borderWidth: 2,
                                borderColor: '#ffffff'
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    position: 'bottom',
                                    labels: { boxWidth: 10, font: { size: 11, weight: 'bold' } }
                                },
                                tooltip: {
                                    callbacks: {
                                        label: (ctx) => ` ${ctx.label}: ₹${Number(ctx.raw).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                                    }
                                }
                            },
                            cutout: '65%'
                        }
                    });
                }
            }

            // 4. Render Budgets List
            const budgetsListEl = document.getElementById('dash-budgets-list');
            const budgetsEmptyEl = document.getElementById('dash-budgets-empty');

            if (budgetsListEl) {
                if (budgets.length === 0) {
                    budgetsListEl.innerHTML = '';
                    if (budgetsEmptyEl) budgetsEmptyEl.classList.remove('hidden');
                } else {
                    if (budgetsEmptyEl) budgetsEmptyEl.classList.add('hidden');
                    budgetsListEl.innerHTML = '';
                    budgets.forEach(b => {
                        const badgeClass = b.status === 'exceeded'
                            ? 'bg-rose-100 text-rose-800 border-rose-200'
                            : b.status === 'near_limit'
                            ? 'bg-amber-100 text-amber-800 border-amber-200'
                            : 'bg-emerald-100 text-emerald-800 border-emerald-200';
                        const badgeText = b.status === 'exceeded'
                            ? 'Exceeded'
                            : b.status === 'near_limit'
                            ? 'Near Limit'
                            : 'On Track';
                        const barColor = b.status === 'exceeded'
                            ? 'bg-rose-500'
                            : b.status === 'near_limit'
                            ? 'bg-amber-500'
                            : 'bg-teal-500';

                        const div = document.createElement('div');
                        div.className = 'p-3.5 rounded-2xl bg-slate-50 border border-slate-200/70 hover:bg-slate-100/70 transition-colors';
                        div.innerHTML = `
                            <div class="flex items-center justify-between mb-1.5">
                                <div class="flex items-center gap-2">
                                    <span class="w-2.5 h-2.5 rounded-full ${barColor}"></span>
                                    <span class="font-bold text-xs text-slate-800">${escapeHtml(b.category)}</span>
                                </div>
                                <span class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase border ${badgeClass}">
                                    ${badgeText}
                                </span>
                            </div>
                            <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden mb-1.5">
                                <div class="${barColor} h-2 rounded-full transition-all duration-500" style="width: ${Math.min(100, b.percent_spent)}%"></div>
                            </div>
                            <div class="flex items-center justify-between text-[11px] text-slate-500 font-medium">
                                <span>Spent: <strong class="text-slate-800">₹${b.spent.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> of ₹${b.amount_limit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                <span>${b.percent_spent}%</span>
                            </div>
                        `;
                        budgetsListEl.appendChild(div);
                    });
                }
            }

            // 5. Render Goals List
            const goalsListEl = document.getElementById('dash-goals-list');
            const goalsEmptyEl = document.getElementById('dash-goals-empty');

            if (goalsListEl) {
                if (goals.length === 0) {
                    goalsListEl.innerHTML = '';
                    if (goalsEmptyEl) goalsEmptyEl.classList.remove('hidden');
                } else {
                    if (goalsEmptyEl) goalsEmptyEl.classList.add('hidden');
                    goalsListEl.innerHTML = '';
                    goals.forEach(g => {
                        const isDone = g.status === 'achieved' || g.current_amount >= g.target_amount;
                        const badgeClass = isDone
                            ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                            : 'bg-cyan-100 text-cyan-800 border-cyan-200';
                        const badgeText = isDone ? 'Achieved' : 'In Progress';

                        const div = document.createElement('div');
                        div.className = 'p-3.5 rounded-2xl bg-slate-50 border border-slate-200/70 hover:bg-slate-100/70 transition-colors';
                        div.innerHTML = `
                            <div class="flex items-center justify-between mb-1.5">
                                <div class="flex items-center gap-2">
                                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                                    <span class="font-bold text-xs text-slate-800">${escapeHtml(g.title)}</span>
                                </div>
                                <span class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase border ${badgeClass}">
                                    ${badgeText}
                                </span>
                            </div>
                            <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden mb-1.5">
                                <div class="bg-gradient-to-r from-teal-500 to-emerald-500 h-2 rounded-full transition-all duration-500" style="width: ${Math.min(100, g.progress_percent)}%"></div>
                            </div>
                            <div class="flex items-center justify-between text-[11px] text-slate-500 font-medium">
                                <span>Saved: <strong class="text-slate-800">₹${g.current_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> of ₹${g.target_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                <span>${g.progress_percent}%</span>
                            </div>
                        `;
                        goalsListEl.appendChild(div);
                    });
                }
            }

            // 6. Render Recent Transactions Table
            const txWrapper = document.getElementById('dash-transactions-wrapper');
            const txTbody = document.getElementById('dash-transactions-tbody');
            const txEmpty = document.getElementById('dash-transactions-empty');

            if (txTbody) {
                if (recentTransactions.length === 0) {
                    txTbody.innerHTML = '';
                    if (txWrapper) txWrapper.classList.add('hidden');
                    if (txEmpty) txEmpty.classList.remove('hidden');
                } else {
                    if (txEmpty) txEmpty.classList.add('hidden');
                    if (txWrapper) txWrapper.classList.remove('hidden');
                    txTbody.innerHTML = '';

                    recentTransactions.forEach(tx => {
                        const isIncome = tx.type === 'income';
                        const badgeClass = isIncome
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border-rose-200';
                        const iconClass = isIncome ? 'fa-arrow-down' : 'fa-arrow-up';
                        const typeLabel = isIncome ? 'Income' : 'Expense';
                        const amountSign = isIncome ? '+' : '-';
                        const amountColor = isIncome ? 'text-emerald-600' : 'text-rose-600';

                        const tr = document.createElement('tr');
                        tr.className = 'hover:bg-slate-50/80 transition-colors';
                        tr.innerHTML = `
                            <td class="py-3 px-3">
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border inline-flex items-center gap-1 ${badgeClass}">
                                    <i class="fa-solid ${iconClass} text-[9px]"></i> ${typeLabel}
                                </span>
                            </td>
                            <td class="py-3 px-3 font-bold text-slate-800">
                                ${escapeHtml(tx.category || 'Dining')}
                            </td>
                            <td class="py-3 px-3 text-slate-600">
                                ${escapeHtml(tx.description || '')}
                            </td>
                            <td class="py-3 px-3 text-slate-400 text-[11px]">
                                ${escapeHtml(tx.date || '')}
                            </td>
                            <td class="py-3 px-3 text-right font-black ${amountColor}">
                                ${amountSign}₹${Number(tx.amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                        `;
                        txTbody.appendChild(tr);
                    });
                }
            }

            if (skeleton) skeleton.classList.add('hidden');
            if (container) container.classList.remove('hidden');

        } catch (err) {
            console.error('Failed to load financial summary:', err);
            if (skeleton) skeleton.classList.add('hidden');
            if (container) container.classList.add('hidden');
            if (errorBanner) errorBanner.classList.remove('hidden');
            if (errorText) errorText.textContent = err.message || 'An error occurred while communicating with the database.';
        } finally {
            if (refreshIcon) refreshIcon.classList.remove('animate-spin');
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Bind Refresh and Retry buttons
    const refreshFinBtn = document.getElementById('refresh-financials-btn');
    if (refreshFinBtn) refreshFinBtn.addEventListener('click', loadFinancialSummary);

    const retryFinBtn = document.getElementById('retry-financials-btn');
    if (retryFinBtn) retryFinBtn.addEventListener('click', loadFinancialSummary);

    await initUser();
    await Promise.all([
        loadMorningSurveyStatus(),
        loadFinancialSummary(),
        loadRecommendations(),
        loadActiveOrders(),
        loadStalls()
    ]);
});
