const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

document.addEventListener('DOMContentLoaded', async () => {
    const profileForm = document.getElementById('profile-form');
    const profileMessage = document.getElementById('profile-message');
    const saveProfileBtn = document.getElementById('save-profile-btn');

    const passForm = document.getElementById('password-form');
    const passwordMessage = document.getElementById('password-message');
    const changePasswordBtn = document.getElementById('change-password-btn');

    const nameInput = document.getElementById('profile-name');
    const emailInput = document.getElementById('profile-email');
    const mobileInput = document.getElementById('profile-mobile');
    const typeInput = document.getElementById('profile-type');
    const identifierInput = document.getElementById('profile-identifier');
    const identifierLabel = document.getElementById('profile-identifier-label');
    const identifierContainer = document.getElementById('profile-identifier-container');

    let currentMobile = '';

    // Fetch user details from real backend API
    try {
        const res = await fetch(`${API_BASE_URL}/customer/profile`, {
            method: 'GET',
            credentials: 'include'
        });

        if (res.status === 401) {
            // Not authenticated, redirect to login
            window.location.href = '../auth/login.html';
            return;
        }

        if (res.ok) {
            const data = await res.json();
            if (data.success && data.user) {
                const u = data.user;
                if (nameInput) nameInput.value = u.full_name || '';
                if (emailInput) emailInput.value = u.email || '';
                if (mobileInput) {
                    mobileInput.value = u.mobile || '';
                    currentMobile = u.mobile || '';
                }
                if (typeInput) typeInput.value = (u.customer_type || 'Customer').toUpperCase();
                if (identifierInput) {
                    identifierInput.value = u.identifier || 'N/A';
                }
                if (identifierLabel) {
                    if (u.customer_type === 'student') identifierLabel.textContent = 'Roll Number';
                    else if (u.customer_type === 'faculty') identifierLabel.textContent = 'Faculty ID';
                    else identifierLabel.textContent = 'Identifier';
                }
                if (u.customer_type === 'guest' && identifierContainer) {
                    identifierContainer.classList.add('hidden');
                }
            }
        }
    } catch (e) {
        console.warn('Profile fetch error:', e);
    }

    // Handle Profile Form Submission via real PUT /api/customer/profile
    if (profileForm) {
        profileForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const fullName = (nameInput?.value || '').trim();
            const mobile = (mobileInput?.value || '').trim();

            if (!fullName) {
                profileMessage.textContent = 'Full name cannot be empty.';
                profileMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                profileMessage.classList.remove('hidden');
                return;
            }

            const originalBtn = saveProfileBtn ? saveProfileBtn.innerHTML : '';
            if (saveProfileBtn) {
                saveProfileBtn.disabled = true;
                saveProfileBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Saving...';
            }

            try {
                const payload = { full_name: fullName };
                // Only send mobile if it was modified
                if (mobile && mobile !== currentMobile) {
                    payload.mobile = mobile;
                }

                const res = await fetch(`${API_BASE_URL}/customer/profile`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });

                const data = await res.json();

                if (res.ok && data.success) {
                    profileMessage.textContent = '✓ Profile details saved successfully!';
                    profileMessage.className = 'rounded-lg bg-emerald-50 text-emerald-800 p-3 text-xs font-semibold block mt-3';
                    profileMessage.classList.remove('hidden');

                    if (data.user) {
                        currentMobile = data.user.mobile || currentMobile;
                        // Update sessionStorage user cache if present
                        const cached = sessionStorage.getItem('foodCourtUser');
                        if (cached) {
                            try {
                                const parsed = JSON.parse(cached);
                                parsed.full_name = data.user.full_name;
                                parsed.mobile = data.user.mobile;
                                sessionStorage.setItem('foodCourtUser', JSON.stringify(parsed));
                            } catch (ignore) {}
                        }
                    }
                } else {
                    profileMessage.textContent = data.message || 'Failed to update profile.';
                    profileMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                    profileMessage.classList.remove('hidden');
                }
            } catch (err) {
                profileMessage.textContent = 'Unable to connect to server. Please try again.';
                profileMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                profileMessage.classList.remove('hidden');
            } finally {
                if (saveProfileBtn) {
                    saveProfileBtn.disabled = false;
                    saveProfileBtn.innerHTML = originalBtn;
                }
            }
        });
    }

    // Handle Password Change via real PUT /api/customer/password
    if (passForm) {
        passForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const currentPassword = document.getElementById('current-password')?.value || '';
            const newPassword = document.getElementById('new-password')?.value || '';
            const confirmPassword = document.getElementById('confirm-password')?.value || '';

            if (passwordMessage) passwordMessage.classList.add('hidden');

            if (!currentPassword || !newPassword || !confirmPassword) {
                passwordMessage.textContent = 'All password fields are required.';
                passwordMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                passwordMessage.classList.remove('hidden');
                return;
            }

            if (newPassword !== confirmPassword) {
                passwordMessage.textContent = 'New passwords do not match.';
                passwordMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                passwordMessage.classList.remove('hidden');
                return;
            }

            if (newPassword.length < 8) {
                passwordMessage.textContent = 'New password must be at least 8 characters long.';
                passwordMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                passwordMessage.classList.remove('hidden');
                return;
            }

            const originalBtn = changePasswordBtn ? changePasswordBtn.innerHTML : '';
            if (changePasswordBtn) {
                changePasswordBtn.disabled = true;
                changePasswordBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Updating...';
            }

            try {
                const res = await fetch(`${API_BASE_URL}/customer/password`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword,
                        confirm_password: confirmPassword
                    })
                });

                const data = await res.json();

                if (res.ok && data.success) {
                    passwordMessage.textContent = '✓ Password updated successfully!';
                    passwordMessage.className = 'rounded-lg bg-emerald-50 text-emerald-800 p-3 text-xs font-semibold block mt-3';
                    passwordMessage.classList.remove('hidden');
                    passForm.reset();
                } else {
                    passwordMessage.textContent = data.message || 'Failed to update password.';
                    passwordMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                    passwordMessage.classList.remove('hidden');
                }
            } catch (err) {
                passwordMessage.textContent = 'Unable to connect to password service.';
                passwordMessage.className = 'rounded-lg bg-red-50 text-red-700 p-3 text-xs font-semibold block mt-3';
                passwordMessage.classList.remove('hidden');
            } finally {
                if (changePasswordBtn) {
                    changePasswordBtn.disabled = false;
                    changePasswordBtn.innerHTML = originalBtn;
                }
            }
        });
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to sign out?')) return;
            try {
                await fetch(`${API_BASE_URL}/auth/logout`, {
                    method: 'POST',
                    credentials: 'include'
                });
            } catch (e) {}
            sessionStorage.removeItem('foodCourtUser');
            window.location.href = '../auth/login.html';
        });
    }
});

