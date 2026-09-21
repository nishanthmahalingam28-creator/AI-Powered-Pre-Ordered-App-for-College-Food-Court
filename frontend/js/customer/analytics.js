document.addEventListener("DOMContentLoaded", async () => {
    "use strict";

    const API_BASE_URL =
        window.FOOD_COURT_API_BASE ||
        (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "/api");

    let monthlyChart = null;
    let categoryChart = null;
    let budgetChart = null;

    const money = (value) => "₹" + (Number(value) || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });

    const escapeHtml = (value) => String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    function showAlert(message, error = false) {
        const box = document.getElementById("analytics-alert");
        const icon = document.getElementById("analytics-alert-icon");
        const text = document.getElementById("analytics-alert-text");
        if (!box || !icon || !text) return;

        box.className = "mb-5 rounded-2xl p-4 text-xs font-semibold flex items-center justify-between gap-3 " +
            (error
                ? "bg-rose-50 border border-rose-200 text-rose-800"
                : "bg-teal-50 border border-teal-200 text-teal-800");

        icon.className = error
            ? "fa-solid fa-triangle-exclamation text-rose-600"
            : "fa-solid fa-circle-check text-teal-600";

        text.textContent = message;
        box.classList.remove("hidden");
    }

    window.dismissAlert = function () {
        const box = document.getElementById("analytics-alert");
        if (box) box.classList.add("hidden");
    };

    async function verifyAuthentication() {
        try {
            const response = await fetch(API_BASE_URL + "/auth/me", { credentials: "include" });
            if (!response.ok) throw new Error("Authentication failed");

            const data = await response.json();
            if (!data.authenticated || !data.user || data.user.role !== "customer") {
                window.location.href = "../auth/login.html";
                return false;
            }
            return true;
        } catch (error) {
            console.error("Analytics authentication error:", error);
            window.location.href = "../auth/login.html";
            return false;
        }
    }

    function renderMetricCards(summary) {
        const total = Number(summary.total_expenses) || 0;
        const count = Number(summary.counts?.expense_entries) || 0;
        const average = Number(summary.average_expense) || 0;
        const budgetPercent = Number(summary.budget_percent_spent) || 0;
        const activeBudgets = Number(summary.counts?.active_budgets) || 0;
        const goalsPercent = Number(summary.goals_overall_progress) || 0;
        const activeGoals = Number(summary.counts?.active_goals) || 0;
        const goalsSaved = Number(summary.total_goals_saved) || 0;

        document.getElementById("metric-total-expenses").textContent = money(total);
        document.getElementById("metric-expense-count").textContent = count + (count === 1 ? " purchase" : " purchases");
        document.getElementById("metric-avg-expense").textContent = money(average);
        document.getElementById("metric-budget-percent").textContent = Math.round(budgetPercent) + "%";
        document.getElementById("metric-budget-counts").textContent = activeBudgets + " active " + (activeBudgets === 1 ? "budget" : "budgets");

        const budgetStatus = document.getElementById("metric-budget-status-label");
        if (budgetStatus) {
            budgetStatus.textContent = budgetPercent > 100 ? "Exceeded" : budgetPercent >= 80 ? "Near Limit" : "On Track";
            budgetStatus.className = budgetPercent > 100
                ? "text-rose-600 font-semibold"
                : budgetPercent >= 80
                    ? "text-amber-600 font-semibold"
                    : "text-emerald-600 font-semibold";
        }

        document.getElementById("metric-goals-percent").textContent = Math.round(goalsPercent) + "%";
        document.getElementById("metric-goals-counts").textContent = activeGoals + " active " + (activeGoals === 1 ? "goal" : "goals");
        document.getElementById("metric-goals-saved-total").textContent = money(goalsSaved) + " saved";
    }

    function renderMonthlyChart(trends) {
        const canvas = document.getElementById("monthlyTrendsChart");
        const empty = document.getElementById("monthly-trends-empty");
        if (!canvas || typeof Chart === "undefined") return;

        if (monthlyChart) {
            monthlyChart.destroy();
            monthlyChart = null;
        }

        if (!Array.isArray(trends) || trends.length === 0) {
            canvas.classList.add("hidden");
            empty?.classList.remove("hidden");
            return;
        }

        canvas.classList.remove("hidden");
        empty?.classList.add("hidden");

        monthlyChart = new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: trends.map(item => item.label || item.month || ""),
                datasets: [{
                    label: "Spent",
                    data: trends.map(item => Number(item.expenses) || 0),
                    backgroundColor: "#0d9488",
                    borderRadius: 8,
                    maxBarThickness: 48
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: context => " Spent: " + money(context.raw)
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: value => "₹" + Number(value).toLocaleString("en-IN") },
                        grid: { color: "rgba(226,232,240,.65)" }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    function renderCategoryChart(categories, total) {
        const canvas = document.getElementById("categoryExpenseChart");
        const empty = document.getElementById("category-expense-empty");
        const legend = document.getElementById("category-expense-legend");
        if (!canvas || typeof Chart === "undefined") return;

        if (categoryChart) {
            categoryChart.destroy();
            categoryChart = null;
        }

        if (!Array.isArray(categories) || categories.length === 0 || total <= 0) {
            canvas.classList.add("hidden");
            empty?.classList.remove("hidden");
            if (legend) legend.innerHTML = "";
            return;
        }

        canvas.classList.remove("hidden");
        empty?.classList.add("hidden");

        const palette = ["#0d9488", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#64748b"];

        categoryChart = new Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: categories.map(item => item.category || "Other"),
                datasets: [{
                    data: categories.map(item => Number(item.amount) || 0),
                    backgroundColor: categories.map((_, index) => palette[index % palette.length]),
                    borderColor: "#ffffff",
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: context => " " + context.label + ": " + money(context.raw)
                        }
                    }
                }
            }
        });

        if (legend) {
            legend.innerHTML = categories.map((item, index) => {
                const color = palette[index % palette.length];
                const percent = Number(item.percentage) || 0;
                return '<div class="flex items-center justify-between gap-3 text-xs">' +
                    '<div class="flex items-center gap-2 min-w-0">' +
                    '<span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:' + color + '"></span>' +
                    '<span class="font-bold text-slate-700 truncate">' + escapeHtml(item.category || "Other") + '</span>' +
                    '</div><span class="text-slate-500 font-semibold shrink-0">' + percent.toFixed(1) + '%</span></div>';
            }).join("");
        }
    }

    function renderBudgetChart(budgets, summary) {
        const canvas = document.getElementById("budgetComparisonChart");
        const empty = document.getElementById("budget-comparison-empty");
        if (!canvas || typeof Chart === "undefined") return;

        document.getElementById("budget-total-limit-text").textContent =
            "Total Limit: " + money(summary.total_budget || 0);
        document.getElementById("budget-total-spent-text").textContent =
            "Total Spent: " + money(summary.total_budget_spent || 0);

        if (budgetChart) {
            budgetChart.destroy();
            budgetChart = null;
        }

        if (!Array.isArray(budgets) || budgets.length === 0) {
            canvas.classList.add("hidden");
            empty?.classList.remove("hidden");
            return;
        }

        canvas.classList.remove("hidden");
        empty?.classList.add("hidden");

        budgetChart = new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: budgets.map(item => item.category || "Other"),
                datasets: [
                    {
                        label: "Budget Limit",
                        data: budgets.map(item => Number(item.amount_limit) || 0),
                        backgroundColor: "rgba(99,102,241,.20)",
                        borderColor: "#6366f1",
                        borderWidth: 1.5,
                        borderRadius: 6
                    },
                    {
                        label: "Actual Spent",
                        data: budgets.map(item => Number(item.spent) || 0),
                        backgroundColor: budgets.map(item => Number(item.spent) > Number(item.amount_limit) ? "#ef4444" : "#0d9488"),
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top", labels: { boxWidth: 10, font: { size: 10, weight: "bold" } } },
                    tooltip: {
                        callbacks: {
                            label: context => " " + context.dataset.label + ": " + money(context.raw)
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: value => "₹" + Number(value).toLocaleString("en-IN") },
                        grid: { color: "rgba(226,232,240,.65)" }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    function renderBudgetTable(budgets) {
        const body = document.getElementById("budget-table-body");
        if (!body) return;

        if (!Array.isArray(budgets) || budgets.length === 0) {
            body.innerHTML = '<tr><td colspan="6" class="py-8 text-center text-slate-400">No category budgets configured yet. <a href="budgets.html" class="text-teal-600 font-bold">Create a budget</a>.</td></tr>';
            return;
        }

        body.innerHTML = budgets.map(item => {
            const limit = Number(item.amount_limit) || 0;
            const spent = Number(item.spent) || 0;
            const remaining = Number(item.remaining);
            const percent = Math.max(0, Number(item.percent_spent) || 0);
            const status = item.status === "exceeded" ? "Exceeded" : item.status === "near_limit" ? "Near Limit" : "On Track";
            const statusClass = item.status === "exceeded"
                ? "bg-rose-100 text-rose-700"
                : item.status === "near_limit"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-emerald-100 text-emerald-700";
            const barClass = item.status === "exceeded" ? "bg-rose-500" : item.status === "near_limit" ? "bg-amber-500" : "bg-teal-500";

            return '<tr class="hover:bg-slate-50">' +
                '<td class="py-3 px-3 font-bold text-slate-900">' + escapeHtml(item.category || "Other") + '</td>' +
                '<td class="py-3 px-3 font-semibold">' + money(limit) + '</td>' +
                '<td class="py-3 px-3 font-semibold">' + money(spent) + '</td>' +
                '<td class="py-3 px-3 font-semibold ' + (remaining <= 0 ? "text-rose-600" : "text-emerald-700") + '">' + money(remaining) + '</td>' +
                '<td class="py-3 px-3"><div class="flex items-center gap-2"><div class="w-24 h-2 bg-slate-100 rounded-full overflow-hidden"><div class="' + barClass + ' h-full rounded-full" style="width:' + Math.min(100, percent) + '%"></div></div><span class="text-[10px] font-bold text-slate-500">' + percent.toFixed(1) + '%</span></div></td>' +
                '<td class="py-3 px-3 text-center"><span class="inline-flex px-2.5 py-1 rounded-full text-[10px] font-black ' + statusClass + '">' + status + '</span></td>' +
                '</tr>';
        }).join("");
    }

    function renderGoals(goals) {
        const grid = document.getElementById("goals-grid-container");
        if (!grid) return;

        if (!Array.isArray(goals) || goals.length === 0) {
            grid.innerHTML = '<div class="col-span-full rounded-2xl bg-slate-50 border border-slate-200 p-8 text-center text-xs text-slate-400">No financial goals active. <a href="budgets.html#goals-section" class="text-purple-600 font-bold">Create a savings goal</a>.</div>';
            return;
        }

        grid.innerHTML = goals.map(goal => {
            const progress = Math.max(0, Number(goal.progress_percent) || 0);
            return '<div class="rounded-2xl border border-slate-200 bg-slate-50 p-5">' +
                '<div class="flex items-start justify-between gap-3">' +
                '<h3 class="text-sm font-black text-slate-900 truncate">' + escapeHtml(goal.title || "Savings Goal") + '</h3>' +
                '<span class="px-2 py-1 rounded-full bg-purple-100 text-purple-700 text-[10px] font-bold shrink-0">' + escapeHtml(goal.category || "General") + '</span>' +
                '</div>' +
                '<div class="flex justify-between mt-4 text-xs"><span class="font-bold">' + money(goal.current_amount) + '</span><span class="text-slate-400">Target ' + money(goal.target_amount) + '</span></div>' +
                '<div class="h-2.5 bg-slate-200 rounded-full overflow-hidden mt-2"><div class="h-full bg-purple-500 rounded-full" style="width:' + Math.min(100, progress) + '%"></div></div>' +
                '<div class="flex justify-between mt-3 text-[11px] text-slate-500"><span>' + progress.toFixed(1) + '% achieved</span><span>' + (goal.target_date ? "By " + escapeHtml(goal.target_date) : "Ongoing") + '</span></div>' +
                '</div>';
        }).join("");
    }

    function renderRecentExpenses(transactions) {
        const body = document.getElementById("recent-transactions-body");
        if (!body) return;

        const expenses = (Array.isArray(transactions) ? transactions : [])
            .filter(item => !item.type || item.type === "expense")
            .slice(0, 10);

        if (!expenses.length) {
            body.innerHTML = '<tr><td colspan="4" class="py-8 text-center text-slate-400">No recent expenses found.</td></tr>';
            return;
        }

        body.innerHTML = expenses.map(item =>
            '<tr class="hover:bg-slate-50">' +
            '<td class="py-3 px-3 text-slate-500 whitespace-nowrap">' + escapeHtml(item.date || item.created_at?.slice(0, 10) || "-") + '</td>' +
            '<td class="py-3 px-3 font-bold text-slate-800">' + escapeHtml(item.category || "General") + '</td>' +
            '<td class="py-3 px-3 text-slate-600">' + escapeHtml(item.description || "-") + '</td>' +
            '<td class="py-3 px-3 text-right font-black text-slate-900">-' + money(item.amount) + '</td>' +
            '</tr>'
        ).join("");
    }

    function render(data) {
        const summary = data.summary || {};
        const budgets = data.budget_comparisons || [];
        const expenses = Number(summary.total_expenses) || 0;
        const recent = data.recent_transactions || [];

        renderMetricCards(summary);
        renderMonthlyChart(data.monthly_trends || []);
        renderCategoryChart(data.category_breakdown || [], expenses);
        renderBudgetChart(budgets, summary);
        renderBudgetTable(budgets);
        renderGoals(data.goals || []);
        renderRecentExpenses(recent);

        const hasData = expenses > 0 || recent.some(item => !item.type || item.type === "expense") || budgets.length > 0 || (data.goals || []).length > 0;
        document.getElementById("analytics-empty-state")?.classList.toggle("hidden", hasData);
    }

    async function loadAnalytics() {
        const skeleton = document.getElementById("analytics-loading-skeleton");
        const content = document.getElementById("analytics-content-shell");
        const icon = document.getElementById("refresh-icon");

        icon?.classList.add("fa-spin");

        try {
            const response = await fetch(API_BASE_URL + "/customer/analytics", { credentials: "include" });
            if (!response.ok) throw new Error("Server returned HTTP " + response.status);

            const data = await response.json();
            if (!data.success) throw new Error(data.message || "Unable to load analytics.");

            render(data);
            skeleton?.classList.add("hidden");
            content?.classList.remove("hidden");
        } catch (error) {
            console.error("Analytics load failed:", error);
            skeleton?.classList.add("hidden");
            content?.classList.remove("hidden");
            showAlert("Unable to load analytics data. Please refresh and try again.", true);
        } finally {
            icon?.classList.remove("fa-spin");
        }
    }

    document.getElementById("refresh-analytics-btn")?.addEventListener("click", loadAnalytics);

    if (await verifyAuthentication()) {
        await loadAnalytics();
    }
});