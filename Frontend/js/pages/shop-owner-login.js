document.getElementById('vendorLoginForm').addEventListener('submit', function (event) {
    event.preventDefault();

    const alertBox = document.getElementById('alert-box');
    const shop = document.getElementById('vendorShop').value;
    const email = document.getElementById('vendorEmail').value.trim().toLowerCase();
    const password = document.getElementById('vendorPassword').value;

    const adminVendorDatabase = {
        "ypr": { shopName: "YPR", email: "ypr@kpriet.ac.in", pass: "ypr123" },
        "campus kitchen": { shopName: "Campus Kitchen", email: "campus@kpriet.ac.in", pass: "cam123" },
        "german cafe": { shopName: "German Cafe", email: "german@kpriet.ac.in", pass: "german123" },
        "royal kitchen": { shopName: "Royal Kitchen", email: "royal@kpriet.ac.in", pass: "royal123" },
        "mario": { shopName: "Mario", email: "mario@kpriet.ac.in", pass: "mario123" },
        "saaral": { shopName: "Saaral", email: "saaral@kpriet.ac.in", pass: "saaral123" }
    };

    const targetKey = shop.toLowerCase();
    const record = adminVendorDatabase[targetKey];

    alertBox.classList.remove('hidden', 'bg-red-50', 'text-red-700', 'bg-emerald-50', 'text-emerald-700');

    if (record && record.email === email && record.pass === password) {
        alertBox.classList.add('bg-emerald-50', 'text-emerald-700');
        alertBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> Authentication Successful! Loading ${record.shopName} Terminal...`;

        const fileFriendlyName = record.shopName.toLowerCase().replace(/\s+/g, '-');

        setTimeout(() => {
            window.location.href = `${fileFriendlyName}-dashboard.html`;
        }, 1500);
    } else {
        alertBox.classList.add('bg-red-50', 'text-red-700');
        alertBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Access Denied: Unrecognized credentials for stall "${shop}" in Admin database record registry.`;
    }
});
