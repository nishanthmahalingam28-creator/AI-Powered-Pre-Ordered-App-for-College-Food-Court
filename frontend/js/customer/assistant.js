/**
 * KPRIET AI Assistant Client Controller
 * Keeps the page focused on food-court assistance only.
 */

document.addEventListener("DOMContentLoaded", async () => {
    const API_BASE_URL = window.FOOD_COURT_API_BASE ||
        (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "/api");

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
    const quickPromptBtns = document.querySelectorAll(".quick-prompt-btn");

    let isRequestPending = false;
    let lastQueryAttempted = "";

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
            return true;
        } catch (err) {
            console.error("Authentication check failed:", err);
            window.location.href = "../auth/login.html";
            return false;
        }
    }

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    function renderMarkdown(text) {
        let escaped = escapeHtml(text || "");
        escaped = escaped.replace(/^### (.*$)/gim, '<h4 class="font-black text-slate-900 text-sm mt-3 mb-1.5">$1</h4>');
        escaped = escaped.replace(/^## (.*$)/gim, '<h3 class="font-black text-slate-900 text-base mt-3.5 mb-2">$1</h3>');
        escaped = escaped.replace(/^# (.*$)/gim, '<h2 class="font-black text-slate-900 text-lg mt-4 mb-2">$1</h2>');
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-900">$1</strong>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<em class="italic text-slate-700">$1</em>');
        escaped = escaped.replace(/^\s*-\s+(.*$)/gim, '<li class="ml-4 list-disc text-xs sm:text-sm text-slate-700 leading-relaxed my-0.5">$1</li>');
        escaped = escaped.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ml-4 list-decimal text-xs sm:text-sm text-slate-700 leading-relaxed my-0.5">$2</li>');
        escaped = escaped.replace(/\n\n/g, '<div class="h-2"></div>');
        escaped = escaped.replace(/\n/g, "<br/>");
        return escaped;
    }

    function scrollToBottom() {
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }

    function appendUserMessage(text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "flex justify-end gap-2.5";
        msgDiv.innerHTML = `
            <div class="max-w-xl bg-gradient-to-r from-teal-600 to-cyan-600 text-white rounded-2xl rounded-tr-sm px-4 sm:px-5 py-3 shadow-md text-xs sm:text-sm leading-relaxed">
                <p class="whitespace-pre-wrap break-words">${escapeHtml(text)}</p>
                <div class="text-[10px] text-teal-100 text-right mt-1 opacity-80">${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}</div>
            </div>
            <div class="w-8 h-8 rounded-xl bg-teal-600 text-white flex items-center justify-center text-xs font-bold shrink-0"><i class="fa-solid fa-user"></i></div>`;
        chatMessagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendAssistantMessage(htmlContent, source = "AI Assistant", isError = false) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "flex gap-3";
        msgDiv.innerHTML = `
            <div class="w-8 h-8 rounded-xl ${isError ? "bg-rose-600" : "bg-gradient-to-tr from-teal-500 to-cyan-500"} text-white flex items-center justify-center text-xs font-bold shrink-0 mt-1">
                <i class="fa-solid ${isError ? "fa-triangle-exclamation" : "fa-robot"}"></i>
            </div>
            <div class="max-w-2xl bg-white border ${isError ? "border-rose-200 bg-rose-50/50" : "border-slate-200"} rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-sm text-xs sm:text-sm leading-relaxed text-slate-800">
                <div class="flex items-center gap-2 mb-2">
                    <span class="font-black text-slate-900 text-xs">KPRIET AI Assistant</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${isError ? "bg-rose-100 text-rose-700 border-rose-200" : "bg-teal-100 text-teal-800 border-teal-200"}">${escapeHtml(source)}</span>
                    <span class="text-[10px] text-slate-400 ml-auto">${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}</span>
                </div>
                <div class="ai-rendered-content text-slate-700 space-y-1">${htmlContent}</div>
            </div>`;
        chatMessagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function renderInitialWelcome() {
        chatMessagesContainer.innerHTML = "";
        appendAssistantMessage(`
            <p class="font-bold text-slate-800 text-sm mb-1">Hi! 👋 I'm your Food Court AI Assistant.</p>
            <p class="text-slate-600">I can help you with today's available food, food recommendations, your orders, food budget, expenses, and the morning survey.</p>
            <p class="text-slate-500 text-xs mt-2">Choose a quick question below or type your own question.</p>
        `, "Ready");
    }

    function showError(message) {
        if (!errorBanner) return;
        errorMessageEl.textContent = message;
        errorBanner.classList.remove("hidden");
    }

    function hideError() {
        if (errorBanner) errorBanner.classList.add("hidden");
    }

    function updateCharCounter() {
        if (!charCounter) return;
        const len = userQueryInput.value.length;
        charCounter.textContent = `${len}/1000`;
        charCounter.className = `absolute bottom-2 right-3 text-[10px] ${len >= 950 ? "text-rose-500 font-bold" : "text-slate-400"} pointer-events-none`;
    }

    function setLoadingState(loading) {
        typingIndicator.classList.toggle("hidden", !loading);
        sendQueryBtn.disabled = loading;
        userQueryInput.disabled = loading;
        sendBtnText.textContent = loading ? "Thinking..." : "Ask AI";
        sendBtnIcon.className = loading ? "fa-solid fa-spinner fa-spin" : "fa-solid fa-paper-plane";
        if (assistantStatusBadge) {
            assistantStatusBadge.textContent = loading ? "Thinking" : "Ready";
            assistantStatusBadge.className = `px-2 py-0.5 rounded-full text-[10px] font-bold ${loading ? "bg-amber-400/20 text-amber-300 border border-amber-400/30" : "bg-teal-400/20 text-teal-300 border border-teal-400/30"}`;
        }
    }

    async function submitQuery(queryText) {
        const cleanQuery = (queryText || "").trim();
        if (!cleanQuery) return;
        if (cleanQuery.length > 1000) {
            showError("Please keep your question within 1000 characters.");
            return;
        }
        if (isRequestPending) return;

        isRequestPending = true;
        lastQueryAttempted = cleanQuery;
        hideError();
        setLoadingState(true);
        appendUserMessage(cleanQuery);
        userQueryInput.value = "";
        updateCharCounter();

        try {
            const res = await fetch(`${API_BASE_URL}/ai/assistant/chat`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "include",
                body: JSON.stringify({message: cleanQuery})
            });
            const data = await res.json();

            if (!res.ok || !data.success) {
                throw new Error(data.message || `Server responded with status ${res.status}`);
            }

            const sourceLabel = data.source === "gemini" ? "Gemini AI" : "AI Assistant";
            appendAssistantMessage(renderMarkdown(data.response || "No response generated."), sourceLabel);
        } catch (err) {
            console.error("AI request failed:", err);
            appendAssistantMessage(
                `<p><strong>Unable to get a response.</strong> ${escapeHtml(err.message || "Please try again.")}</p>`,
                "Connection Error",
                true
            );
            showError("AI Assistant is temporarily unavailable. Please retry.");
        } finally {
            isRequestPending = false;
            setLoadingState(false);
            userQueryInput.focus();
        }
    }

    const authenticated = await verifyAuthentication();
    if (!authenticated) return;

    chatForm.addEventListener("submit", (event) => {
        event.preventDefault();
        submitQuery(userQueryInput.value);
    });

    userQueryInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submitQuery(userQueryInput.value);
        }
    });

    userQueryInput.addEventListener("input", updateCharCounter);

    quickPromptBtns.forEach((button) => {
        button.addEventListener("click", () => submitQuery(button.dataset.prompt || ""));
    });

    if (errorRetryBtn) {
        errorRetryBtn.addEventListener("click", () => {
            if (lastQueryAttempted) submitQuery(lastQueryAttempted);
        });
    }

    if (clearChatBtn) {
        clearChatBtn.addEventListener("click", () => {
            hideError();
            renderInitialWelcome();
        });
    }

    renderInitialWelcome();
    updateCharCounter();
});