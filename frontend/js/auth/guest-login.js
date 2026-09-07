document.addEventListener('DOMContentLoaded', () => {
    // --- Guest Login DOM Elements ---
    const guestLoginForm = document.getElementById('guestLoginForm');
    const googleGuestBtn = document.getElementById('googleGuestBtn');
    const loginPwdInput = document.getElementById('password');
    const toggleLoginPwdBtn = document.getElementById('togglePassword');

    // 1. Password Visibility Toggle
    if (toggleLoginPwdBtn && loginPwdInput) {
        toggleLoginPwdBtn.addEventListener('click', () => {
            // Check current input field state
            const isPassword = loginPwdInput.getAttribute('type') === 'password';
            
            // Toggle types between text and mask
            loginPwdInput.setAttribute('type', isPassword ? 'text' : 'password');
            
            // Switch inline emoji layout indicator
            toggleLoginPwdBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    // 2. Google OAuth Integration Handler
    if (googleGuestBtn) {
        googleGuestBtn.addEventListener('click', () => {
            console.log("Redirecting Guest user to Google Gateway Auth Pipeline...");
            // Place your identity gateway routing url here:
            // window.location.href = 'YOUR_GOOGLE_GUEST_OAUTH_URL';
        });
    }

    // 3. Form Submission Handling Pipeline
    if (guestLoginForm) {
        guestLoginForm.addEventListener('submit', (event) => {
            event.preventDefault(); // Stop standard browser reloading

            const identifier = document.getElementById('email').value.trim();
            const password = loginPwdInput.value;

            console.log(`Processing Guest authentication payload for: ${identifier}`);
            
            // Proceed to bundle inputs and route to backend auth endpoints
            // fetch('/api/guest/login', { method: 'POST', body: JSON.stringify({ identifier, password }) })
        });
    }
});