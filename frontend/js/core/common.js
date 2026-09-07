function initMobileMenu() {
    const menuBtn = document.getElementById('menuBtn');
    const dropdownMenu = document.getElementById('dropdownMenu');

    if (!menuBtn || !dropdownMenu) {
        return;
    }

    menuBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        dropdownMenu.classList.toggle('hidden');
    });

    document.addEventListener('click', () => {
        dropdownMenu.classList.add('hidden');
    });
}

initMobileMenu();
