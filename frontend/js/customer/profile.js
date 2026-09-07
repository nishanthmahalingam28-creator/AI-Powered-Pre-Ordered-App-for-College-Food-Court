const profileForm = document.getElementById('profile-form');
const profileMessage = document.getElementById('profile-message');

profileForm.addEventListener('submit', (event) => {
    event.preventDefault();
    profileMessage.textContent = 'Profile changes are ready to be saved when backend account integration is connected.';
    profileMessage.classList.remove('hidden');
});

document.getElementById('password-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const passwordMessage = document.getElementById('password-message');
    passwordMessage.textContent = 'Password changes are not stored in this frontend demo.';
    passwordMessage.classList.remove('hidden');
});
