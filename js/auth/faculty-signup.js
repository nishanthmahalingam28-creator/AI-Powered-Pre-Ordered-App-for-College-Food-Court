const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', () => {
    const signUpForm = document.getElementById('signUpForm');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const toggleConfirmPasswordBtn = document.getElementById('toggleConfirmPassword');
    const rollNumberInput = document.getElementById('rollNumber');
    const fullNameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('email');
    const mismatchMessage = document.getElementById('passwordMismatchMessage');

    // Setup or retrieve alert container
    let alertBox = document.getElementById('faculty-signup-alert');
    if (!alertBox && signUpForm) {
        alertBox = document.createElement('div');
        alertBox.id = 'faculty-signup-alert';
        alertBox.className = 'hidden p-3.5 mb-4 rounded-xl text-xs font-semibold flex items-center gap-2';
        signUpForm.parentNode.insertBefore(alertBox, signUpForm);
    }

    // Uppercase Faculty ID
    if (rollNumberInput) {
        rollNumberInput.addEventListener('input', (e) => {
            const start = e.target.selectionStart;
            const end = e.target.selectionEnd;
            e.target.value = e.target.value.toUpperCase();
            e.target.setSelectionRange(start, end);
        });
    }

    // Toggle password character visibility
    function setupPasswordToggle(btn, input) {
        if (btn && input) {
            btn.addEventListener('click', () => {
                const isPassword = input.getAttribute('type') === 'password';
                input.setAttribute('type', isPassword ? 'text' : 'password');
                btn.textContent = isPassword ? '🙈' : '👁️';
            });
        }
    }
    setupPasswordToggle(togglePasswordBtn, passwordInput);
    setupPasswordToggle(toggleConfirmPasswordBtn, confirmPasswordInput);

    // Live password match verification
    function checkPasswords() {
        if (!confirmPasswordInput?.value) {
            if (mismatchMessage) mismatchMessage.classList.add('hidden');
            return true;
        }
        const matches = passwordInput.value === confirmPasswordInput.value;
        if (mismatchMessage) {
            mismatchMessage.classList.toggle('hidden', matches);
        }
        return matches;
    }

    if (passwordInput && confirmPasswordInput) {
        passwordInput.addEventListener('input', checkPasswords);
        confirmPasswordInput.addEventListener('input', checkPasswords);
    }

    // Registration submission
    if (signUpForm) {
        signUpForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            if (!checkPasswords()) {
                confirmPasswordInput.focus();
                return;
            }

            const fullName = (fullNameInput?.value || '').trim();
            const email = (emailInput?.value || '').trim().toLowerCase();
            const password = passwordInput?.value || '';
            const facultyId = (rollNumberInput?.value || '').trim();
            const submitBtn = signUpForm.querySelector('button[type="submit"]');
            const originalBtn = submitBtn ? submitBtn.innerHTML : '';

            alertBox.className = 'hidden';

            if (!fullName || !email || !password || !facultyId) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> All fields are required.';
                return;
            }

            if (!email.endsWith('@kpriet.ac.in')) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Institutional email must end with @kpriet.ac.in.';
                return;
            }

            try {
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Registering Faculty Account...';
                }

                const response = await fetch(`${API_BASE_URL}/auth/customer/signup`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        fullName: fullName,
                        email: email,
                        password: password,
                        customerType: 'faculty',
                        identifier: facultyId,
                        mobile: '9876543210'
                    })
                });

                const result = await response.json();

                if (!response.ok || !result.success) {
                    alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                    alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${result.message || 'Registration failed.'}`;
                    return;
                }

                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Faculty account registered successfully! Redirecting to login...';

                setTimeout(() => {
                    window.location.href = 'faculty-login.html';
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