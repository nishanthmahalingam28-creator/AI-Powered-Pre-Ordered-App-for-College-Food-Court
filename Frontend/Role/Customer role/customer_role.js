document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.card');

    cards.forEach(card => {
        // Triggers navigation matching the active card selection click block
        card.addEventListener('click', () => {
            const chosenRole = card.getAttribute('data-role');
            navigateToDashboard(chosenRole);
        });
    });

    function navigateToDashboard(role) {
        console.log(`Navigating user to: ${role}`);
        
        switch (role) {
            case 'student':
                window.location.href = 'student/dashboard.html';
                break;
            case 'faculty':
                window.location.href = 'faculty/dashboard.html';
                break;
            case 'guest':
                window.location.href = 'guest/menu.html';
                break;
            default:
                console.warn('Dashboard target route undefined.');
        }
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
