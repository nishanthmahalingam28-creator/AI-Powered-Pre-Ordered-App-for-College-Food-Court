/**
 * KPRIET AI Financial Assistant Client Controller
 * 
 * Strict Guarantees:
 * 1. Zero AI API keys in frontend JavaScript.
 * 2. Multi-tenant security: All requests rely strictly on authenticated backend session.
 * 3. Loading state and duplicate request prevention.
 * 4. Graceful handling of API errors and network disruptions with fallback messaging.
 * 5. Factual financial context: Zero invented data when user has 0 transactions.
 */

document.addEventListener("DOMContentLoaded", async () => {
    // -------------------------------------------------------------
    // 1. API Configuration & Storage Sanitization
    // -------------------------------------------------------------
    const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "http://127.0.0.1:5000/api");

    // Elements
    const chatForm = document.getElementById("chat-form");
    const userQueryInput = document.getElementById("user-query-input");
    const sendQueryBtn = document.getElementById("send-query-btn");
    const sendBtnText = document.getElementById("send-btn-text");
    const sendBtnIcon = document.getElementById("send-btn-icon");
    const chatMessagesContainer = document.getElementById("chat-messages");
    const typingIndicator = document.getElementById("typing-indicator");
    const charCounter = document.getElementById("char-counter");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const errorBanner = document.getElementById("ai-error-banner");
    const errorMessageEl = document.getElementById("ai-error-message");
    const errorRetryBtn = document.getElementById("ai-error-retry-btn");
    const assistantStatusBadge = document.getElementById("assistant-status-badge");

    // Context Strip Elements
    const ctxBalanceEl = document.getElementById("ctx-balance");
    const ctxIncomeEl = document.getElementById("ctx-income");
    const ctxExpensesEl = document.getElementById("ctx-expenses");
    const ctxBudgetsEl = document.getElementById("ctx-budgets");

    // Quick Prompts
    const quickPromptBtns = document.querySelectorAll(".quick-prompt-btn");

    // State Variables
    let currentUser = null;
    let isRequestPending = false;
    let lastQueryAttempted = "";
    let financialContext = {
        totalIncome: 0,
        totalExpenses: 0,
        balance: 0,
        budgetsCount: 0,
        hasHistory: false
    };

    // -------------------------------------------------------------
    // 2. Authentication Verification
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
            console.error("Authentication check failed:", err);
            window.location.href = "../auth/login.html";
            return false;
        }
    }

    const authenticated = await verifyAuthentication();
    if (!authenticated) return;

    // -------------------------------------------------------------
    // 3. Financial Context Loader
    // -------------------------------------------------------------
    async function loadFinancialContext() {
        try {
            const res = await fetch(`${API_BASE_URL}/customer/financial-summary`, { credentials: "include" });
            if (res.ok) {
                const data = await res.json();
                if (data.success && data.summary) {
                    const s = data.summary;
                    financialContext.totalIncome = Number(s.total_income || 0);
                    financialContext.totalExpenses = Number(s.total_expenses || 0);
                    financialContext.balance = Number(s.balance || 0);
                    financialContext.budgetsCount = Array.isArray(s.budgets) ? s.budgets.length : (s.active_budgets_count || 0);
                    financialContext.hasHistory = (financialContext.totalIncome > 0 || financialContext.totalExpenses > 0 || financialContext.budgetsCount > 0);

                    // Update UI Context Strip
                    if (ctxBalanceEl) ctxBalanceEl.textContent = `₹${financialContext.balance.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    if (ctxIncomeEl) ctxIncomeEl.textContent = `₹${financialContext.totalIncome.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    if (ctxExpensesEl) ctxExpensesEl.textContent = `₹${financialContext.totalExpenses.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    if (ctxBudgetsEl) ctxBudgetsEl.textContent = `${financialContext.budgetsCount} Active`;
                }
            }
        } catch (err) {
            console.warn("Could not fetch financial summary for header strip:", err);
        }
    }

    // -------------------------------------------------------------
    // 4. Markdown Formatter Helper
    // -------------------------------------------------------------
    function renderMarkdown(text) {
        if (!text) return "";
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Headers
        escaped = escaped.replace(/^### (.*$)/gim, '<h4 class="font-black text-slate-900 text-sm mt-3 mb-1.5">$1</h4>');
        escaped = escaped.replace(/^## (.*$)/gim, '<h3 class="font-black text-slate-900 text-base mt-3.5 mb-2">$1</h3>');
        escaped = escaped.replace(/^# (.*$)/gim, '<h2 class="font-black text-slate-900 text-lg mt-4 mb-2">$1</h2>');

        // Bold & Italic
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-900">$1</strong>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<em class="italic text-slate-700">$1</em>');

        // Inline Code
        escaped = escaped.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-slate-100 rounded text-teal-800 text-xs font-mono">$1</code>');

        // Links
        escaped = escaped.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-teal-600 hover:text-teal-700 font-bold underline transition-colors">$1</a>');

        // Bullet lists
        escaped = escaped.replace(/^\s*-\s+(.*$)/gim, '<li class="ml-4 list-disc text-xs sm:text-sm text-slate-700 leading-relaxed my-0.5">$1</li>');
        escaped = escaped.replace(/^\s*\*\s+(.*$)/gim, '<li class="ml-4 list-disc text-xs sm:text-sm text-slate-700 leading-relaxed my-0.5">$1</li>');

        // Numbered lists
        escaped = escaped.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ml-4 list-decimal text-xs sm:text-sm text-slate-700 leading-relaxed my-0.5">$2</li>');

        // Line breaks
        escaped = escaped.replace(/\n\n/g, '<div class="h-2"></div>');
        escaped = escaped.replace(/\n/g, '<br/>');

        return escaped;
    }

    // -------------------------------------------------------------
    // 5. Message Rendering in Chat Stream
    // -------------------------------------------------------------
    function appendUserMessage(text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "flex justify-end gap-2.5 message-user";
        msgDiv.innerHTML = `
            <div class="max-w-xl bg-gradient-to-r from-teal-600 to-cyan-600 text-white rounded-2xl rounded-tr-sm px-4 sm:px-5 py-3 shadow-md text-xs sm:text-sm leading-relaxed">
                <p class="whitespace-pre-wrap break-words">${escapeHtml(text)}</p>
                <div class="text-[10px] text-teal-100 text-right mt-1 opacity-80 font-medium">
                    ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
            </div>
            <div class="w-8 h-8 rounded-xl bg-teal-600 text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-sm">
                <i class="fa-solid fa-user"></i>
            </div>
        `;
        chatMessagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendAssistantMessage(htmlContent, source = "Advisor Engine", isError = false) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `flex gap-3 message-assistant ${isError ? "text-rose-900" : ""}`;
        
        const badgeBg = source.toLowerCase().includes("gemini")
            ? "bg-purple-100 text-purple-700 border-purple-200"
            : "bg-teal-100 text-teal-800 border-teal-200";

        msgDiv.innerHTML = `
            <div class="w-8 h-8 rounded-xl ${isError ? "bg-rose-600" : "bg-gradient-to-tr from-teal-500 to-cyan-500"} text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-sm mt-1">
                <i class="fa-solid ${isError ? "fa-triangle-exclamation" : "fa-robot"}"></i>
            </div>
            <div class="max-w-2xl bg-white border ${isError ? "border-rose-200 bg-rose-50/50" : "border-slate-200"} rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-sm text-xs sm:text-sm leading-relaxed text-slate-800">
                <div class="flex items-center gap-2 mb-2">
                    <span class="font-black text-slate-900 text-xs">KPR Financial Advisor</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeBg}">
                        ${escapeHtml(source)}
                    </span>
                    <span class="text-[10px] text-slate-400 ml-auto font-medium">
                        ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                </div>
                <div class="ai-rendered-content text-slate-700 space-y-1">
                    ${htmlContent}
                </div>
            </div>
        `;
        chatMessagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function scrollToBottom() {
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }

    // -------------------------------------------------------------
    // 6. Initial Welcome Greeting
    // -------------------------------------------------------------
    function renderInitialWelcome() {
        chatMessagesContainer.innerHTML = "";
        let greetingBody = "";

        if (!financialContext.hasHistory) {
            greetingBody = `
                <p class="font-bold text-slate-800 text-sm mb-1">Welcome to your AI Financial Assistant! 👋</p>
                <p class="text-slate-600 mb-3">
                    I am connected to your authenticated food court account. Currently, <strong>no transactions, income, or budgets have been logged</strong>.
                </p>
                <div class="p-3 bg-teal-50 border border-teal-100 rounded-xl mb-3 space-y-1.5 text-xs text-teal-950">
                    <p class="font-bold text-teal-900"><i class="fa-solid fa-circle-info text-teal-600"></i> Get Started in 3 Steps:</p>
                    <p>1. <a href="income.html" class="text-teal-700 font-bold underline">Record your monthly allowance or stipend</a>.</p>
                    <p>2. <a href="expenses.html" class="text-teal-700 font-bold underline">Log your dining and daily purchases</a>.</p>
                    <p>3. <a href="budgets.html" class="text-teal-700 font-bold underline">Define monthly budget limits</a> to stay on track.</p>
                </div>
                <p class="text-slate-500 text-xs">
                    <em>Note: We never invent or hallucinate fake numbers. Once you log your transactions, personalized analytics will unlock automatically!</em>
                </p>
            `;
        } else {
            greetingBody = `
                <p class="font-bold text-slate-800 text-sm mb-1">Welcome back, ${escapeHtml(currentUser.name || "Customer")}! 👋</p>
                <p class="text-slate-600 mb-2">
                    I have synced your authentic financial records. You currently hold a net balance of 
                    <strong class="text-slate-900">₹${financialContext.balance.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong> 
                    across your campus dining and pocket funds.
                </p>
                <p class="text-slate-600 mb-2">
                    You can ask me to evaluate your dining budget, calculate your current savings rate, or recommend daily food court spending caps.
                </p>
            `;
        }

        appendAssistantMessage(greetingBody, "Secure Advisor", false);
    }

    // -------------------------------------------------------------
    // 7. Request Handler with Duplicate Prevention & Error Fallbacks
    // -------------------------------------------------------------
    async function submitQuery(queryText) {
        const cleanQuery = (queryText || "").trim();
        if (!cleanQuery) return;

        if (cleanQuery.length > 1000) {
            showError("Your prompt exceeds the 1000 character limit. Please shorten your message.");
            return;
        }

        // Prevent Duplicate Requests
        if (isRequestPending) {
            console.warn("Duplicate request prevented while previous request is running.");
            return;
        }

        isRequestPending = true;
        lastQueryAttempted = cleanQuery;
        setLoadingState(true);
        hideError();

        // Append User Message to UI
        appendUserMessage(cleanQuery);
        userQueryInput.value = "";
        updateCharCounter();

        try {
            const res = await fetch(`${API_BASE_URL}/ai/assistant/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ message: cleanQuery })
            });

            const data = await res.json();

            if (!res.ok || !data.success) {
                const errMsg = data.message || `Server responded with status ${res.status}`;
                appendAssistantMessage(
                    `<p><strong>Advisor Notice:</strong> ${escapeHtml(errMsg)}</p>` +
                    `<p class="text-xs text-slate-500 mt-1">We could not process this request right now. Please try again or ask a different question.</p>`,
                    "Offline Fallback",
                    true
                );
                showError("Unable to reach the assistant service. Please retry.");
                return;
            }

            // Successful Response
            const renderedHtml = renderMarkdown(data.response || "No response generated.");
            const sourceLabel = data.source === "gemini" ? "Gemini AI" : "Financial Engine";
            appendAssistantMessage(renderedHtml, sourceLabel, false);

            // Re-sync financial context in case user logged items in another tab
            loadFinancialContext();

        } catch (err) {
            console.error("AI Request network error:", err);
            appendAssistantMessage(
                `<p><strong>Connection Interrupted:</strong> Unable to connect to the financial intelligence server.</p>` +
                `<p class="text-xs text-slate-500 mt-1">Please ensure the backend server is running and check your internet connection.</p>`,
                "Network Interruption",
                true
            );
            showError("Network request failed. Please check your connection and retry.");
        } finally {
            isRequestPending = false;
            setLoadingState(false);
            userQueryInput.focus();
        }
    }

    // -------------------------------------------------------------
    // 8. UI State Modifiers
    // -------------------------------------------------------------
    function setLoadingState(loading) {
        if (loading) {
            typingIndicator.classList.remove("hidden");
            sendQueryBtn.disabled = true;
            userQueryInput.disabled = true;
            sendBtnText.textContent = "Analyzing...";
            sendBtnIcon.className = "fa-solid fa-spinner fa-spin";
            if (assistantStatusBadge) {
                assistantStatusBadge.textContent = "Analyzing";
                assistantStatusBadge.className = "px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30";
            }
        } else {
            typingIndicator.classList.add("hidden");
            sendQueryBtn.disabled = false;
            userQueryInput.disabled = false;
            sendBtnText.textContent = "Ask AI";
            sendBtnIcon.className = "fa-solid fa-paper-plane";
            if (assistantStatusBadge) {
                assistantStatusBadge.textContent = "Ready";
                assistantStatusBadge.className = "px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-400/20 text-teal-300 border border-teal-400/30";
            }
        }
    }

    function showError(msg) {
        if (errorBanner) {
            errorMessageEl.textContent = msg;
            errorBanner.classList.remove("hidden");
        }
    }

    function hideError() {
        if (errorBanner) {
            errorBanner.classList.add("hidden");
        }
    }

    function updateCharCounter() {
        if (charCounter && userQueryInput) {
            const len = userQueryInput.value.length;
            charCounter.textContent = `${len}/1000`;
            if (len >= 950) {
                charCounter.className = "absolute bottom-2 right-3 text-[10px] text-rose-500 font-bold pointer-events-none";
            } else {
                charCounter.className = "absolute bottom-2 right-3 text-[10px] text-slate-400 pointer-events-none";
            }
        }
    }

    // -------------------------------------------------------------
    // 9. Event Listeners
    // -------------------------------------------------------------
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        submitQuery(userQueryInput.value);
    });

    userQueryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitQuery(userQueryInput.value);
        }
    });

    userQueryInput.addEventListener("input", updateCharCounter);

    // Quick Prompt Buttons
    quickPromptBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            const prompt = btn.getAttribute("data-prompt");
            if (prompt) {
                submitQuery(prompt);
            }
        });
    });

    // Retry Button
    if (errorRetryBtn) {
        errorRetryBtn.addEventListener("click", () => {
            if (lastQueryAttempted) {
                submitQuery(lastQueryAttempted);
            }
        });
    }

    // Clear Chat
    if (clearChatBtn) {
        clearChatBtn.addEventListener("click", () => {
            if (confirm("Reset current consultation conversation?")) {
                hideError();
                renderInitialWelcome();
            }
        });
    }

    // -------------------------------------------------------------
    // 10. Initialization
    // -------------------------------------------------------------
    await loadFinancialContext();
    renderInitialWelcome();
    updateCharCounter();
});
