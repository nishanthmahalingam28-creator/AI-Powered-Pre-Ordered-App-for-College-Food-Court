document.addEventListener('DOMContentLoaded', () => {
    // --- Guest Sign Up DOM Elements ---
    const guestSignUpForm = document.getElementById('guestSignUpForm');
    const googleGuestSignUpBtn = document.getElementById('googleGuestSignUpBtn');
    
    const pwdInput = document.getElementById('guestPassword');
    const togglePwdBtn = document.getElementById('toggleGuestPassword');
    
    const confirmPwdInput = document.getElementById('confirmGuestPassword');
    const toggleConfirmPwdBtn = document.getElementById('toggleConfirmGuestPassword');
    
    const mismatchMessage = document.getElementById('guestMismatchMessage');

    // 1. Password Visibility Toggle (Primary Password Field)
    if (togglePwdBtn && pwdInput) {
        togglePwdBtn.addEventListener('click', () => {
            const isPassword = pwdInput.getAttribute('type') === 'password';
            pwdInput.setAttribute('type', isPassword ? 'text' : 'password');
            togglePwdBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    // 2. Password Visibility Toggle (Confirm Password Field)
    if (toggleConfirmPwdBtn && confirmPwdInput) {
        toggleConfirmPwdBtn.addEventListener('click', () => {
            const isPassword = confirmPwdInput.getAttribute('type') === 'password';
            confirmPwdInput.setAttribute('type', isPassword ? 'text' : 'password');
            toggleConfirmPwdBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    // 3. Live Password Mismatch Validation
    function validatePasswords() {
        if (!confirmPwdInput.value) {
            mismatchMessage.classList.add('hidden');
            confirmPwdInput.classList.remove('border-red-500', 'focus:ring-red-500', 'focus:border-red-500');
            return;
        }

        if (pwdInput.value !== confirmPwdInput.value) {
            mismatchMessage.classList.remove('hidden');
            confirmPwdInput.classList.add('border-red-500', 'focus:ring-red-500', 'focus:border-red-500');
            confirmPwdInput.classList.remove('focus:ring-kpr-teal', 'focus:border-kpr-teal');
        } else {
            mismatchMessage.classList.add('hidden');
            confirmPwdInput.classList.remove('border-red-500', 'focus:ring-red-500', 'focus:border-red-500');
            confirmPwdInput.classList.add('focus:ring-kpr-teal', 'focus:border-kpr-teal');
        }
    }

    if (pwdInput && confirmPwdInput) {
        pwdInput.addEventListener('input', validatePasswords);
        confirmPwdInput.addEventListener('input', validatePasswords);
    }

    // 4. Google OAuth Sign Up Handler
    if (googleGuestSignUpBtn) {
        googleGuestSignUpBtn.addEventListener('click', () => {
            console.log("Redirecting Guest user to Google Gateway Registration Pipeline...");
            // window.location.href = 'YOUR_GOOGLE_GUEST_OAUTH_SIGNUP_URL';
        });
    }

    // 5. Form Registration Pipeline
    if (guestSignUpForm) {
        guestSignUpForm.addEventListener('submit', (event) => {
            // Guard clause to prevent submission if passwords mismatch
            if (pwdInput.value !== confirmPwdInput.value) {
                event.preventDefault();
                confirmPwdInput.focus();
                return;
            }

            event.preventDefault(); // Stop standard browser reloading

            const fullName = document.getElementById('fullName').value.trim();
            const email = document.getElementById('guestEmail').value.trim();
            const password = pwdInput.value;

            console.log(`Processing new Guest registration payload for: ${email}`);
            
            // Proceed to dispatch payload to registration endpoint
            // fetch('/api/guest/register', { method: 'POST', body: JSON.stringify({ fullName, email, password }) })
        });
    }
});
const menuBtn = document.getElementById('menuBtn');
const dropdownMenu = document.getElementById('dropdownMenu');

menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdownMenu.classList.toggle('hidden');
});

// Close dropdown when clicking anywhere outside of it
document.addEventListener('click', () => {
    dropdownMenu.classList.add('hidden');
});