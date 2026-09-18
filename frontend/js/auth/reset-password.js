/**
 * Reset Password Client Controller.
 * 
 * Strict Guarantees:
 * 1. ZERO usage of localStorage or sessionStorage for reset tokens.
 * 2. Token resides exclusively in private JavaScript module memory during the active session.
 * 3. Immediate token validity verification on page load.
 * 4. Interactive password complexity checklist.
 * 5. Loading states and duplicate request prevention.
 */

document.addEventListener("DOMContentLoaded", async () => {
    const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === "function" ? window.getApiUrl("") : "/api");

    // Elements
    const tokenCheckingState = document.getElementById("tokenCheckingState");
    const tokenInvalidState = document.getElementById("tokenInvalidState");
    const successState = document.getElementById("successState");
    const resetPasswordForm = document.getElementById("resetPasswordForm");
    const userEmailTarget = document.getElementById("userEmailTarget");
    const subHeaderPrompt = document.getElementById("subHeaderPrompt");

    const passwordInput = document.getElementById("password");
    const confirmPasswordInput = document.getElementById("confirmPassword");
    const passwordError = document.getElementById("passwordError");
    const confirmPasswordError = document.getElementById("confirmPasswordError");

    const togglePasswordBtn = document.getElementById("togglePasswordBtn");
    const passwordEyeIcon = document.getElementById("passwordEyeIcon");
    const toggleConfirmBtn = document.getElementById("toggleConfirmBtn");
    const confirmEyeIcon = document.getElementById("confirmEyeIcon");

    const submitBtn = document.getElementById("submitBtn");
    const submitBtnText = document.getElementById("submitBtnText");
    const submitBtnIcon = document.getElementById("submitBtnIcon");

    const alertBanner = document.getElementById("alertBanner");
    const alertIcon = document.getElementById("alertIcon");
    const alertMessage = document.getElementById("alertMessage");

    // Requirement items
    const reqLength = document.getElementById("req-length");
    const reqLetter = document.getElementById("req-letter");
    const reqNumber = document.getElementById("req-number");
    const reqMatch = document.getElementById("req-match");

    // In-memory token storage (NEVER written to localStorage or cookies)
    let memoryToken = "";
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

    // Toggle Password Visibility
    if (togglePasswordBtn) {
        togglePasswordBtn.addEventListener("click", () => {
            const isPassword = passwordInput.type === "password";
            passwordInput.type = isPassword ? "text" : "password";
            passwordEyeIcon.className = isPassword ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
        });
    }

    if (toggleConfirmBtn) {
        toggleConfirmBtn.addEventListener("click", () => {
            const isPassword = confirmPasswordInput.type === "password";
            confirmPasswordInput.type = isPassword ? "text" : "password";
            confirmEyeIcon.className = isPassword ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
        });
    }

    // Interactive Requirement Checklist
    function updateChecklist() {
        const pwd = passwordInput.value;
        const confirm = confirmPasswordInput.value;

        // Length >= 8
        if (pwd.length >= 8) {
            reqLength.className = "flex items-center gap-1.5 text-emerald-600 font-semibold";
            reqLength.innerHTML = '<i class="fa-solid fa-circle-check text-[10px]"></i> At least 8 characters';
        } else {
            reqLength.className = "flex items-center gap-1.5 text-slate-400";
            reqLength.innerHTML = '<i class="fa-solid fa-circle-dot text-[10px]"></i> At least 8 characters';
        }

        // Has letters
        if (/[A-Za-z]/.test(pwd)) {
            reqLetter.className = "flex items-center gap-1.5 text-emerald-600 font-semibold";
            reqLetter.innerHTML = '<i class="fa-solid fa-circle-check text-[10px]"></i> Contains letters (A-Z, a-z)';
        } else {
            reqLetter.className = "flex items-center gap-1.5 text-slate-400";
            reqLetter.innerHTML = '<i class="fa-solid fa-circle-dot text-[10px]"></i> Contains letters (A-Z, a-z)';
        }

        // Has numbers
        if (/\d/.test(pwd)) {
            reqNumber.className = "flex items-center gap-1.5 text-emerald-600 font-semibold";
            reqNumber.innerHTML = '<i class="fa-solid fa-circle-check text-[10px]"></i> Contains numbers (0-9)';
        } else {
            reqNumber.className = "flex items-center gap-1.5 text-slate-400";
            reqNumber.innerHTML = '<i class="fa-solid fa-circle-dot text-[10px]"></i> Contains numbers (0-9)';
        }

        // Passwords match
        if (pwd && confirm && pwd === confirm) {
            reqMatch.className = "flex items-center gap-1.5 text-emerald-600 font-semibold";
            reqMatch.innerHTML = '<i class="fa-solid fa-circle-check text-[10px]"></i> Passwords match';
        } else {
            reqMatch.className = "flex items-center gap-1.5 text-slate-400";
            reqMatch.innerHTML = '<i class="fa-solid fa-circle-dot text-[10px]"></i> Passwords match';
        }
    }

    passwordInput.addEventListener("input", () => {
        passwordError.classList.add("hidden");
        updateChecklist();
        hideAlert();
    });

    confirmPasswordInput.addEventListener("input", () => {
        confirmPasswordError.classList.add("hidden");
        updateChecklist();
        hideAlert();
    });

    // 1. Read & Verify Token
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get("token") || "";

    if (!tokenFromUrl) {
        tokenCheckingState.classList.add("hidden");
        tokenInvalidState.classList.remove("hidden");
        return;
    }

    memoryToken = tokenFromUrl;

    try {
        const res = await fetch(`${API_BASE_URL}/auth/password/reset/verify?token=${encodeURIComponent(memoryToken)}`, {
            credentials: "include"
        });
        const data = await res.json();

        tokenCheckingState.classList.add("hidden");

        if (!res.ok || !data.valid) {
            tokenInvalidState.classList.remove("hidden");
            return;
        }

        // Token is valid: reveal form
        if (userEmailTarget && data.email) {
            userEmailTarget.textContent = data.email;
        }
        resetPasswordForm.classList.remove("hidden");
        passwordInput.focus();

    } catch (err) {
        console.error("Token verification network error:", err);
        tokenCheckingState.classList.add("hidden");
        tokenInvalidState.classList.remove("hidden");
        return;
    }

    // 2. Submit Password Reset
    resetPasswordForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        let hasError = false;

        if (!password) {
            passwordError.textContent = "Please enter a new password.";
            passwordError.classList.remove("hidden");
            hasError = true;
        } else if (password.length < 8) {
            passwordError.textContent = "Password must contain at least 8 characters.";
            passwordError.classList.remove("hidden");
            hasError = true;
        } else if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
            passwordError.textContent = "Password must contain both letters and numbers.";
            passwordError.classList.remove("hidden");
            hasError = true;
        }

        if (!confirmPassword) {
            confirmPasswordError.textContent = "Please confirm your new password.";
            confirmPasswordError.classList.remove("hidden");
            hasError = true;
        } else if (password !== confirmPassword) {
            confirmPasswordError.textContent = "Passwords do not match.";
            confirmPasswordError.classList.remove("hidden");
            hasError = true;
        }

        if (hasError) return;

        if (isSubmitting) return;
        isSubmitting = true;

        // UI Loading State
        submitBtn.disabled = true;
        passwordInput.disabled = true;
        confirmPasswordInput.disabled = true;
        submitBtnText.textContent = "Updating Password...";
        submitBtnIcon.className = "fa-solid fa-spinner fa-spin text-xs";
        hideAlert();

        try {
            const res = await fetch(`${API_BASE_URL}/auth/password/reset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    token: memoryToken,
                    password: password,
                    confirmPassword: confirmPassword
                })
            });

            const data = await res.json();

            if (!res.ok || !data.success) {
                showAlert(data.message || "Failed to reset password. Please request a new reset link.", true);
                submitBtn.disabled = false;
                passwordInput.disabled = false;
                confirmPasswordInput.disabled = false;
                submitBtnText.textContent = "Reset Password";
                submitBtnIcon.className = "fa-solid fa-arrow-right text-xs";
                isSubmitting = false;
                return;
            }

            // Success: clear token memory and reveal success screen
            memoryToken = "";
            passwordInput.value = "";
            confirmPasswordInput.value = "";
            resetPasswordForm.classList.add("hidden");
            if (subHeaderPrompt) subHeaderPrompt.classList.add("hidden");
            successState.classList.remove("hidden");

        } catch (err) {
            console.error("Password reset error:", err);
            showAlert("Network request failed. Please check your connection and retry.", true);
            submitBtn.disabled = false;
            passwordInput.disabled = false;
            confirmPasswordInput.disabled = false;
            submitBtnText.textContent = "Reset Password";
            submitBtnIcon.className = "fa-solid fa-arrow-right text-xs";
            isSubmitting = false;
        }
    });
});
