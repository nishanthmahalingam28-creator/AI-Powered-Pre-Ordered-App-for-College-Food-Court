document.addEventListener("DOMContentLoaded", async () => {
    "use strict";

    const API_BASE_URL =
        window.FOOD_COURT_API_BASE ||
        (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "/api");

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

    const api = (path) => API_BASE_URL.replace(/\/+$/, "") + "/" + path.replace(/^\/+/, "");

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
        document.getElementById("analytics-alert")?.classList.add("hidden");
    };

    async function verifyAuthentication() {
        try {
            const response = await fetch(api("/auth/me"), { credentials: "include" });
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

    function localDateString(date = new Date()) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return year + "-" + month + "-" + day;
    }

    function currentMonthRange() {
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), 1);
        const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        return [localDateString(start), localDateString(end)];
    }

    function isFoodExpense(item) {
        return String(item?.category || "").trim().toLowerCase() === "food";
    }

    function expenseDate(item) {
        return String(item?.expense_date || item?.date || item?.created_at || "").slice(0, 10);
    }

    async function fetchJson(path) {
        const response = await fetch(api(path), { credentials: "include" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            throw new Error(data.message || "Unable to load " + path);
        }
        return data;
    }

    function findMonthlyFoodBudget(budgets) {
        return (Array.isArray(budgets) ? budgets : []).find(
            item => String(item?.period || "").toLowerCase() === "monthly" &&
                    String(item?.category || "").trim().toLowerCase() === "food"
        );
    }

    function renderStatus(spent, budget) {
        const remaining = budget > 0 ? budget - spent : 0;
        const percent = budget > 0 ? (spent / budget) * 100 : 0;
        const displayPercent = Math.max(0, percent);

        document.getElementById("metric-food-spent").textContent = money(spent);
        document.getElementById("metric-food-budget").textContent = money(budget);
        document.getElementById("metric-food-remaining").textContent = money(Math.max(0, remaining));

        const spentText = document.getElementById("status-spent-text");
        const budgetText = document.getElementById("status-budget-text");
        const percentText = document.getElementById("status-percent");
        const progress = document.getElementById("status-progress");
        const statusCard = document.getElementById("status-card");
        const statusIcon = document.getElementById("status-icon");
        const statusTitle = document.getElementById("status-title");
        const statusDetail = document.getElementById("status-detail");
        const statusLabel = document.getElementById("metric-food-status");

        spentText.textContent = "Spent: " + money(spent);
        budgetText.textContent = "Budget: " + money(budget);
        percentText.textContent = budget > 0 ? percent.toFixed(1) + "%" : "0.0%";
        progress.style.width = Math.min(100, Math.max(0, displayPercent)) + "%";

        if (budget <= 0) {
            progress.className = "h-full bg-slate-300 rounded-full transition-all duration-500";
            statusCard.className = "rounded-2xl bg-slate-50 border border-slate-200 p-5 text-center";
            statusIcon.className = "text-2xl text-slate-500";
            statusIcon.innerHTML = '<i class="fa-solid fa-circle-info"></i>';
            statusTitle.className = "text-sm font-black text-slate-700 mt-2";
            statusTitle.textContent = "No budget set";
            statusDetail.className = "text-xs text-slate-500 mt-1";
            statusDetail.textContent = "Create a monthly food budget to track spending.";
            statusLabel.className = "text-[11px] font-bold text-slate-500 mt-1";
            statusLabel.textContent = "No budget set";
            return;
        }

        if (spent > budget) {
            progress.className = "h-full bg-rose-500 rounded-full transition-all duration-500";
            statusCard.className = "rounded-2xl bg-rose-50 border border-rose-200 p-5 text-center";
            statusIcon.className = "text-2xl text-rose-600";
            statusIcon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
            statusTitle.className = "text-sm font-black text-rose-800 mt-2";
            statusTitle.textContent = "Budget exceeded";
            statusDetail.className = "text-xs text-rose-700 mt-1";
            statusDetail.textContent = money(spent - budget) + " over the monthly limit.";
            statusLabel.className = "text-[11px] font-bold text-rose-600 mt-1";
            statusLabel.textContent = "Exceeded";
        } else if (percent >= 80) {
            progress.className = "h-full bg-amber-500 rounded-full transition-all duration-500";
            statusCard.className = "rounded-2xl bg-amber-50 border border-amber-200 p-5 text-center";
            statusIcon.className = "text-2xl text-amber-600";
            statusIcon.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i>';
            statusTitle.className = "text-sm font-black text-amber-800 mt-2";
            statusTitle.textContent = "Near budget limit";
            statusDetail.className = "text-xs text-amber-700 mt-1";
            statusDetail.textContent = money(remaining) + " remaining.";
            statusLabel.className = "text-[11px] font-bold text-amber-600 mt-1";
            statusLabel.textContent = "Near Limit";
        } else {
            progress.className = "h-full bg-teal-500 rounded-full transition-all duration-500";
            statusCard.className = "rounded-2xl bg-emerald-50 border border-emerald-200 p-5 text-center";
            statusIcon.className = "text-2xl text-emerald-600";
            statusIcon.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
            statusTitle.className = "text-sm font-black text-emerald-800 mt-2";
            statusTitle.textContent = "Within budget";
            statusDetail.className = "text-xs text-emerald-700 mt-1";
            statusDetail.textContent = money(remaining) + " remaining.";
            statusLabel.className = "text-[11px] font-bold text-emerald-600 mt-1";
            statusLabel.textContent = "On Track";
        }
    }

    function renderExpenses(expenses) {
        const body = document.getElementById("food-expenses-body");
        const empty = document.getElementById("expenses-empty");
        const table = document.getElementById("expenses-table-wrapper");

        if (!body) return;

        if (!expenses.length) {
            body.innerHTML = "";
            empty?.classList.remove("hidden");
            table?.classList.add("hidden");
            return;
        }

        empty?.classList.add("hidden");
        table?.classList.remove("hidden");

        body.innerHTML = expenses
            .slice()
            .sort((a, b) => expenseDate(b).localeCompare(expenseDate(a)))
            .slice(0, 10)
            .map(item =>
                '<tr class="hover:bg-slate-50">' +
                '<td class="py-3 px-3 text-slate-500 whitespace-nowrap">' + escapeHtml(expenseDate(item) || "-") + "</td>" +
                '<td class="py-3 px-3 font-bold text-slate-800">' + escapeHtml(item.category || "Food") + "</td>" +
                '<td class="py-3 px-3 text-slate-600">' + escapeHtml(item.description || "-") + "</td>" +
                '<td class="py-3 px-3 text-right font-black text-slate-900 whitespace-nowrap">' + money(item.amount) + "</td>" +
                "</tr>"
            ).join("");
    }

    async function loadAnalytics() {
        const skeleton = document.getElementById("analytics-loading-skeleton");
        const content = document.getElementById("analytics-content-shell");
        const icon = document.getElementById("refresh-icon");

        icon?.classList.add("fa-spin");

        try {
            const [expenseData, budgetData] = await Promise.all([
                fetchJson("/expenses"),
                fetchJson("/budgets")
            ]);

            const allExpenses = Array.isArray(expenseData.expenses) ? expenseData.expenses : [];
            const budgets = Array.isArray(budgetData.budgets) ? budgetData.budgets : [];

            const [monthStart, monthEnd] = currentMonthRange();
            const monthlyFoodExpenses = allExpenses.filter(item => {
                const date = expenseDate(item);
                return isFoodExpense(item) && date >= monthStart && date <= monthEnd;
            });

            const foodSpent = monthlyFoodExpenses.reduce(
                (total, item) => total + (Number(item.amount) || 0), 0
            );

            const monthlyFoodBudget = findMonthlyFoodBudget(budgets);
            const foodBudget = Number(monthlyFoodBudget?.amount_limit) || 0;

            document.getElementById("metric-food-count").textContent =
                monthlyFoodExpenses.length + (monthlyFoodExpenses.length === 1 ? " expense this month" : " expenses this month");
            document.getElementById("status-period-label").textContent =
                "Monthly food budget vs food expenses (" + monthStart.slice(0, 7) + ")";

            renderStatus(foodSpent, foodBudget);
            renderExpenses(monthlyFoodExpenses);

            skeleton?.classList.add("hidden");
            content?.classList.remove("hidden");
        } catch (error) {
            console.error("Food analytics load failed:", error);
            skeleton?.classList.add("hidden");
            content?.classList.remove("hidden");
            showAlert(error.message || "Unable to load food spending data. Please refresh and try again.", true);
        } finally {
            icon?.classList.remove("fa-spin");
        }
    }

    document.getElementById("refresh-analytics-btn")?.addEventListener("click", loadAnalytics);

    if (await verifyAuthentication()) {
        await loadAnalytics();
    }
});