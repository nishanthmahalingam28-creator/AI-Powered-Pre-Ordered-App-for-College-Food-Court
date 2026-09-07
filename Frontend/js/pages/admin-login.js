document.getElementById('adminLoginForm').addEventListener('submit', function (event) {
    event.preventDefault();

    const alertBox = document.getElementById('admin-alert-box');
    const user = document.getElementById('adminUser').value.trim();
    const pass = document.getElementById('adminPassword').value;

    alertBox.classList.remove('hidden', 'bg-red-50', 'text-red-700', 'bg-emerald-50', 'text-emerald-700');

    if (user === "admin" && pass === "admin123") {
        alertBox.classList.add('bg-emerald-50', 'text-emerald-700');
        alertBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> Authorization Granted! Redirecting...`;

        setTimeout(() => {
            window.location.href = "admin-dashboard.html";
        }, 1500);
    } else {
        alertBox.classList.add('bg-red-50', 'text-red-700');
        alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Denied: Invalid root access identifiers.`;
    }
});
