const API_BASE_URL = window.FOOD_COURT_API_BASE;

document.getElementById('shopOwnerLoginForm').addEventListener('submit', async function (event) {
    event.preventDefault();

    const alertBox = document.getElementById('alert-box');
    const shop = document.getElementById('vendorShop').value;
    const email = document.getElementById('vendorEmail').value.trim().toLowerCase();
    const password = document.getElementById('vendorPassword').value;
    const submitBtn = document.getElementById('submitAnchorBtn');

    alertBox.classList.remove('hidden', 'bg-red-50', 'text-red-700', 'bg-emerald-50', 'text-emerald-700');

    if (!email || !password) {
        alertBox.classList.add('bg-red-50', 'text-red-700');
        alertBox.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Please enter both vendor email and access password.';
        return;
    }

    const originalBtn = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Verifying Terminal Access...</span><i class="fa-solid fa-spinner fa-spin text-sm"></i>';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/vendor/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password, shop })
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok || !result.success) {
            alertBox.classList.add('bg-red-50', 'text-red-700');
            alertBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Access Denied: ${result.message || 'Unrecognized stall credentials.'}`;
            return;
        }

        alertBox.classList.add('bg-emerald-50', 'text-emerald-700');
        alertBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> Authentication Successful! Loading ${result.user?.shop_name || shop} Terminal...`;

        if (result.user) {
            sessionStorage.setItem('foodCourtUser', JSON.stringify(result.user));
        }

        setTimeout(() => {
            const redirectUrl = result.redirect || `dashboard.html?shop=${encodeURIComponent(result.user?.shop_name || shop)}`;
            window.location.href = redirectUrl;
        }, 800);

    } catch (e) {
        alertBox.classList.add('bg-red-50', 'text-red-700');
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Unable to connect to server. Ensure Flask API is running.';
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtn;
        }
    }
});
