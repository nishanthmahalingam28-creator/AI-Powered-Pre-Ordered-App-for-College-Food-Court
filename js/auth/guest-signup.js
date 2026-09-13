const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', () => {
    const guestSignUpForm = document.getElementById('guestSignUpForm');
    const pwdInput = document.getElementById('guestPassword');
    const togglePwdBtn = document.getElementById('toggleGuestPassword');
    const confirmPwdInput = document.getElementById('confirmGuestPassword');
    const toggleConfirmPwdBtn = document.getElementById('toggleConfirmGuestPassword');
    const mismatchMessage = document.getElementById('guestMismatchMessage');
    const fullNameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('guestEmail');

    // Setup or retrieve alert container
    let alertBox = document.getElementById('guest-signup-alert');
    if (!alertBox && guestSignUpForm) {
        alertBox = document.createElement('div');
        alertBox.id = 'guest-signup-alert';
        alertBox.className = 'hidden p-3.5 mb-4 rounded-xl text-xs font-semibold flex items-center gap-2';
        guestSignUpForm.parentNode.insertBefore(alertBox, guestSignUpForm);
    }

    // Password Visibility Toggle
    function setupPasswordToggle(btn, input) {
        if (btn && input) {
            btn.addEventListener('click', () => {
                const isPassword = input.getAttribute('type') === 'password';
                input.setAttribute('type', isPassword ? 'text' : 'password');
                btn.textContent = isPassword ? '🙈' : '👁️';
            });
        }
    }
    setupPasswordToggle(togglePwdBtn, pwdInput);
    setupPasswordToggle(toggleConfirmPwdBtn, confirmPwdInput);

    // Live Password Match Validation
    function validatePasswords() {
        if (!confirmPwdInput.value) {
            if (mismatchMessage) mismatchMessage.classList.add('hidden');
            return true;
        }

        const matches = pwdInput.value === confirmPwdInput.value;
        if (mismatchMessage) {
            mismatchMessage.classList.toggle('hidden', matches);
        }
        return matches;
    }

    if (pwdInput && confirmPwdInput) {
        pwdInput.addEventListener('input', validatePasswords);
        confirmPwdInput.addEventListener('input', validatePasswords);
    }

    // Form Registration Submission
    if (guestSignUpForm) {
        guestSignUpForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            if (!validatePasswords()) {
                confirmPwdInput.focus();
                return;
            }

            const fullName = (fullNameInput?.value || '').trim();
            const email = (emailInput?.value || '').trim().toLowerCase();
            const password = pwdInput.value;
            const submitBtn = guestSignUpForm.querySelector('button[type="submit"]');
            const originalBtn = submitBtn ? submitBtn.innerHTML : '';

            alertBox.className = 'hidden';

            if (!fullName || !email || !password) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> All fields are required.';
                return;
            }

            try {
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Registering Guest...';
                }

                const response = await fetch(`${API_BASE_URL}/auth/customer/signup`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        fullName: fullName,
                        email: email,
                        password: password,
                        customerType: 'guest',
                        mobile: '9876543200'
                    })
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                    alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${result.message || 'Registration failed.'}`;
                    return;
                }

                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Guest account registered successfully! Redirecting to sign in...';

                setTimeout(() => {
                    window.location.href = 'guest-login.html';
                }, 1000);

            } catch (err) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to registration server.';
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtn;
                }
            }
        });
    }
});