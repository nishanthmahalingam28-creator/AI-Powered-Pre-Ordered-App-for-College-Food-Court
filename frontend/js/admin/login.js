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

        if (result.user) {
            sessionStorage.setItem('foodCourtUser', JSON.stringify(result.user));
        }

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
