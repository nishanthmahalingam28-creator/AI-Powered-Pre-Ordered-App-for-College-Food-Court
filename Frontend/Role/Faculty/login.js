document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');

    // Smooth show/hide password mechanic
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            togglePasswordBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    // Explicit verification intercept
    if (loginForm) {
        loginForm.addEventListener('submit', (event) => {
            event.preventDefault();
            
            const emailValue = document.getElementById('email').value;
            const passwordValue = passwordInput.value;

            console.log(`Processing authenticating for faculty user identity: ${emailValue}`);
            
            // Integrate with your standard institutional backend routers here
            // Example: window.location.href = 'faculty/dashboard.html';
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