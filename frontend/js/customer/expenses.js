/**
 * Customer Expenses Management Controller.
 * 
 * Interacts directly with authenticated backend API (/api/expenses).
 * Enforces:
 * 1. Database-backed persistence (removes localStorage as source of truth).
 * 2. Session-based authentication.
 * 3. Input validation for amount, date, category, and description.
 * 4. Loading, empty, and error states with retry capability.
 * 5. Duplicate submission prevention on all mutation buttons.
 * 6. Modal workflows for editing and deleting expenses.
 */

document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // 1. Remove Legacy localStorage Persistence
    // -------------------------------------------------------------
    try {
        localStorage.removeItem("expenses");
        localStorage.removeItem("food_court_expenses");
    } catch (e) {
        console.warn("Storage access restricted:", e);
    }

    // -------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------
    const form = document.getElementById("expense-form");
    const amountInput = document.getElementById("expense-amount");
    const dateInput = document.getElementById("expense-date");
    const categoryInput = document.getElementById("expense-category");
    const descriptionInput = document.getElementById("expense-description");
    const submitBtn = document.getElementById("submit-expense-btn");
    const submitBtnText = document.getElementById("submit-btn-text");
    const submitBtnSpinner = document.getElementById("submit-btn-spinner");

    const amountError = document.getElementById("amount-error");
    const dateError = document.getElementById("date-error");
    const categoryError = document.getElementById("category-error");
    const descriptionError = document.getElementById("description-error");
    const formAlert = document.getElementById("form-alert");
    const formAlertText = document.getElementById("form-alert-text");

    const statTotalAmount = document.getElementById("stat-total-amount");
    const statTotalCount = document.getElementById("stat-total-count");
    const statCurrentMonth = document.getElementById("stat-current-month");

    const loadingState = document.getElementById("expenses-loading");
    const errorState = document.getElementById("expenses-error");
    const errorMessageText = document.getElementById("error-message-text");
    const retryBtn = document.getElementById("retry-btn");
    const emptyState = document.getElementById("expenses-empty");
    const tableWrapper = document.getElementById("expenses-table-wrapper");
    const tbody = document.getElementById("expenses-tbody");
    const refreshBtn = document.getElementById("refresh-btn");
    const listAlert = document.getElementById("list-alert");
    const listAlertText = document.getElementById("list-alert-text");

    // Edit Modal Elements
    const editModal = document.getElementById("edit-modal");
    const editForm = document.getElementById("edit-expense-form");
    const editIdInput = document.getElementById("edit-expense-id");
    const editAmountInput = document.getElementById("edit-amount");
    const editDateInput = document.getElementById("edit-date");
    const editCategoryInput = document.getElementById("edit-category");
    const editDescInput = document.getElementById("edit-description");
    const saveEditBtn = document.getElementById("save-edit-btn");
    const saveEditText = document.getElementById("save-edit-text");
    const saveEditSpinner = document.getElementById("save-edit-spinner");
    const closeEditBtn = document.getElementById("close-edit-modal-btn");
    const cancelEditBtn = document.getElementById("cancel-edit-btn");
    const editAlert = document.getElementById("edit-alert");
    const editAlertText = document.getElementById("edit-alert-text");

    // Delete Modal Elements
    const deleteModal = document.getElementById("delete-modal");
    const cancelDeleteBtn = document.getElementById("cancel-delete-btn");
    const confirmDeleteBtn = document.getElementById("confirm-delete-btn");
    const confirmDeleteText = document.getElementById("confirm-delete-text");
    const confirmDeleteSpinner = document.getElementById("confirm-delete-spinner");

    // Local State
    let expensesList = [];
    let isSubmitting = false;
    let pendingDeleteId = null;

    // Default form date to today (YYYY-MM-DD)
    const today = new Date().toISOString().split("T")[0];
    if (dateInput) dateInput.value = today;

    // Set active month name
    const currentMonthName = new Date().toLocaleString("default", { month: "short", year: "numeric" });
    if (statCurrentMonth) statCurrentMonth.textContent = currentMonthName;

    // -------------------------------------------------------------
    // Helper: API Base Resolver
    // -------------------------------------------------------------
    function getApiUrl(path) {
        if (typeof window.getApiUrl === "function") {
            return window.getApiUrl(path);
        }
        const base = window.FOOD_COURT_API_BASE || "http://127.0.0.1:5000/api";
        return base.replace(/\/+$/, "") + "/" + path.replace(/^\/+/, "");
    }

    // -------------------------------------------------------------
    // Helper: Alert Display
    // -------------------------------------------------------------
    function showAlert(alertEl, textEl, message, isSuccess = false) {
        if (!alertEl || !textEl) return;
        textEl.textContent = message;
        alertEl.className = isSuccess
            ? "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200"
            : "mb-4 p-3.5 rounded-xl text-xs font-semibold flex items-start gap-2.5 bg-rose-50 text-rose-800 border border-rose-200";
        alertEl.classList.remove("hidden");
    }

    function hideAlert(alertEl) {
        if (alertEl) alertEl.classList.add("hidden");
    }

    // -------------------------------------------------------------
    // 2. Fetch Expenses from Database API
    // -------------------------------------------------------------
    async function loadExpenses() {
        hideAlert(listAlert);
        loadingState.classList.remove("hidden");
        errorState.classList.add("hidden");
        emptyState.classList.add("hidden");
        tableWrapper.classList.add("hidden");

        try {
            const res = await fetch(getApiUrl("/expenses"), {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include"
            });

            if (res.status === 401) {
                // Not authenticated -> redirect to login
                window.location.href = "../auth/login.html?redirect=customer/expenses.html";
                return;
            }

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || "Failed to load expenses.");
            }

            expensesList = Array.isArray(data.expenses) ? data.expenses : [];
            renderExpenses();

        } catch (err) {
            console.error("Error loading expenses:", err);
            loadingState.classList.add("hidden");
            errorState.classList.remove("hidden");
            if (errorMessageText) {
                errorMessageText.textContent = err.message || "Could not connect to the server. Please verify your connection.";
            }
        }
    }

    // -------------------------------------------------------------
    // 3. Render Expenses Table and Update Statistics
    // -------------------------------------------------------------
    function renderExpenses() {
        loadingState.classList.add("hidden");

        // Calculate and update metrics
        let total = 0.0;
        expensesList.forEach(exp => {
            total += parseFloat(exp.amount) || 0.0;
        });

        if (statTotalAmount) statTotalAmount.textContent = "₹" + total.toFixed(2);
        if (statTotalCount) statTotalCount.textContent = expensesList.length.toString();

        if (expensesList.length === 0) {
            emptyState.classList.remove("hidden");
            tableWrapper.classList.add("hidden");
            return;
        }

        emptyState.classList.add("hidden");
        tableWrapper.classList.remove("hidden");
        tbody.innerHTML = "";

        // Category Badge Color Palette
        const categoryColors = {
            "Food & Dining": "bg-amber-100 text-amber-800 border-amber-200",
            "Snacks & Beverages": "bg-teal-100 text-teal-800 border-teal-200",
            "Meal Plan": "bg-indigo-100 text-indigo-800 border-indigo-200",
            "Groceries": "bg-emerald-100 text-emerald-800 border-emerald-200",
            "Campus Supplies": "bg-purple-100 text-purple-800 border-purple-200",
            "Other": "bg-slate-100 text-slate-800 border-slate-200"
        };

        expensesList.forEach(exp => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-50 transition-colors";

            const badgeClass = categoryColors[exp.category] || "bg-slate-100 text-slate-800 border-slate-200";

            tr.innerHTML = `
                <td class="py-3 px-3 font-semibold text-slate-600 whitespace-nowrap">
                    ${escapeHtml(exp.date || exp.expense_date)}
                </td>
                <td class="py-3 px-3 whitespace-nowrap">
                    <span class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${badgeClass}">
                        ${escapeHtml(exp.category)}
                    </span>
                </td>
                <td class="py-3 px-3 font-medium text-slate-800 max-w-xs truncate" title="${escapeHtml(exp.description)}">
                    ${escapeHtml(exp.description)}
                </td>
                <td class="py-3 px-3 text-right font-black text-slate-900 whitespace-nowrap">
                    ₹${(parseFloat(exp.amount) || 0).toFixed(2)}
                </td>
                <td class="py-3 px-3 text-center whitespace-nowrap">
                    <div class="flex items-center justify-center gap-1.5">
                        <button 
                            class="edit-expense-btn w-7 h-7 rounded-lg bg-slate-100 hover:bg-teal-100 text-slate-600 hover:text-teal-700 transition-all flex items-center justify-center cursor-pointer"
                            data-id="${exp.id}"
                            title="Edit expense"
                        >
                            <i class="fa-solid fa-pencil text-[11px]"></i>
                        </button>
                        <button 
                            class="delete-expense-btn w-7 h-7 rounded-lg bg-slate-100 hover:bg-rose-100 text-slate-600 hover:text-rose-700 transition-all flex items-center justify-center cursor-pointer"
                            data-id="${exp.id}"
                            title="Delete expense"
                        >
                            <i class="fa-solid fa-trash-can text-[11px]"></i>
                        </button>
                    </div>
                </td>
            `;

            tbody.appendChild(tr);
        });

        // Bind Edit & Delete Button Event Listeners
        tbody.querySelectorAll(".edit-expense-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const id = parseInt(btn.dataset.id, 10);
                openEditModal(id);
            });
        });

        tbody.querySelectorAll(".delete-expense-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const id = parseInt(btn.dataset.id, 10);
                openDeleteModal(id);
            });
        });
    }

    // -------------------------------------------------------------
    // 4. Create New Expense (Duplicate submission prevented)
    // -------------------------------------------------------------
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert(formAlert);
        clearFormErrors();

        const amountVal = parseFloat(amountInput.value);
        const dateVal = dateInput.value.trim();
        const categoryVal = categoryInput.value.trim();
        const descriptionVal = descriptionInput.value.trim();

        // Validation
        let hasError = false;

        if (isNaN(amountVal) || amountVal <= 0) {
            showFieldError(amountError, amountInput, "Enter a valid positive amount greater than 0.");
            hasError = true;
        } else if (amountVal > 1000000) {
            showFieldError(amountError, amountInput, "Amount exceeds ₹1,000,000 limit.");
            hasError = true;
        }

        if (!dateVal || !/^\d{4}-\d{2}-\d{2}$/.test(dateVal)) {
            showFieldError(dateError, dateInput, "Please select a valid date in YYYY-MM-DD format.");
            hasError = true;
        }

        if (!categoryVal) {
            showFieldError(categoryError, categoryInput, "Please select an expense category.");
            hasError = true;
        }

        if (!descriptionVal) {
            showFieldError(descriptionError, descriptionInput, "Please enter a description for this expense.");
            hasError = true;
        } else if (descriptionVal.length > 255) {
            showFieldError(descriptionError, descriptionInput, "Description must not exceed 255 characters.");
            hasError = true;
        }

        if (hasError || isSubmitting) return;

        // Prevent Duplicate Submissions: lock button
        setButtonLoading(submitBtn, submitBtnText, submitBtnSpinner, true, "Saving...");
        isSubmitting = true;

        try {
            const res = await fetch(getApiUrl("/expenses"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    amount: amountVal,
                    date: dateVal,
                    category: categoryVal,
                    description: descriptionVal
                })
            });

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || "Failed to create expense.");
            }

            // Success: clear form & refresh
            form.reset();
            dateInput.value = today;
            showAlert(formAlert, formAlertText, "Expense saved successfully!", true);

            // Prepend new expense or reload from database
            await loadExpenses();

            setTimeout(() => {
                hideAlert(formAlert);
            }, 3500);

        } catch (err) {
            console.error("Create expense error:", err);
            showAlert(formAlert, formAlertText, err.message || "Failed to save expense.");
        } finally {
            setButtonLoading(submitBtn, submitBtnText, submitBtnSpinner, false, "Save Expense");
            isSubmitting = false;
        }
    });

    // -------------------------------------------------------------
    // 5. Edit Expense Flow
    // -------------------------------------------------------------
    function openEditModal(expenseId) {
        const exp = expensesList.find(item => item.id === expenseId);
        if (!exp) return;

        editIdInput.value = exp.id;
        editAmountInput.value = exp.amount;
        editDateInput.value = exp.date || exp.expense_date;
        editCategoryInput.value = exp.category;
        editDescInput.value = exp.description;
        hideAlert(editAlert);

        editModal.classList.remove("hidden");
    }

    function closeEditModal() {
        editModal.classList.add("hidden");
        hideAlert(editAlert);
    }

    if (closeEditBtn) closeEditBtn.addEventListener("click", closeEditModal);
    if (cancelEditBtn) cancelEditBtn.addEventListener("click", closeEditModal);

    editForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert(editAlert);

        const expId = parseInt(editIdInput.value, 10);
        const amountVal = parseFloat(editAmountInput.value);
        const dateVal = editDateInput.value.trim();
        const categoryVal = editCategoryInput.value.trim();
        const descriptionVal = editDescInput.value.trim();

        if (isNaN(amountVal) || amountVal <= 0) {
            showAlert(editAlert, editAlertText, "Enter a valid positive amount.");
            return;
        }

        if (!dateVal) {
            showAlert(editAlert, editAlertText, "Date is required.");
            return;
        }

        if (!categoryVal || !descriptionVal) {
            showAlert(editAlert, editAlertText, "Category and description are required.");
            return;
        }

        // Prevent Duplicate Submissions
        setButtonLoading(saveEditBtn, saveEditText, saveEditSpinner, true, "Saving...");

        try {
            const res = await fetch(getApiUrl(`/expenses/${expId}`), {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    amount: amountVal,
                    date: dateVal,
                    category: categoryVal,
                    description: descriptionVal
                })
            });

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.message || "Failed to update expense.");
            }

            closeEditModal();
            showAlert(listAlert, listAlertText, "Expense updated successfully!", true);
            await loadExpenses();

            setTimeout(() => {
                hideAlert(listAlert);
            }, 3000);

        } catch (err) {
            console.error("Update error:", err);
            showAlert(editAlert, editAlertText, err.message || "Failed to update record.");
        } finally {
            setButtonLoading(saveEditBtn, saveEditText, saveEditSpinner, false, "Save Changes");
        }
    });

    // -------------------------------------------------------------
    // 6. Delete Expense Flow
    // -------------------------------------------------------------
    function openDeleteModal(expenseId) {
        pendingDeleteId = expenseId;
        deleteModal.classList.remove("hidden");
    }

    function closeDeleteModal() {
        pendingDeleteId = null;
        deleteModal.classList.add("hidden");
    }

    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener("click", closeDeleteModal);

    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener("click", async () => {
            if (!pendingDeleteId) return;

            setButtonLoading(confirmDeleteBtn, confirmDeleteText, confirmDeleteSpinner, true, "Deleting...");

            try {
                const res = await fetch(getApiUrl(`/expenses/${pendingDeleteId}`), {
                    method: "DELETE",
                    credentials: "include"
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || "Failed to delete expense.");
                }

                closeDeleteModal();
                showAlert(listAlert, listAlertText, "Expense deleted successfully.", true);
                await loadExpenses();

                setTimeout(() => {
                    hideAlert(listAlert);
                }, 3000);

            } catch (err) {
                console.error("Delete error:", err);
                showAlert(listAlert, listAlertText, err.message || "Failed to delete record.");
                closeDeleteModal();
            } finally {
                setButtonLoading(confirmDeleteBtn, confirmDeleteText, confirmDeleteSpinner, false, "Delete Record");
            }
        });
    }

    // -------------------------------------------------------------
    // Form Utility Helpers
    // -------------------------------------------------------------
    function showFieldError(errorEl, inputEl, message) {
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove("hidden");
        }
        if (inputEl) {
            inputEl.classList.add("border-rose-400", "focus:ring-rose-400");
        }
    }

    function clearFormErrors() {
        [amountError, dateError, categoryError, descriptionError].forEach(el => {
            if (el) el.classList.add("hidden");
        });
        [amountInput, dateInput, categoryInput, descriptionInput].forEach(el => {
            if (el) el.classList.remove("border-rose-400", "focus:ring-rose-400");
        });
    }

    // Real-time error clearing on input
    [amountInput, dateInput, categoryInput, descriptionInput].forEach(input => {
        if (input) {
            input.addEventListener("input", clearFormErrors);
        }
    });

    function setButtonLoading(btn, textEl, spinnerEl, isLoading, text) {
        if (!btn) return;
        btn.disabled = isLoading;
        if (textEl) textEl.textContent = text;
        if (spinnerEl) {
            if (isLoading) spinnerEl.classList.remove("hidden");
            else spinnerEl.classList.add("hidden");
        }
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Retry and refresh button event listeners
    if (retryBtn) retryBtn.addEventListener("click", loadExpenses);
    if (refreshBtn) refreshBtn.addEventListener("click", loadExpenses);

    // Initial Load
    loadExpenses();
});
