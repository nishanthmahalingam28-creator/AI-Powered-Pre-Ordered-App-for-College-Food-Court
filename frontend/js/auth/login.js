const customerTypeSelect = document.getElementById("customerType");
const emailLabel = document.getElementById("emailLabel");
const emailInput = document.getElementById("email");
const emailError = document.getElementById("emailError");
const passwordInput = document.getElementById("password");
const passwordError = document.getElementById("passwordError");
const loginForm = document.getElementById("loginForm");
const loginButton = loginForm?.querySelector('button[type="submit"]');

const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

function updateCustomerTypeFields() {
    if (customerTypeSelect.value === "guest") {
        emailLabel.innerText = "Email ID";
        emailInput.placeholder = "example@gmail.com";
    } else {
        emailLabel.innerText = "Institute Email ID";
        emailInput.placeholder = "example@kpriet.ac.in";
    }

    emailError.innerHTML = "";
}

customerTypeSelect?.addEventListener("change", updateCustomerTypeFields);

loginForm?.addEventListener("submit", async function (event) {
    event.preventDefault();

    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const customerType = customerTypeSelect.value;

    emailError.innerHTML = "";
    passwordError.innerHTML = "";

    let valid = true;

    if (email === "") {
        emailError.innerHTML = "Email is required";
        valid = false;
    } else if (customerType === "student" || customerType === "faculty") {
        const kprietPattern = /^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$/;
        if (!kprietPattern.test(email)) {
            emailError.innerHTML = "Enter a valid KPRIET Email (@kpriet.ac.in)";
            valid = false;
        }
    } else {
        const standardEmailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!standardEmailPattern.test(email)) {
            emailError.innerHTML = "Enter a valid email address";
            valid = false;
        }
    }

    if (password === "") {
        passwordError.innerHTML = "Password is required";
        valid = false;
    } else if (password.length < 8) {
        passwordError.innerHTML = "Password must contain at least 8 characters";
        valid = false;
    }

    if (!valid) {
        return;
    }

    const originalButtonContent = loginButton?.innerHTML;

    if (loginButton) {
        loginButton.disabled = true;
        loginButton.classList.add("opacity-70", "cursor-not-allowed");
        loginButton.innerHTML = '<span>Signing in...</span><i class="fa-solid fa-spinner fa-spin text-sm"></i>';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/customer/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify({
                customerType,
                email,
                password
            })
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok || !result.success) {
            passwordError.innerHTML = result.message || "Invalid email or password.";
            return;
        }

        // Save the signed fallback token for browsers that block the session cookie.
        if (result.auth_token) {
            localStorage.setItem("foodCourtAuthToken", result.auth_token);
        }

        // Keep only non-sensitive session information for the frontend UI.
        if (result.user) {
            sessionStorage.setItem("foodCourtUser", JSON.stringify({
                id: result.user.id,
                email: result.user.email,
                role: result.user.role,
                customer_type: result.user.customer_type,
                full_name: result.user.full_name,
                identifier: result.user.identifier
            }));
        }

        // Verify that the browser actually received the authenticated Flask session
        // cookie before leaving the login page. Without this check the UI could show
        // the cached student session while protected API calls still return 401.
        const meHeaders = {};
        const authToken = localStorage.getItem("foodCourtAuthToken");
        if (authToken) {
            meHeaders.Authorization = "Bearer " + authToken;
        }
        const meResponse = await fetch(`${API_BASE_URL}/auth/me`, {
            method: "GET",
            headers: meHeaders,
            credentials: "include",
            cache: "no-store"
        });
        const meData = await meResponse.json().catch(() => ({}));

        if (!meResponse.ok || !meData.authenticated || !meData.user) {
            sessionStorage.removeItem("foodCourtUser");
            localStorage.removeItem("foodCourtAuthToken");
            passwordError.innerHTML = "Login verification failed. Please try again.";
            return;
        }

        // Always use the authoritative server profile for the dashboard UI.
        sessionStorage.setItem("foodCourtUser", JSON.stringify(meData.user));
        window.location.href = "../customer/dashboard.html";
    } catch (error) {
        console.error("Customer login API error:", error);
        passwordError.innerHTML = "Unable to connect to the server. Start the Flask API and try again.";
    } finally {
        if (loginButton) {
            loginButton.disabled = false;
            loginButton.classList.remove("opacity-70", "cursor-not-allowed");
            loginButton.innerHTML = originalButtonContent;
        }
    }
});
