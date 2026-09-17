/**
 * Customer Budgets & Financial Goals Management Controller.
 * 
 * Interacts directly with authenticated backend APIs:
 * - /api/budgets (Category Budgets)
 * - /api/goals & /api/financial-goals (Savings / Financial Goals)
 * 
 * Enforces:
 * 1. Database-backed persistence (removes localStorage as source of truth).
 * 2. Session-based authentication (cookies included via credentials: "include").
 * 3. Client-side input validation and error handling.
 * 4. Loading, error (with retry), and empty states.
 * 5. Duplicate submission prevention on all action buttons.
 * 6. Interactive modals for editing and deleting records.
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // 1. Remove Legacy localStorage Persistence
    // -------------------------------------------------------------
    try {
        localStorage.removeItem("budgets");
        localStorage.removeItem("food_court_budgets");
        localStorage.removeItem("goals");
        localStorage.removeItem("financial_goals");
        localStorage.removeItem("food_court_goals");
    } catch (e) {
        console.warn("Storage access restricted:", e);
    }

    // -------------------------------------------------------------
    // API Resolver Helper
    // -------------------------------------------------------------
    function getApiUrl(path) {
        if (typeof window.getApiUrl === "function") {
            return window.getApiUrl(path);
        }
        const origin = window.location.origin;
        if (origin && origin.startsWith("http")) {
            return `${origin}${path}`;
        }
        return `http://127.0.0.1:5000${path}`;
    }

    // -------------------------------------------------------------
    // Tab Navigation Switcher
    // -------------------------------------------------------------
    const tabBudgetsBtn = document.getElementById("tab-budgets-btn");
    const tabGoalsBtn = document.getElementById("tab-goals-btn");
    const budgetsSection = document.getElementById("budgets-section");
    const goalsSection = document.getElementById("goals-section");

    function switchTab(target) {
        if (target === "goals-section") {
            budgetsSection.classList.add("hidden");
            goalsSection.classList.remove("hidden");

            tabBudgetsBtn.className = "tab-btn px-6 py-3 border-b-2 font-bold text-sm uppercase tracking-wider transition-all cursor-pointer border-transparent text-slate-500 hover:text-slate-900 flex items-center gap-2";
            tabGoalsBtn.className = "tab-btn px-6 py-3 border-b-2 font-black text-sm uppercase tracking-wider transition-all cursor-pointer border-emerald-600 text-emerald-700 flex items-center gap-2";

            fetchGoals();
        } else {
            goalsSection.classList.add("hidden");
            budgetsSection.classList.remove("hidden");

            tabGoalsBtn.className = "tab-btn px-6 py-3 border-b-2 font-bold text-sm uppercase tracking-wider transition-all cursor-pointer border-transparent text-slate-500 hover:text-slate-900 flex items-center gap-2";
            tabBudgetsBtn.className = "tab-btn px-6 py-3 border-b-2 font-black text-sm uppercase tracking-wider transition-all cursor-pointer border-teal-600 text-teal-700 flex items-center gap-2";

            fetchBudgets();
        }
    }

    if (tabBudgetsBtn && tabGoalsBtn) {
        tabBudgetsBtn.addEventListener("click", () => switchTab("budgets-section"));
        tabGoalsBtn.addEventListener("click", () => switchTab("goals-section"));
    }

    // Check URL hash
    if (window.location.hash === "#goals-section" || window.location.hash === "#goals") {
        switchTab("goals-section");
    }

    // Current Month active label
    const currentMonthLabel = new Date().toLocaleString("default", { month: "short", year: "numeric" });
    const statBudgetPeriod = document.getElementById("stat-budget-period");
    if (statBudgetPeriod) statBudgetPeriod.textContent = currentMonthLabel;

    // =============================================================
    // BUDGETS CONTROLLER
    // =============================================================
    let budgetsList = [];
    let isSubmittingBudget = false;

    const budgetForm = document.getElementById("budget-form");
    const budgetCategory = document.getElementById("budget-category");
    const budgetLimit = document.getElementById("budget-limit");
    const budgetPeriod = document.getElementById("budget-period");
    const budgetStartDate = document.getElementById("budget-start-date");
    const budgetEndDate = document.getElementById("budget-end-date");
    const submitBudgetBtn = document.getElementById("submit-budget-btn");
    const submitBudgetText = document.getElementById("submit-budget-text");
    const submitBudgetSpinner = document.getElementById("submit-budget-spinner");
    const budgetFormAlert = document.getElementById("budget-form-alert");
    const budgetFormAlertText = document.getElementById("budget-form-alert-text");
    const budgetCategoryError = document.getElementById("budget-category-error");
    const budgetLimitError = document.getElementById("budget-limit-error");

    const statTotalBudget = document.getElementById("stat-total-budget");
    const statBudgetCount = document.getElementById("stat-budget-count");

    const budgetsLoading = document.getElementById("budgets-loading");
    const budgetsError = document.getElementById("budgets-error");
    const budgetsErrorText = document.getElementById("budgets-error-text");
    const retryBudgetsBtn = document.getElementById("retry-budgets-btn");
    const budgetsEmpty = document.getElementById("budgets-empty");
    const budgetsTableWrapper = document.getElementById("budgets-table-wrapper");
    const budgetsTbody = document.getElementById("budgets-tbody");
    const refreshBudgetsBtn = document.getElementById("refresh-budgets-btn");
    const budgetListAlert = document.getElementById("budget-list-alert");
    const budgetListAlertText = document.getElementById("budget-list-alert-text");

    function showBudgetFormAlert(msg, isSuccess = false) {
        if (!budgetFormAlert || !budgetFormAlertText) return;
        budgetFormAlert.className = isSuccess
            ? "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200"
            : "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-rose-50 text-rose-800 border border-rose-200";
        budgetFormAlertText.textContent = msg;
        budgetFormAlert.classList.remove("hidden");
    }

    function hideBudgetFormAlert() {
        if (budgetFormAlert) budgetFormAlert.classList.add("hidden");
    }

    function showBudgetListAlert(msg, isSuccess = false) {
        if (!budgetListAlert || !budgetListAlertText) return;
        budgetListAlert.className = isSuccess
            ? "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200"
            : "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-rose-50 text-rose-800 border border-rose-200";
        budgetListAlertText.textContent = msg;
        budgetListAlert.classList.remove("hidden");
        setTimeout(() => {
            if (budgetListAlert) budgetListAlert.classList.add("hidden");
        }, 5000);
    }

    async function fetchBudgets() {
        if (!budgetsLoading) return;
        budgetsLoading.classList.remove("hidden");
        budgetsError.classList.add("hidden");
        budgetsEmpty.classList.add("hidden");
        budgetsTableWrapper.classList.add("hidden");

        try {
            const res = await fetch(getApiUrl("/api/budgets"), {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include"
            });

            if (res.status === 401) {
                window.location.href = "../auth/login.html?redirect=customer/budgets.html";
                return;
            }

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || "Failed to retrieve budgets.");
            }

            budgetsList = data.budgets || [];
            updateBudgetMetrics(budgetsList);
            renderBudgetsTable(budgetsList);

        } catch (err) {
            console.error("Fetch budgets error:", err);
            budgetsLoading.classList.add("hidden");
            budgetsError.classList.remove("hidden");
            if (budgetsErrorText) budgetsErrorText.textContent = err.message || "Failed to communicate with the database.";
        }
    }

    function updateBudgetMetrics(list) {
        let total = 0;
        list.forEach(b => {
            total += Number(b.amount_limit || b.amount || 0);
        });

        if (statTotalBudget) statTotalBudget.textContent = `₹${total.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (statBudgetCount) statBudgetCount.textContent = list.length.toString();
    }

    function renderBudgetsTable(list) {
        budgetsLoading.classList.add("hidden");
        if (!list || list.length === 0) {
            budgetsEmpty.classList.remove("hidden");
            budgetsTableWrapper.classList.add("hidden");
            return;
        }

        budgetsEmpty.classList.add("hidden");
        budgetsTableWrapper.classList.remove("hidden");
        budgetsTbody.innerHTML = "";

        list.forEach(b => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-50/80 transition-colors";

            const limitVal = Number(b.amount_limit || b.amount || 0).toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });

            const dateRange = (b.start_date || b.end_date)
                ? `${b.start_date || "Start"} → ${b.end_date || "Ongoing"}`
                : "Continuous";

            tr.innerHTML = `
                <td class="py-3 px-3 font-bold text-slate-800 flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-teal-500 shrink-0"></span>
                    ${escapeHtml(b.category)}
                </td>
                <td class="py-3 px-3">
                    <span class="px-2 py-0.5 rounded-md text-[11px] font-bold uppercase bg-slate-100 text-slate-600">
                        ${escapeHtml(b.period || "monthly")}
                    </span>
                </td>
                <td class="py-3 px-3 text-right font-black text-slate-900">
                    ₹${limitVal}
                </td>
                <td class="py-3 px-3 text-slate-500 text-[11px]">
                    ${dateRange}
                </td>
                <td class="py-3 px-3 text-center">
                    <div class="flex items-center justify-center gap-2">
                        <button class="edit-budget-btn p-1.5 rounded-lg text-slate-400 hover:text-teal-700 hover:bg-teal-50 transition-colors" data-id="${b.id}" title="Edit Budget">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button class="delete-budget-btn p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors" data-id="${b.id}" title="Delete Budget">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;
            budgetsTbody.appendChild(tr);
        });

        // Attach action listeners
        document.querySelectorAll(".edit-budget-btn").forEach(btn => {
            btn.addEventListener("click", () => openEditBudgetModal(btn.dataset.id));
        });
        document.querySelectorAll(".delete-budget-btn").forEach(btn => {
            btn.addEventListener("click", () => openDeleteModal("budget", btn.dataset.id));
        });
    }

    // Add Budget Form Submit
    if (budgetForm) {
        budgetForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            hideBudgetFormAlert();

            if (isSubmittingBudget) return;

            const category = budgetCategory.value.trim();
            const limitStr = budgetLimit.value.trim();
            const limit = parseFloat(limitStr);

            let hasError = false;
            if (!category) {
                budgetCategoryError.textContent = "Category is required.";
                budgetCategoryError.classList.remove("hidden");
                hasError = true;
            } else {
                budgetCategoryError.classList.add("hidden");
            }

            if (isNaN(limit) || limit <= 0) {
                budgetLimitError.textContent = "Enter a valid limit greater than ₹0.";
                budgetLimitError.classList.remove("hidden");
                hasError = true;
            } else if (limit > 1000000) {
                budgetLimitError.textContent = "Limit cannot exceed ₹1,000,000.";
                budgetLimitError.classList.remove("hidden");
                hasError = true;
            } else {
                budgetLimitError.classList.add("hidden");
            }

            if (hasError) return;

            // Lock submit button
            isSubmittingBudget = true;
            submitBudgetBtn.disabled = true;
            submitBudgetText.textContent = "Saving...";
            submitBudgetSpinner.classList.remove("hidden");

            const payload = {
                category: category,
                amount_limit: limit,
                period: budgetPeriod.value || "monthly",
                start_date: budgetStartDate.value || null,
                end_date: budgetEndDate.value || null
            };

            try {
                const res = await fetch(getApiUrl("/api/budgets"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify(payload)
                });

                if (res.status === 401) {
                    window.location.href = "../auth/login.html?redirect=customer/budgets.html";
                    return;
                }

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || "Failed to save budget.");
                }

                showBudgetFormAlert("Budget category saved successfully!", true);
                budgetForm.reset();
                fetchBudgets();

            } catch (err) {
                showBudgetFormAlert(err.message || "Network error. Please try again.");
            } finally {
                isSubmittingBudget = false;
                submitBudgetBtn.disabled = false;
                submitBudgetText.textContent = "Save Budget";
                submitBudgetSpinner.classList.add("hidden");
            }
        });
    }

    if (refreshBudgetsBtn) refreshBudgetsBtn.addEventListener("click", fetchBudgets);
    if (retryBudgetsBtn) retryBudgetsBtn.addEventListener("click", fetchBudgets);

    // =============================================================
    // GOALS CONTROLLER
    // =============================================================
    let goalsList = [];
    let isSubmittingGoal = false;

    const goalForm = document.getElementById("goal-form");
    const goalTitle = document.getElementById("goal-title");
    const goalTarget = document.getElementById("goal-target");
    const goalCurrent = document.getElementById("goal-current");
    const goalDate = document.getElementById("goal-date");
    const goalCategory = document.getElementById("goal-category");
    const submitGoalBtn = document.getElementById("submit-goal-btn");
    const submitGoalText = document.getElementById("submit-goal-text");
    const submitGoalSpinner = document.getElementById("submit-goal-spinner");
    const goalFormAlert = document.getElementById("goal-form-alert");
    const goalFormAlertText = document.getElementById("goal-form-alert-text");
    const goalTitleError = document.getElementById("goal-title-error");
    const goalTargetError = document.getElementById("goal-target-error");
    const goalCurrentError = document.getElementById("goal-current-error");
    const goalDateError = document.getElementById("goal-date-error");

    const statTotalTarget = document.getElementById("stat-total-target");
    const statTotalSaved = document.getElementById("stat-total-saved");
    const statOverallProgress = document.getElementById("stat-overall-progress");

    const goalsLoading = document.getElementById("goals-loading");
    const goalsError = document.getElementById("goals-error");
    const goalsErrorText = document.getElementById("goals-error-text");
    const retryGoalsBtn = document.getElementById("retry-goals-btn");
    const goalsEmpty = document.getElementById("goals-empty");
    const goalsGrid = document.getElementById("goals-grid");
    const refreshGoalsBtn = document.getElementById("refresh-goals-btn");
    const goalListAlert = document.getElementById("goal-list-alert");
    const goalListAlertText = document.getElementById("goal-list-alert-text");

    function showGoalFormAlert(msg, isSuccess = false) {
        if (!goalFormAlert || !goalFormAlertText) return;
        goalFormAlert.className = isSuccess
            ? "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200"
            : "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-rose-50 text-rose-800 border border-rose-200";
        goalFormAlertText.textContent = msg;
        goalFormAlert.classList.remove("hidden");
    }

    function hideGoalFormAlert() {
        if (goalFormAlert) goalFormAlert.classList.add("hidden");
    }

    function showGoalListAlert(msg, isSuccess = false) {
        if (!goalListAlert || !goalListAlertText) return;
        goalListAlert.className = isSuccess
            ? "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200"
            : "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-rose-50 text-rose-800 border border-rose-200";
        goalListAlertText.textContent = msg;
        goalListAlert.classList.remove("hidden");
        setTimeout(() => {
            if (goalListAlert) goalListAlert.classList.add("hidden");
        }, 5000);
    }

    async function fetchGoals() {
        if (!goalsLoading) return;
        goalsLoading.classList.remove("hidden");
        goalsError.classList.add("hidden");
        goalsEmpty.classList.add("hidden");
        goalsGrid.classList.add("hidden");

        try {
            const res = await fetch(getApiUrl("/api/goals"), {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include"
            });

            if (res.status === 401) {
                window.location.href = "../auth/login.html?redirect=customer/budgets.html#goals-section";
                return;
            }

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || "Failed to retrieve goals.");
            }

            goalsList = data.goals || [];
            updateGoalMetrics(goalsList);
            renderGoalsGrid(goalsList);

        } catch (err) {
            console.error("Fetch goals error:", err);
            goalsLoading.classList.add("hidden");
            goalsError.classList.remove("hidden");
            if (goalsErrorText) goalsErrorText.textContent = err.message || "Failed to communicate with the database.";
        }
    }

    function updateGoalMetrics(list) {
        let totalTarget = 0;
        let totalSaved = 0;
        list.forEach(g => {
            totalTarget += Number(g.target_amount || 0);
            totalSaved += Number(g.current_amount || 0);
        });

        if (statTotalTarget) statTotalTarget.textContent = `₹${totalTarget.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (statTotalSaved) statTotalSaved.textContent = `₹${totalSaved.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        const overallPct = totalTarget > 0 ? Math.min(100, Math.round((totalSaved / totalTarget) * 100)) : 0;
        if (statOverallProgress) statOverallProgress.textContent = `${overallPct}%`;
    }

    function renderGoalsGrid(list) {
        goalsLoading.classList.add("hidden");
        if (!list || list.length === 0) {
            goalsEmpty.classList.remove("hidden");
            goalsGrid.classList.add("hidden");
            return;
        }

        goalsEmpty.classList.add("hidden");
        goalsGrid.classList.remove("hidden");
        goalsGrid.innerHTML = "";

        list.forEach(g => {
            const targetVal = Number(g.target_amount || 0);
            const savedVal = Number(g.current_amount || 0);
            const pct = targetVal > 0 ? Math.min(100, Math.round((savedVal / targetVal) * 100)) : 0;

            const isCompleted = savedVal >= targetVal || g.status === "achieved";
            const statusBadge = isCompleted
                ? `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase bg-emerald-100 text-emerald-800 border border-emerald-200"><i class="fa-solid fa-check mr-1"></i>Achieved</span>`
                : `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase bg-cyan-100 text-cyan-800 border border-cyan-200"><i class="fa-solid fa-clock mr-1"></i>In Progress</span>`;

            const card = document.createElement("div");
            card.className = "bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between";
            card.innerHTML = `
                <div>
                    <div class="flex items-start justify-between gap-2 mb-3">
                        <div>
                            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">${escapeHtml(g.category || "Dining")}</span>
                            <h3 class="text-sm font-black text-slate-900 mt-0.5">${escapeHtml(g.title || g.name)}</h3>
                        </div>
                        <div class="shrink-0">${statusBadge}</div>
                    </div>

                    <div class="flex items-baseline justify-between mt-3 mb-1.5 text-xs font-bold">
                        <span class="text-slate-500">Saved: <strong class="text-slate-900">₹${savedVal.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></span>
                        <span class="text-slate-500">Target: <strong class="text-slate-900">₹${targetVal.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></span>
                    </div>

                    <!-- Progress Bar -->
                    <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden mb-3">
                        <div class="bg-gradient-to-r from-teal-500 to-emerald-500 h-2.5 rounded-full transition-all duration-500" style="width: ${pct}%"></div>
                    </div>

                    <div class="flex items-center justify-between text-[11px] text-slate-400 mb-4">
                        <span><i class="fa-solid fa-flag-checkered mr-1"></i> ${pct}% Funded</span>
                        <span><i class="fa-regular fa-calendar mr-1"></i> ${g.target_date || "No deadline"}</span>
                    </div>
                </div>

                <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                    <button class="edit-goal-btn px-3 py-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors flex items-center gap-1.5" data-id="${g.id}">
                        <i class="fa-solid fa-plus-minus text-xs"></i> Update Savings
                    </button>
                    <button class="delete-goal-btn p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors" data-id="${g.id}" title="Delete Goal">
                        <i class="fa-solid fa-trash-can text-xs"></i>
                    </button>
                </div>
            `;
            goalsGrid.appendChild(card);
        });

        // Attach action listeners
        document.querySelectorAll(".edit-goal-btn").forEach(btn => {
            btn.addEventListener("click", () => openEditGoalModal(btn.dataset.id));
        });
        document.querySelectorAll(".delete-goal-btn").forEach(btn => {
            btn.addEventListener("click", () => openDeleteModal("goal", btn.dataset.id));
        });
    }

    // Add Goal Form Submit
    if (goalForm) {
        goalForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            hideGoalFormAlert();

            if (isSubmittingGoal) return;

            const title = goalTitle.value.trim();
            const targetStr = goalTarget.value.trim();
            const target = parseFloat(targetStr);
            const currentStr = goalCurrent.value.trim();
            const current = currentStr ? parseFloat(currentStr) : 0;

            let hasError = false;
            if (!title) {
                goalTitleError.textContent = "Goal title is required.";
                goalTitleError.classList.remove("hidden");
                hasError = true;
            } else {
                goalTitleError.classList.add("hidden");
            }

            if (isNaN(target) || target <= 0) {
                goalTargetError.textContent = "Target amount must be greater than ₹0.";
                goalTargetError.classList.remove("hidden");
                hasError = true;
            } else if (target > 10000000) {
                goalTargetError.textContent = "Target amount exceeds maximum limit of ₹10,000,000.";
                goalTargetError.classList.remove("hidden");
                hasError = true;
            } else {
                goalTargetError.classList.add("hidden");
            }

            if (isNaN(current) || current < 0) {
                goalCurrentError.textContent = "Saved amount cannot be negative.";
                goalCurrentError.classList.remove("hidden");
                hasError = true;
            } else {
                goalCurrentError.classList.add("hidden");
            }

            if (hasError) return;

            // Lock submit button
            isSubmittingGoal = true;
            submitGoalBtn.disabled = true;
            submitGoalText.textContent = "Creating...";
            submitGoalSpinner.classList.remove("hidden");

            const payload = {
                title: title,
                target_amount: target,
                current_amount: current,
                target_date: goalDate.value || null,
                category: goalCategory.value || "Dining"
            };

            try {
                const res = await fetch(getApiUrl("/api/goals"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify(payload)
                });

                if (res.status === 401) {
                    window.location.href = "../auth/login.html?redirect=customer/budgets.html#goals-section";
                    return;
                }

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || "Failed to create financial goal.");
                }

                showGoalFormAlert("Financial goal created successfully!", true);
                goalForm.reset();
                fetchGoals();

            } catch (err) {
                showGoalFormAlert(err.message || "Network error. Please try again.");
            } finally {
                isSubmittingGoal = false;
                submitGoalBtn.disabled = false;
                submitGoalText.textContent = "Create Goal";
                submitGoalSpinner.classList.add("hidden");
            }
        });
    }

    if (refreshGoalsBtn) refreshGoalsBtn.addEventListener("click", fetchGoals);
    if (retryGoalsBtn) retryGoalsBtn.addEventListener("click", fetchGoals);

    // =============================================================
    // EDIT BUDGET MODAL WORKFLOW
    // =============================================================
    const editBudgetModal = document.getElementById("edit-budget-modal");
    const editBudgetForm = document.getElementById("edit-budget-form");
    const editBudgetId = document.getElementById("edit-budget-id");
    const editBudgetCategory = document.getElementById("edit-budget-category");
    const editBudgetLimit = document.getElementById("edit-budget-limit");
    const editBudgetPeriod = document.getElementById("edit-budget-period");
    const closeEditBudgetBtn = document.getElementById("close-edit-budget-btn");
    const cancelEditBudgetBtn = document.getElementById("cancel-edit-budget-btn");
    const saveEditBudgetBtn = document.getElementById("save-edit-budget-btn");
    const saveEditBudgetText = document.getElementById("save-edit-budget-text");
    const saveEditBudgetSpinner = document.getElementById("save-edit-budget-spinner");
    const editBudgetAlert = document.getElementById("edit-budget-alert");
    const editBudgetAlertText = document.getElementById("edit-budget-alert-text");

    function openEditBudgetModal(id) {
        const item = budgetsList.find(b => String(b.id) === String(id));
        if (!item) return;

        editBudgetId.value = item.id;
        editBudgetCategory.value = item.category || "";
        editBudgetLimit.value = item.amount_limit || item.amount || "";
        editBudgetPeriod.value = item.period || "monthly";
        editBudgetAlert.classList.add("hidden");

        editBudgetModal.classList.remove("hidden");
    }

    function closeEditBudgetModal() {
        if (editBudgetModal) editBudgetModal.classList.add("hidden");
    }

    if (closeEditBudgetBtn) closeEditBudgetBtn.addEventListener("click", closeEditBudgetModal);
    if (cancelEditBudgetBtn) cancelEditBudgetBtn.addEventListener("click", closeEditBudgetModal);

    if (editBudgetForm) {
        editBudgetForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = editBudgetId.value;
            const category = editBudgetCategory.value.trim();
            const limit = parseFloat(editBudgetLimit.value);

            if (!category || isNaN(limit) || limit <= 0) {
                editBudgetAlertText.textContent = "Please provide a valid category and positive limit.";
                editBudgetAlert.className = "mb-4 p-3 rounded-xl text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200";
                editBudgetAlert.classList.remove("hidden");
                return;
            }

            saveEditBudgetBtn.disabled = true;
            saveEditBudgetText.textContent = "Updating...";
            saveEditBudgetSpinner.classList.remove("hidden");

            try {
                const res = await fetch(getApiUrl(`/api/budgets/${id}`), {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify({
                        category: category,
                        amount_limit: limit,
                        period: editBudgetPeriod.value
                    })
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || "Failed to update budget.");
                }

                closeEditBudgetModal();
                showBudgetListAlert("Budget updated successfully!", true);
                fetchBudgets();

            } catch (err) {
                editBudgetAlertText.textContent = err.message;
                editBudgetAlert.className = "mb-4 p-3 rounded-xl text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200";
                editBudgetAlert.classList.remove("hidden");
            } finally {
                saveEditBudgetBtn.disabled = false;
                saveEditBudgetText.textContent = "Update Budget";
                saveEditBudgetSpinner.classList.add("hidden");
            }
        });
    }

    // =============================================================
    // EDIT GOAL MODAL WORKFLOW
    // =============================================================
    const editGoalModal = document.getElementById("edit-goal-modal");
    const editGoalForm = document.getElementById("edit-goal-form");
    const editGoalId = document.getElementById("edit-goal-id");
    const editGoalTitle = document.getElementById("edit-goal-title");
    const editGoalTarget = document.getElementById("edit-goal-target");
    const editGoalCurrent = document.getElementById("edit-goal-current");
    const editGoalStatus = document.getElementById("edit-goal-status");
    const closeEditGoalBtn = document.getElementById("close-edit-goal-btn");
    const cancelEditGoalBtn = document.getElementById("cancel-edit-goal-btn");
    const saveEditGoalBtn = document.getElementById("save-edit-goal-btn");
    const saveEditGoalText = document.getElementById("save-edit-goal-text");
    const saveEditGoalSpinner = document.getElementById("save-edit-goal-spinner");
    const editGoalAlert = document.getElementById("edit-goal-alert");
    const editGoalAlertText = document.getElementById("edit-goal-alert-text");

    function openEditGoalModal(id) {
        const item = goalsList.find(g => String(g.id) === String(id));
        if (!item) return;

        editGoalId.value = item.id;
        editGoalTitle.value = item.title || item.name || "";
        editGoalTarget.value = item.target_amount || "";
        editGoalCurrent.value = item.current_amount || 0;
        editGoalStatus.value = item.status || "in_progress";
        editGoalAlert.classList.add("hidden");

        editGoalModal.classList.remove("hidden");
    }

    function closeEditGoalModal() {
        if (editGoalModal) editGoalModal.classList.add("hidden");
    }

    if (closeEditGoalBtn) closeEditGoalBtn.addEventListener("click", closeEditGoalModal);
    if (cancelEditGoalBtn) cancelEditGoalBtn.addEventListener("click", closeEditGoalModal);

    if (editGoalForm) {
        editGoalForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const id = editGoalId.value;
            const title = editGoalTitle.value.trim();
            const target = parseFloat(editGoalTarget.value);
            const current = parseFloat(editGoalCurrent.value);

            if (!title || isNaN(target) || target <= 0 || isNaN(current) || current < 0) {
                editGoalAlertText.textContent = "Please provide valid title, positive target, and non-negative saved amount.";
                editGoalAlert.className = "mb-4 p-3 rounded-xl text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200";
                editGoalAlert.classList.remove("hidden");
                return;
            }

            saveEditGoalBtn.disabled = true;
            saveEditGoalText.textContent = "Saving...";
            saveEditGoalSpinner.classList.remove("hidden");

            try {
                const res = await fetch(getApiUrl(`/api/goals/${id}`), {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify({
                        title: title,
                        target_amount: target,
                        current_amount: current,
                        status: editGoalStatus.value
                    })
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || "Failed to update financial goal.");
                }

                closeEditGoalModal();
                showGoalListAlert("Goal and savings updated successfully!", true);
                fetchGoals();

            } catch (err) {
                editGoalAlertText.textContent = err.message;
                editGoalAlert.className = "mb-4 p-3 rounded-xl text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200";
                editGoalAlert.classList.remove("hidden");
            } finally {
                saveEditGoalBtn.disabled = false;
                saveEditGoalText.textContent = "Save Changes";
                saveEditGoalSpinner.classList.add("hidden");
            }
        });
    }

    // =============================================================
    // DELETE MODAL (SHARED FOR BUDGETS & GOALS)
    // =============================================================
    const deleteModal = document.getElementById("delete-modal");
    const deleteModalTitle = document.getElementById("delete-modal-title");
    const deleteModalDesc = document.getElementById("delete-modal-desc");
    const cancelDeleteBtn = document.getElementById("cancel-delete-btn");
    const confirmDeleteBtn = document.getElementById("confirm-delete-btn");
    const confirmDeleteText = document.getElementById("confirm-delete-text");
    const confirmDeleteSpinner = document.getElementById("confirm-delete-spinner");

    let deleteType = null; // 'budget' or 'goal'
    let deleteId = null;

    function openDeleteModal(type, id) {
        deleteType = type;
        deleteId = id;
        if (type === "budget") {
            deleteModalTitle.textContent = "Delete Category Budget";
            deleteModalDesc.textContent = "Are you sure you want to delete this category budget limit? It will be permanently removed from your account.";
        } else {
            deleteModalTitle.textContent = "Delete Financial Goal";
            deleteModalDesc.textContent = "Are you sure you want to delete this savings goal? All logged progress for this goal will be removed.";
        }
        deleteModal.classList.remove("hidden");
    }

    function closeDeleteModal() {
        deleteType = null;
        deleteId = null;
        if (deleteModal) deleteModal.classList.add("hidden");
    }

    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener("click", closeDeleteModal);

    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener("click", async () => {
            if (!deleteType || !deleteId) return;

            confirmDeleteBtn.disabled = true;
            confirmDeleteText.textContent = "Deleting...";
            confirmDeleteSpinner.classList.remove("hidden");

            const endpoint = deleteType === "budget" ? `/api/budgets/${deleteId}` : `/api/goals/${deleteId}`;

            try {
                const res = await fetch(getApiUrl(endpoint), {
                    method: "DELETE",
                    credentials: "include"
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || `Failed to delete ${deleteType}.`);
                }

                const msg = deleteType === "budget" ? "Budget deleted successfully." : "Goal deleted successfully.";
                if (deleteType === "budget") {
                    showBudgetListAlert(msg, true);
                    fetchBudgets();
                } else {
                    showGoalListAlert(msg, true);
                    fetchGoals();
                }
                closeDeleteModal();

            } catch (err) {
                alert(err.message || "Failed to delete record.");
            } finally {
                confirmDeleteBtn.disabled = false;
                confirmDeleteText.textContent = "Delete";
                confirmDeleteSpinner.classList.add("hidden");
            }
        });
    }

    // Helper: Escape HTML
    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initial Fetch
    fetchBudgets();
});
