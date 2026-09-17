/**
 * Forgot Password Client Controller.
 * 
 * Enforces:
 * 1. Client-side input validation.
 * 2. Loading state and duplicate request prevention.
 * 3. Non-enumerating success response presentation.
 * 4. Zero usage of localStorage for security tokens.
 */

document.addEventListener("DOMContentLoaded", () => {
    const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "http://127.0.0.1:5000/api");

    const form = document.getElementById("forgotPasswordForm");
    const emailInput = document.getElementById("email");
    const emailError = document.getElementById("emailError");
    const submitBtn = document.getElementById("submitBtn");
    const submitBtnText = document.getElementById("submitBtnText");
    const submitBtnIcon = document.getElementById("submitBtnIcon");
    const alertBanner = document.getElementById("alertBanner");
    const alertIcon = document.getElementById("alertIcon");
    const alertMessage = document.getElementById("alertMessage");
    const successState = document.getElementById("successState");
    const submittedEmailDisplay = document.getElementById("submittedEmailDisplay");
    const formFooter = document.getElementById("formFooter");

    let isSubmitting = false;

    function showAlert(msg, isError = true) {
        if (!alertBanner) return;
        alertMessage.textContent = msg;
        if (isError) {
            alertBanner.className = "mb-6 p-4 rounded-2xl text-xs font-semibold flex items-center gap-3 bg-rose-50 text-rose-800 border border-rose-200";
            alertIcon.className = "fa-solid fa-circle-exclamation text-rose-600 text-base shrink-0";
        } else {
            alertBanner.className = "mb-6 p-4 rounded-2xl text-xs font-semibold flex items-center gap-3 bg-emerald-50 text-emerald-800 border border-emerald-200";
            alertIcon.className = "fa-solid fa-circle-check text-emerald-600 text-base shrink-0";
        }
        alertBanner.classList.remove("hidden");
    }

    function hideAlert() {
        if (alertBanner) alertBanner.classList.add("hidden");
    }

    function validateEmail(email) {
        const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        return re.test(String(email).toLowerCase());
    }

    emailInput.addEventListener("input", () => {
        emailError.classList.add("hidden");
        emailError.textContent = "";
        hideAlert();
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const email = emailInput.value.trim().toLowerCase();

        if (!email) {
            emailError.textContent = "Please enter your email address.";
            emailError.classList.remove("hidden");
            emailInput.focus();
            return;
        }

        if (!validateEmail(email)) {
            emailError.textContent = "Please enter a valid email address.";
            emailError.classList.remove("hidden");
            emailInput.focus();
            return;
        }

        if (isSubmitting) return;
        isSubmitting = true;

        // UI Loading State
        submitBtn.disabled = true;
        emailInput.disabled = true;
        submitBtnText.textContent = "Sending Instructions...";
        submitBtnIcon.className = "fa-solid fa-spinner fa-spin text-xs";
        hideAlert();

        try {
            const res = await fetch(`${API_BASE_URL}/auth/password/forgot`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ email })
            });

            const data = await res.json();

            if (!res.ok) {
                showAlert(data.message || "Unable to process request. Please try again later.", true);
                submitBtn.disabled = false;
                emailInput.disabled = false;
                submitBtnText.textContent = "Send Reset Link";
                submitBtnIcon.className = "fa-solid fa-paper-plane text-xs";
                isSubmitting = false;
                return;
            }

            // Success state: show non-enumerating confirmation
            form.classList.add("hidden");
            if (formFooter) formFooter.classList.add("hidden");
            if (submittedEmailDisplay) submittedEmailDisplay.textContent = email;
            successState.classList.remove("hidden");

        } catch (err) {
            console.error("Forgot password request failed:", err);
            showAlert("Network communication failed. Please check your internet connection and try again.", true);
            submitBtn.disabled = false;
            emailInput.disabled = false;
            submitBtnText.textContent = "Send Reset Link";
            submitBtnIcon.className = "fa-solid fa-paper-plane text-xs";
            isSubmitting = false;
        }
    });
});
