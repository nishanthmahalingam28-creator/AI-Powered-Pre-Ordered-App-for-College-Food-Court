const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

document.addEventListener('DOMContentLoaded', () => {
    const guestLoginForm = document.getElementById('guestLoginForm');
    const loginPwdInput = document.getElementById('password');
    const toggleLoginPwdBtn = document.getElementById('togglePassword');
    const emailInput = document.getElementById('email');

    // Setup or retrieve alert container
    let alertBox = document.getElementById('guest-login-alert');
    if (!alertBox && guestLoginForm) {
        alertBox = document.createElement('div');
        alertBox.id = 'guest-login-alert';
        alertBox.className = 'hidden p-3.5 mb-4 rounded-xl text-xs font-semibold flex items-center gap-2';
        guestLoginForm.parentNode.insertBefore(alertBox, guestLoginForm);
    }

    // Password Visibility Toggle
    if (toggleLoginPwdBtn && loginPwdInput) {
        toggleLoginPwdBtn.addEventListener('click', () => {
            const isPassword = loginPwdInput.getAttribute('type') === 'password';
            loginPwdInput.setAttribute('type', isPassword ? 'text' : 'password');
            toggleLoginPwdBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    // Form Submission
    if (guestLoginForm) {
        guestLoginForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const identifier = (emailInput?.value || '').trim();
            const password = loginPwdInput?.value || '';
            const submitBtn = guestLoginForm.querySelector('button[type="submit"]');
            const originalBtn = submitBtn ? submitBtn.innerHTML : '';

            alertBox.className = 'hidden';

            if (!identifier || !password) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Email/Mobile and password are required.';
                return;
            }

            try {
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Signing In...';
                }

                const response = await fetch(`${API_BASE_URL}/auth/customer/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        email: identifier,
                        password: password,
                        customerType: 'guest'
                    })
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                    alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${result.message || 'Invalid guest credentials.'}`;
                    return;
                }

                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Guest login successful! Entering food court...';

                if (result.user) {
                    sessionStorage.setItem('foodCourtUser', JSON.stringify(result.user));
                }

                setTimeout(() => {
                    window.location.href = '../customer/dashboard.html';
                }, 700);

            } catch (err) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Unable to connect to authentication server.';
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtn;
                }
            }
        });
    }
});