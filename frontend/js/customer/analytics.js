/**
 * Customer Financial Analytics & Spending Intelligence Controller.
 * 
 * Directly queries authenticated backend database APIs:
 * - GET /api/customer/analytics
 * - POST /api/expenses & DELETE /api/expenses/:id
 * - POST /api/income & DELETE /api/income/:id
 * - GET /api/auth/me & POST /api/auth/logout
 * 
 * Enforces:
 * 1. Zero localStorage reliance (strict server database source of truth).
 * 2. Authenticated multi-tenant session isolation (credentials: "include").
 * 3. Graceful rendering of empty datasets with zero JavaScript errors.
 * 4. Real-time chart and metric synchronization upon adding or deleting transactions.
 * 5. Clean Chart.js instance destruction and memory management.
 */

document.addEventListener("DOMContentLoaded", async () => {
    // -------------------------------------------------------------
    // 1. API Configuration & Storage Sanitization
    // -------------------------------------------------------------
    const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "/api");

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

    // Chart.js Instances
    let monthlyTrendsChartInstance = null;
    let categoryExpenseChartInstance = null;
    let budgetComparisonChartInstance = null;

    // State
    let currentUser = null;

    // -------------------------------------------------------------
    // 2. Authentication & Session Verification
    // -------------------------------------------------------------
    async function verifyAuthentication() {
        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: "include" });
            if (!res.ok) {
                window.location.href = "../auth/login.html";
                return false;
            }
            const data = await res.json();
            if (!data.authenticated || !data.user || data.user.role !== "customer") {
                window.location.href = "../auth/login.html";
                return false;
            }
            currentUser = data.user;
            return true;
        } catch (err) {
            console.error("Session verification failed:", err);
            window.location.href = "../auth/login.html";
            return false;
        }
    }

    // Global logout handler
    window.handleCustomerLogout = async function () {
        try {
            await fetch(`${API_BASE_URL}/auth/logout`, {
                method: "POST",
                credentials: "include"
            });
        } catch (e) {
            console.warn("Logout error:", e);
        }
        sessionStorage.clear();
        try {
            localStorage.removeItem("expenses");
            localStorage.removeItem("income");
            localStorage.removeItem("budgets");
            localStorage.removeItem("goals");
        } catch (e) {}
        window.location.href = "../auth/login.html";
    };

    // -------------------------------------------------------------
    // 3. UI Helpers & Formatters
    // -------------------------------------------------------------
    function formatCurrency(val) {
        const num = Number(val) || 0;
        return "₹" + num.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function showAlert(message, isError = false) {
        const alertEl = document.getElementById("analytics-alert");
        const iconEl = document.getElementById("analytics-alert-icon");
        const textEl = document.getElementById("analytics-alert-text");

        if (!alertEl || !textEl || !iconEl) return;

        textEl.textContent = message;
        if (isError) {
            alertEl.className = "mb-6 p-4 rounded-2xl text-xs font-semibold flex items-center justify-between gap-3 shadow-sm bg-rose-50 border border-rose-200 text-rose-800";
            iconEl.className = "fa-solid fa-triangle-exclamation text-base shrink-0 text-rose-600";
        } else {
            alertEl.className = "mb-6 p-4 rounded-2xl text-xs font-semibold flex items-center justify-between gap-3 shadow-sm bg-teal-50 border border-teal-200 text-teal-800";
            iconEl.className = "fa-solid fa-circle-check text-base shrink-0 text-teal-600";
        }
        alertEl.classList.remove("hidden");
    }

    window.dismissAlert = function () {
        const alertEl = document.getElementById("analytics-alert");
        if (alertEl) alertEl.classList.add("hidden");
    };

    // -------------------------------------------------------------
    // 4. Fetch Analytics Data from Backend
    // -------------------------------------------------------------
    async function loadAnalyticsData() {
        const skeleton = document.getElementById("analytics-loading-skeleton");
        const contentShell = document.getElementById("analytics-content-shell");
        const refreshIcon = document.getElementById("refresh-icon");

        if (refreshIcon) refreshIcon.classList.add("fa-spin");

        try {
            const res = await fetch(`${API_BASE_URL}/customer/analytics`, {
                credentials: "include"
            });

            if (!res.ok) {
                throw new Error(`Server returned HTTP ${res.status}`);
            }

            const data = await res.json();
            if (!data.success) {
                throw new Error(data.message || "Failed to retrieve analytics.");
            }

            renderAnalytics(data);

            if (skeleton) skeleton.classList.add("hidden");
            if (contentShell) contentShell.classList.remove("hidden");
        } catch (err) {
            console.error("Failed to load analytics:", err);
            showAlert("Failed to load financial statistics from the server. Please check your connection and click Refresh.", true);
            if (skeleton) skeleton.classList.add("hidden");
            if (contentShell) contentShell.classList.remove("hidden");
        } finally {
            if (refreshIcon) refreshIcon.classList.remove("fa-spin");
        }
    }

    // -------------------------------------------------------------
    // 5. Render All Financial Visualizations & Metrics
    // -------------------------------------------------------------
    function renderAnalytics(data) {
        const summary = data.summary || {};
        const categoryExpenses = data.category_breakdown || [];
                const monthlyTrends = data.monthly_trends || [];
        const budgetComparisons = data.budget_comparisons || [];
        const goals = data.goals || [];
        const recentTransactions = data.recent_transactions || [];

        const hasAnyData = (summary.total_expenses > 0) ||
                           (recentTransactions.length > 0) || (budgetComparisons.length > 0);

        const emptyBanner = document.getElementById("analytics-empty-state");
        const chartsSection = document.getElementById("charts-grid-section");

        if (!hasAnyData) {
            if (emptyBanner) emptyBanner.classList.remove("hidden");
        } else {
            if (emptyBanner) emptyBanner.classList.add("hidden");
        }

        // 1. Metric Cards
        renderMetricCards(summary);

        // 2. Monthly Trends Chart
        renderMonthlyTrendsChart(monthlyTrends);

        // 3. Category Expenses Doughnut Chart
        renderCategoryExpenseChart(categoryExpenses, summary.total_expenses);

        // 5. Budget Comparison Chart
        renderBudgetComparisonChart(budgetComparisons, summary);

        // 6. Category Budgets Table
        renderBudgetTable(budgetComparisons);

        // 7. Financial Goals Grid
        renderGoalsGrid(goals);

        // 8. Recent Transactions Table
        renderRecentTransactions(recentTransactions);
    }

    // -------------------------------------------------------------
    // 6. Metric Cards Renderer
    // -------------------------------------------------------------
    function renderMetricCards(summary) {
        const elTotalExpenses = document.getElementById("metric-total-expenses");
        const elExpenseCount = document.getElementById("metric-expense-count");
        const elAvgExpense = document.getElementById("metric-avg-expense");
        const elBudgetPercent = document.getElementById("metric-budget-percent");
        const elBudgetCounts = document.getElementById("metric-budget-counts");
        const elBudgetStatusLabel = document.getElementById("metric-budget-status-label");

        const elGoalsPercent = document.getElementById("metric-goals-percent");
        const elGoalsCounts = document.getElementById("metric-goals-counts");
        const elGoalsSavedTotal = document.getElementById("metric-goals-saved-total");
        if (elTotalExpenses) elTotalExpenses.textContent = formatCurrency(summary.total_expenses || 0);
        if (elExpenseCount) elExpenseCount.textContent = `${summary.counts?.expense_entries || 0} purchases`;
        if (elAvgExpense) elAvgExpense.textContent = `avg ${formatCurrency(summary.average_expense || 0)}`;const bPct = Number(summary.budget_percent_spent || 0);
        if (elBudgetPercent) elBudgetPercent.textContent = `${Math.round(bPct)}%`;
        if (elBudgetCounts) elBudgetCounts.textContent = `${summary.counts?.active_budgets || 0} active budgets`;
        if (elBudgetStatusLabel) {
            if (bPct > 100) {
                elBudgetStatusLabel.textContent = "Exceeded";
                elBudgetStatusLabel.className = "text-rose-600 font-semibold";
            } else if (bPct >= 80) {
                elBudgetStatusLabel.textContent = "Near Limit";
                elBudgetStatusLabel.className = "text-amber-600 font-semibold";
            } else {
                elBudgetStatusLabel.textContent = "On Track";
                elBudgetStatusLabel.className = "text-indigo-600 font-semibold";
            }
        }

        const gPct = Number(summary.goals_overall_progress || 0);
        if (elGoalsPercent) elGoalsPercent.textContent = `${Math.round(gPct)}%`;
        if (elGoalsCounts) elGoalsCounts.textContent = `${summary.counts?.active_goals || 0} active goals`;
        if (elGoalsSavedTotal) elGoalsSavedTotal.textContent = `${formatCurrency(summary.total_goals_saved || 0)} saved`;
    }

    // -------------------------------------------------------------
    // 7. Monthly Trends Chart (Chart 1)
    // -------------------------------------------------------------
    function renderMonthlyTrendsChart(trends) {
        const canvas = document.getElementById("monthlyTrendsChart");
        const emptyEl = document.getElementById("monthly-trends-empty");
        if (!canvas || typeof Chart === "undefined") return;

        if (!trends || trends.length === 0) {
            canvas.classList.add("hidden");
            if (emptyEl) emptyEl.classList.remove("hidden");
            if (monthlyTrendsChartInstance) {
                monthlyTrendsChartInstance.destroy();
                monthlyTrendsChartInstance = null;
            }
            return;
        }

        canvas.classList.remove("hidden");
        if (emptyEl) emptyEl.classList.add("hidden");

        if (monthlyTrendsChartInstance) {
            monthlyTrendsChartInstance.destroy();
        }

        const labels = trends.map(t => t.label || t.month);        const expenseData = trends.map(t => t.expenses);
        const netData = trends.map(t => t.net_savings);

        const ctx = canvas.getContext("2d");
        monthlyTrendsChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        type: "bar",
                        label: "Expenses",
                        data: expenseData,
                        backgroundColor: "#f43f5e",
                        borderRadius: 8,
                        order: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.dataset.label}: ₹${Number(ctx.raw).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (val) => "₹" + val },
                        grid: { color: "rgba(226, 232, 240, 0.6)" }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // -------------------------------------------------------------
    // 8. Expense Category Breakdown Chart (Chart 2)
    // -------------------------------------------------------------
    function renderCategoryExpenseChart(categories, totalExpenses) {
        const canvas = document.getElementById("categoryExpenseChart");
        const emptyEl = document.getElementById("category-expense-empty");
        const legendEl = document.getElementById("category-expense-legend");
        if (!canvas || typeof Chart === "undefined") return;

        if (!categories || categories.length === 0 || totalExpenses <= 0) {
            canvas.classList.add("hidden");
            if (emptyEl) emptyEl.classList.remove("hidden");
            if (legendEl) legendEl.innerHTML = '<p class="text-slate-400 text-center text-xs">No categorized expenses</p>';
            if (categoryExpenseChartInstance) {
                categoryExpenseChartInstance.destroy();
                categoryExpenseChartInstance = null;
            }
            return;
        }

        canvas.classList.remove("hidden");
        if (emptyEl) emptyEl.classList.add("hidden");

        if (categoryExpenseChartInstance) {
            categoryExpenseChartInstance.destroy();
        }

        const colors = [
            "#0d9488", "#06b6d4", "#3b82f6", "#8b5cf6",
            "#ec4899", "#f59e0b", "#10b981", "#64748b"
        ];

        const ctx = canvas.getContext("2d");
        categoryExpenseChartInstance = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: categories.map(c => c.category),
                datasets: [{
                    data: categories.map(c => c.amount),
                    backgroundColor: colors.slice(0, categories.length),
                    borderWidth: 2,
                    borderColor: "#ffffff"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.label}: ₹${Number(ctx.raw).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
                        }
                    }
                },
                cutout: "68%"
            }
        });

        // Render custom legend
        if (legendEl) {
            legendEl.innerHTML = categories.map((cat, idx) => {
                const color = colors[idx % colors.length];
                return `
                    <div class="flex items-center justify-between text-xs py-0.5">
                        <div class="flex items-center gap-2 truncate">
                            <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: ${color}"></span>
                            <span class="font-bold text-slate-700 truncate">${escapeHtml(cat.category)}</span>
                        </div>
                        <div class="flex items-center gap-2 font-bold shrink-0">
                            <span class="text-slate-900">${formatCurrency(cat.amount)}</span>
                            <span class="text-slate-400 text-[10px] w-10 text-right">${cat.percentage}%</span>
                        </div>
                    </div>
                `;
            }).join("");
        }
    }

    // -------------------------------------------------------------
    // 9. Budget Comparison Chart
    // -------------------------------------------------------------
    function renderBudgetComparisonChart(budgets, summary) {
        const canvas = document.getElementById("budgetComparisonChart");
        const emptyEl = document.getElementById("budget-comparison-empty");
        const limitSummaryEl = document.getElementById("budget-total-limit-text");
        const spentSummaryEl = document.getElementById("budget-total-spent-text");
        if (!canvas || typeof Chart === "undefined") return;

        if (limitSummaryEl) limitSummaryEl.textContent = `Total Limit: ${formatCurrency(summary.total_budget || 0)}`;
        if (spentSummaryEl) spentSummaryEl.textContent = `Total Spent: ${formatCurrency(summary.total_budget_spent || 0)}`;

        if (!budgets || budgets.length === 0) {
            canvas.classList.add("hidden");
            if (emptyEl) emptyEl.classList.remove("hidden");
            if (budgetComparisonChartInstance) {
                budgetComparisonChartInstance.destroy();
                budgetComparisonChartInstance = null;
            }
            return;
        }

        canvas.classList.remove("hidden");
        if (emptyEl) emptyEl.classList.add("hidden");

        if (budgetComparisonChartInstance) {
            budgetComparisonChartInstance.destroy();
        }

        const labels = budgets.map(b => b.category);
        const limits = budgets.map(b => b.amount_limit);
        const spents = budgets.map(b => b.spent);

        const ctx = canvas.getContext("2d");
        budgetComparisonChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Budget Limit",
                        data: limits,
                        backgroundColor: "rgba(99, 102, 241, 0.25)",
                        borderColor: "#6366f1",
                        borderWidth: 1.5,
                        borderRadius: 6
                    },
                    {
                        label: "Actual Spent",
                        data: spents,
                        backgroundColor: spents.map((s, idx) => s > limits[idx] ? "#ef4444" : "#0d9488"),
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "top",
                        labels: { boxWidth: 10, font: { size: 10, weight: "bold" } }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => ` ${ctx.dataset.label}: ₹${Number(ctx.raw).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (val) => "₹" + val },
                        grid: { color: "rgba(226, 232, 240, 0.6)" }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // -------------------------------------------------------------
    // 11. Category Budgets Table Renderer
    // -------------------------------------------------------------
    function renderBudgetTable(budgets) {
        const tbody = document.getElementById("budget-table-body");
        if (!tbody) return;

        if (!budgets || budgets.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="py-8 text-center text-slate-400 font-medium">
                        No category budgets configured yet. <a href="budgets.html" class="text-teal-600 font-bold hover:underline">Add a Budget</a>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = budgets.map(b => {
            const pct = Math.min(100, Math.max(0, b.percent_spent || 0));
            let badgeHtml = "";
            let barColor = "bg-teal-500";

            if (b.status === "exceeded") {
                badgeHtml = `<span class="px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-200">Exceeded</span>`;
                barColor = "bg-rose-500";
            } else if (b.status === "near_limit") {
                badgeHtml = `<span class="px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200">Near Limit</span>`;
                barColor = "bg-amber-500";
            } else {
                badgeHtml = `<span class="px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">On Track</span>`;
                barColor = "bg-teal-500";
            }

            return `
                <tr class="hover:bg-slate-50/75 transition-colors">
                    <td class="py-3.5 px-4 font-bold text-slate-900">${escapeHtml(b.category)}</td>
                    <td class="py-3.5 px-4 font-bold text-slate-700">${formatCurrency(b.amount_limit)}</td>
                    <td class="py-3.5 px-4 font-bold text-slate-900">${formatCurrency(b.spent)}</td>
                    <td class="py-3.5 px-4 font-bold ${b.remaining <= 0 ? 'text-rose-600' : 'text-emerald-700'}">${formatCurrency(b.remaining)}</td>
                    <td class="py-3.5 px-4">
                        <div class="flex items-center gap-3">
                            <div class="w-28 bg-slate-100 rounded-full h-2 overflow-hidden">
                                <div class="${barColor} h-2 rounded-full transition-all duration-500" style="width: ${pct}%"></div>
                            </div>
                            <span class="text-[11px] font-bold text-slate-500 w-10">${b.percent_spent}%</span>
                        </div>
                    </td>
                    <td class="py-3.5 px-4 text-center">${badgeHtml}</td>
                </tr>
            `;
        }).join("");
    }

    // -------------------------------------------------------------
    // 12. Financial Goals Grid Renderer
    // -------------------------------------------------------------
    function renderGoalsGrid(goals) {
        const container = document.getElementById("goals-grid-container");
        if (!container) return;

        if (!goals || goals.length === 0) {
            container.innerHTML = `
                <div class="col-span-full py-8 text-center text-slate-400 font-medium bg-slate-50 rounded-2xl border border-slate-200/60">
                    No financial goals active. <a href="budgets.html#goals-section" class="text-purple-600 font-bold hover:underline">Set a savings goal</a> to track your milestones!
                </div>
            `;
            return;
        }

        container.innerHTML = goals.map(g => {
            const pct = Math.min(100, Math.max(0, g.progress_percent || 0));
            return `
                <div class="bg-slate-50/80 rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between gap-2 mb-2">
                            <h4 class="text-sm font-black text-slate-900 truncate">${escapeHtml(g.title)}</h4>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-purple-100 text-purple-800 shrink-0">
                                ${escapeHtml(g.category || 'General')}
                            </span>
                        </div>
                        <div class="flex items-baseline justify-between text-xs mt-3 mb-1.5">
                            <span class="font-bold text-slate-900">${formatCurrency(g.current_amount)}</span>
                            <span class="text-slate-400">target ${formatCurrency(g.target_amount)}</span>
                        </div>
                        <div class="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                            <div class="bg-gradient-to-r from-purple-500 to-indigo-500 h-2.5 rounded-full transition-all duration-500" style="width: ${pct}%"></div>
                        </div>
                    </div>
                    <div class="mt-4 pt-3 border-t border-slate-200/60 flex items-center justify-between text-[11px] text-slate-500 font-medium">
                        <span>${g.progress_percent}% achieved</span>
                        <span>${g.target_date ? 'By ' + escapeHtml(g.target_date) : 'Ongoing'}</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    // -------------------------------------------------------------
    // 13. Recent Transactions Ledger & Delete Buttons
    // -------------------------------------------------------------
    function renderRecentTransactions(transactions) {
        const tbody = document.getElementById("recent-transactions-body");
        if (!tbody) return;

        if (!transactions || transactions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="py-8 text-center text-slate-400 font-medium">
                        No transactions recorded yet. Use the buttons above to log your first transaction.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = transactions.map(tx => {
            const isExpense = tx.type === "expense";
            const badgeClass = isExpense
                ? "bg-rose-100 text-rose-800 border-rose-200"
                : "bg-emerald-100 text-emerald-800 border-emerald-200";
            const typeLabel = "Expense";
            const sign = isExpense ? "-" : "+";
            const amountClass = "text-slate-900 font-black";

            return `
                <tr class="hover:bg-slate-50/75 transition-colors">
                    <td class="py-3.5 px-4">
                        <span class="px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider border ${badgeClass}">
                            ${typeLabel}
                        </span>
                    </td>
                    <td class="py-3.5 px-4 text-slate-500 font-medium whitespace-nowrap">${escapeHtml(tx.date || tx.created_at?.slice(0, 10) || "")}</td>
                    <td class="py-3.5 px-4 font-bold text-slate-800">${escapeHtml(tx.category || "General")}</td>
                    <td class="py-3.5 px-4 text-slate-600 max-w-xs truncate">${escapeHtml(tx.description || "-")}</td>
                    <td class="py-3.5 px-4 text-right ${amountClass}">${sign}${formatCurrency(tx.amount)}</td>
                    <td class="py-3.5 px-4 text-center">
                        <button
                            onclick="requestDeleteTransaction('${tx.type}', ${tx.id})"
                            class="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition-all cursor-pointer"
                            title="Delete transaction and refresh charts"
                        >
                            <i class="fa-solid fa-trash-can text-xs"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // -------------------------------------------------------------
    // 14. Transaction Deletion Flow (Real-time update)
    // -------------------------------------------------------------

    // -------------------------------------------------------------
    // 16. Initialize Flow
    // -------------------------------------------------------------
    const isAuth = await verifyAuthentication();
    if (isAuth) {
        await loadAnalyticsData();
    }
});
