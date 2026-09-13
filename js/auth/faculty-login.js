const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const emailInput = document.getElementById('email');

    // Setup or retrieve alert container
    let alertBox = document.getElementById('faculty-login-alert');
    if (!alertBox && loginForm) {
        alertBox = document.createElement('div');
        alertBox.id = 'faculty-login-alert';
        alertBox.className = 'hidden p-3.5 mb-4 rounded-xl text-xs font-semibold flex items-center gap-2';
        loginForm.parentNode.insertBefore(alertBox, loginForm);
    }

    // Password visibility toggle
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            togglePasswordBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const email = (emailInput?.value || '').trim();
            const password = passwordInput?.value || '';
            const submitBtn = loginForm.querySelector('button[type="submit"]');
            const originalBtn = submitBtn ? submitBtn.innerHTML : '';

            alertBox.className = 'hidden';

            if (!email || !password) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Email and password are required.';
                return;
            }

            try {
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Authenticating...';
                }

                const response = await fetch(`${API_BASE_URL}/auth/customer/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        email: email,
                        password: password,
                        customerType: 'faculty'
                    })
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                    alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${result.message || 'Invalid institutional credentials.'}`;
                    return;
                }

                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Welcome back, Professor! Redirecting to dashboard...';

                if (result.user) {
                    sessionStorage.setItem('foodCourtUser', JSON.stringify(result.user));
                }

                setTimeout(() => {
                    window.location.href = '../customer/dashboard.html';
                }, 700);

            } catch (err) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Unable to connect to authentication server. Verify Flask API is active.';
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtn;
                }
            }
        });
    }
});