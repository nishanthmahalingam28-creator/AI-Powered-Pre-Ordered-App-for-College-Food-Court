document.addEventListener('DOMContentLoaded', () => {
    const signUpForm = document.getElementById('signUpForm');
    const googleBtn = document.getElementById('googleSignUpBtn');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('togglePassword');
    //Roll number
    document.addEventListener('DOMContentLoaded', () => {
    const rollNumberInput = document.getElementById('rollNumber');

    if (rollNumberInput) {
        // Automatically convert letters to uppercase as the user types
        rollNumberInput.addEventListener('input', (e) => {
            const start = e.target.selectionStart;
            const end = e.target.selectionEnd;
            e.target.value = e.target.value.toUpperCase();
            e.target.setSelectionRange(start, end);
        });

        // Optional validation helper when focus leaves the input field
        rollNumberInput.addEventListener('blur', (e) => {
            const value = e.target.value.trim();
            // Adjust this regex pattern to match your exact institutional roll format if needed
            const rollPattern = /^[0-9]{2}[A-Z]{2}[0-9]{2,3}$/;
            
            if (value && !rollPattern.test(value)) {
                console.warn('Note: The entered roll number format does not match the standard pattern.');
            }
        });
    }
});

    // Toggle password character visibility
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            togglePasswordBtn.textContent = isPassword ? '🙈' : '👁️';
        });
    }

    // Google Single Sign-On initialization handler
    if (googleBtn) {
        googleBtn.addEventListener('click', () => {
            console.log("Initializing Google OAuth pipeline...");
            // Link your authentication path routing here
        });
    }

    // Standard Email Registration Submission pipeline
    if (signUpForm) {
        signUpForm.addEventListener('submit', (event) => {
            event.preventDefault();
            
            const name = document.getElementById('fullName').value;
            const email = document.getElementById('email').value;
            
            console.log(`Sign-up intercept: account payload created for ${name} (${email})`);
            // Forward validated fields out to database registers here
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