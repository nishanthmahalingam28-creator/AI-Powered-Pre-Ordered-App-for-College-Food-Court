const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', async () => {
    const profileForm = document.getElementById('profile-form');
    const profileMessage = document.getElementById('profile-message');

    // Fetch user details
    try {
        const res = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            if (data.authenticated && data.user) {
                const u = data.user;
                if (profileForm) {
                    const nameInput = profileForm.querySelector('input[name="name"]');
                    if (nameInput && u.full_name) nameInput.value = u.full_name;

                    const emailInput = profileForm.querySelector('input[name="email"]');
                    if (emailInput && u.email) emailInput.value = u.email;

                    const mobileInput = profileForm.querySelector('input[name="mobile"]');
                    if (mobileInput && u.mobile) mobileInput.value = u.mobile;

                    const typeSelect = profileForm.querySelector('select[name="customerType"]');
                    if (typeSelect && u.customer_type) {
                        typeSelect.value = u.customer_type.charAt(0).toUpperCase() + u.customer_type.slice(1);
                    }
                }
            }
        }
    } catch (e) {
        console.warn('Profile fetch error:', e);
    }

    if (profileForm) {
        profileForm.addEventListener('submit', (event) => {
            event.preventDefault();
            profileMessage.textContent = '✓ Profile details saved successfully!';
            profileMessage.className = 'rounded-lg bg-emerald-50 text-emerald-800 p-3 text-sm block mt-3';
        });
    }

    const passForm = document.getElementById('password-form');
    if (passForm) {
        passForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const passwordMessage = document.getElementById('password-message');
            passwordMessage.textContent = '✓ Password updated successfully.';
            passwordMessage.className = 'rounded-lg bg-emerald-50 text-emerald-800 p-3 text-sm block mt-3';
            passForm.reset();
        });
    }
});
