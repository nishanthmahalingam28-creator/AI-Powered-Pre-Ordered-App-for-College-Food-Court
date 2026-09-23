const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

document.getElementById('adminLoginForm').addEventListener('submit', async function (event) {
    event.preventDefault();

    const alertBox = document.getElementById('admin-alert-box');
    const user = document.getElementById('adminUser').value.trim();
    const pass = document.getElementById('adminPassword').value;
    const submitBtn = this.querySelector('button[type="submit"]');

    alertBox.classList.remove('hidden', 'bg-red-50', 'text-red-700', 'bg-emerald-50', 'text-emerald-700');

    if (!user || !pass) {
        alertBox.classList.add('bg-red-50', 'text-red-700');
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Please enter both Security ID and Passphrase.';
        return;
    }

    const originalBtn = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Verifying...</span><i class="fa-solid fa-spinner fa-spin text-sm"></i>';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/admin/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username: user, password: pass })
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok || !result.success) {
            alertBox.classList.add('bg-red-50', 'text-red-700');
            alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${result.message || 'Access Denied: Invalid root identifiers.'}`;
            return;
        }

        alertBox.classList.add('bg-emerald-50', 'text-emerald-700');
        alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Root Authorization Granted! Loading Admin Control Hub...';

        if (result.auth_token) {
            localStorage.setItem('foodCourtAuthToken', result.auth_token);
        }
        if (result.user) {
            sessionStorage.setItem('foodCourtUser', JSON.stringify(result.user));
        }

        const authToken = localStorage.getItem('foodCourtAuthToken');
        const meResponse = await fetch(API_BASE_URL + '/auth/me', {
            method: 'GET',
            headers: authToken ? { Authorization: 'Bearer ' + authToken } : {},
            credentials: 'include',
            cache: 'no-store'
        });
        const meData = await meResponse.json().catch(() => ({}));

        if (!meResponse.ok || !meData.authenticated || !meData.user || meData.user.role !== 'admin') {
            sessionStorage.removeItem('foodCourtUser');
            localStorage.removeItem('foodCourtAuthToken');
            alertBox.classList.remove('bg-emerald-50', 'text-emerald-700');
            alertBox.classList.add('bg-red-50', 'text-red-700');
            alertBox.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Login verification failed. Please try again.';
            return;
        }

        sessionStorage.setItem('foodCourtUser', JSON.stringify(meData.user));

        setTimeout(() => {
            window.location.href = result.redirect || 'dashboard.html';
        }, 800);

    } catch (e) {
        alertBox.classList.add('bg-red-50', 'text-red-700');
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Unable to connect to authentication server. Verify Flask API is active.';
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtn;
        }
    }
});
