const customerCartKey = 'kpriet-food-court-cart';

function readPreorderCart() {
    try {
        const storedCart = window.localStorage.getItem(customerCartKey);
        return storedCart ? JSON.parse(storedCart) : [];
    } catch (error) {
        console.error('Unable to read the demo cart.', error);
        return [];
    }
}

function savePreorderCart(cart) {
    window.localStorage.setItem(customerCartKey, JSON.stringify(cart));
}

function formatCurrency(value) {
    return `₹${value.toFixed(2)}`;
}

function renderPreorder() {
    const cart = readPreorderCart();
    const cartContainer = document.getElementById('cart-items');
    const emptyState = document.getElementById('empty-cart');
    const subtotalElement = document.getElementById('cart-subtotal');
    const totalElement = document.getElementById('cart-total');
    const confirmButton = document.getElementById('confirm-order');
    const subtotal = cart.reduce((total, item) => total + item.price * item.quantity, 0);

    cartContainer.innerHTML = '';
    emptyState.classList.toggle('hidden', cart.length > 0);
    confirmButton.disabled = cart.length === 0;
    confirmButton.classList.toggle('opacity-50', cart.length === 0);

    cart.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 py-4';
        row.innerHTML = `
            <div>
                <h3 class="font-bold text-slate-800">${item.name}</h3>
                <p class="text-xs text-slate-500">${item.shop} · ${formatCurrency(item.price)} each</p>
            </div>
            <div class="flex items-center gap-2">
                <button type="button" class="customer-button customer-button-secondary px-3 py-1.5" data-decrease="${item.id}" aria-label="Decrease ${item.name} quantity">−</button>
                <span class="min-w-6 text-center font-bold">${item.quantity}</span>
                <button type="button" class="customer-button customer-button-secondary px-3 py-1.5" data-increase="${item.id}" aria-label="Increase ${item.name} quantity">+</button>
                <button type="button" class="customer-button customer-button-danger px-3 py-1.5" data-remove="${item.id}">Remove</button>
            </div>`;
        cartContainer.appendChild(row);
    });

    subtotalElement.textContent = formatCurrency(subtotal);
    totalElement.textContent = formatCurrency(subtotal);
    document.querySelectorAll('[data-increase]').forEach((button) => {
        button.addEventListener('click', () => changeQuantity(button.dataset.increase, 1));
    });
    document.querySelectorAll('[data-decrease]').forEach((button) => {
        button.addEventListener('click', () => changeQuantity(button.dataset.decrease, -1));
    });
    document.querySelectorAll('[data-remove]').forEach((button) => {
        button.addEventListener('click', () => removeItem(button.dataset.remove));
    });
}

function changeQuantity(itemId, difference) {
    const cart = readPreorderCart();
    const item = cart.find((cartItem) => cartItem.id === itemId);
    if (item) {
        item.quantity += difference;
    }
    savePreorderCart(cart.filter((cartItem) => cartItem.quantity > 0));
    renderPreorder();
}

function removeItem(itemId) {
    savePreorderCart(readPreorderCart().filter((item) => item.id !== itemId));
    renderPreorder();
}

document.getElementById('confirm-order').addEventListener('click', () => {
    const cart = readPreorderCart();
    if (!cart.length) {
        return;
    }
    const reference = `KPR-${Date.now().toString().slice(-6)}`;
    const otp = String(Math.floor(100000 + Math.random() * 900000));
    document.getElementById('order-reference').textContent = reference;
    document.getElementById('pickup-otp').textContent = otp;
    document.getElementById('confirmation').classList.remove('hidden');
});

renderPreorder();
