const API_BASE_URL = window.FOOD_COURT_API_BASE;

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

    // Mobile & OTP elements
    const mobileNumberInput = document.getElementById('mobileNumber');
    const sendOtpBtn = document.getElementById('sendOtpBtn');
    const otpContainer = document.getElementById('otpContainer');
    const otpInput = document.getElementById('otpInput');
    const verifyOtpBtn = document.getElementById('verifyOtpBtn');
    const mobileError = document.getElementById('mobileError');
    const otpError = document.getElementById('otpError');
    const otpSuccess = document.getElementById('otpSuccess');

    let isOtpVerified = false;

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

    // OTP Send Handler
    if (sendOtpBtn) {
        sendOtpBtn.addEventListener('click', async () => {
            const mobileVal = (mobileNumberInput?.value || '').trim();
            const phonePattern = /^[6-9]\d{9}$/;

            if (mobileError) mobileError.innerHTML = '';
            if (otpSuccess) otpSuccess.innerHTML = '';
            if (otpError) otpError.innerHTML = '';

            if (!phonePattern.test(mobileVal)) {
                if (mobileError) mobileError.innerHTML = 'Enter a valid 10-digit Indian mobile number (e.g. 9876543210)';
                return;
            }

            sendOtpBtn.disabled = true;
            sendOtpBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Sending...';

            try {
                const res = await fetch(`${API_BASE_URL}/auth/otp/send`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mobile: mobileVal, purpose: 'signup' })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    if (otpContainer) otpContainer.classList.remove('hidden');
                    if (otpSuccess) otpSuccess.innerHTML = `OTP sent to +91 ${mobileVal}. ${data.demo_otp ? '(Demo OTP: <strong>' + data.demo_otp + '</strong>)' : ''}`;
                    if (data.demo_otp && otpInput) {
                        otpInput.value = data.demo_otp;
                    }
                } else {
                    if (mobileError) mobileError.innerHTML = data.message || 'Failed to dispatch OTP.';
                }
            } catch (e) {
                if (mobileError) mobileError.innerHTML = 'Unable to connect to OTP service.';
            } finally {
                sendOtpBtn.disabled = false;
                sendOtpBtn.innerHTML = 'Send OTP';
            }
        });
    }

    // OTP Verify Handler
    if (verifyOtpBtn) {
        verifyOtpBtn.addEventListener('click', async () => {
            const enteredOtp = (otpInput?.value || '').trim();
            const mobileVal = (mobileNumberInput?.value || '').trim();

            if (otpError) otpError.innerHTML = '';
            if (otpSuccess) otpSuccess.innerHTML = '';

            if (!enteredOtp) {
                if (otpError) otpError.innerHTML = 'Please enter the 6-digit OTP code.';
                return;
            }

            verifyOtpBtn.disabled = true;
            verifyOtpBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Verifying...';

            try {
                const res = await fetch(`${API_BASE_URL}/auth/otp/verify`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mobile: mobileVal, code: enteredOtp, purpose: 'signup' })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    isOtpVerified = true;
                    if (otpSuccess) otpSuccess.innerHTML = 'Mobile number verified successfully! ✓';
                    if (mobileNumberInput) mobileNumberInput.disabled = true;
                    sendOtpBtn.disabled = true;
                    sendOtpBtn.classList.add('opacity-50', 'cursor-not-allowed');
                    verifyOtpBtn.disabled = true;
                    verifyOtpBtn.classList.add('opacity-50', 'cursor-not-allowed');
                    if (otpInput) otpInput.disabled = true;
                } else {
                    if (otpError) otpError.innerHTML = data.message || 'Invalid OTP code.';
                }
            } catch (e) {
                if (otpError) otpError.innerHTML = 'Unable to verify OTP.';
            } finally {
                if (!isOtpVerified) {
                    verifyOtpBtn.disabled = false;
                    verifyOtpBtn.innerHTML = 'Verify OTP';
                }
            }
        });
    }

    // Invalidate OTP if mobile changes
    if (mobileNumberInput) {
        mobileNumberInput.addEventListener('input', () => {
            if (isOtpVerified) {
                isOtpVerified = false;
                sendOtpBtn.disabled = false;
                sendOtpBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                verifyOtpBtn.disabled = false;
                verifyOtpBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                if (otpInput) otpInput.disabled = false;
                if (otpSuccess) otpSuccess.innerHTML = '';
            }
        });
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
            const mobile = (mobileNumberInput?.value || '').trim();
            const submitBtn = signUpForm.querySelector('button[type="submit"]');
            const originalBtn = submitBtn ? submitBtn.innerHTML : '';

            alertBox.className = 'hidden';

            if (!fullName || !email || !password || !facultyId || !mobile) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> All fields including mobile number are required.';
                return;
            }

            if (!isOtpVerified) {
                alertBox.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 flex items-center gap-2';
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Please verify your mobile number with OTP first.';
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
                        mobile: mobile
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