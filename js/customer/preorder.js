const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';
const customerCartKey = 'kpriet-food-court-cart';

function readPreorderCart() {
    try {
        const storedCart = window.localStorage.getItem(customerCartKey);
        return storedCart ? JSON.parse(storedCart) : [];
    } catch (error) {
        return [];
    }
}

function savePreorderCart(cart) {
    window.localStorage.setItem(customerCartKey, JSON.stringify(cart));
}

function formatCurrency(value) {
    return `₹${parseFloat(value).toFixed(2)}`;
}

function renderPreorder() {
    const cart = readPreorderCart();
    const cartContainer = document.getElementById('cart-items');
    const emptyState = document.getElementById('empty-cart');
    const subtotalElement = document.getElementById('cart-subtotal');
    const totalElement = document.getElementById('cart-total');
    const confirmButton = document.getElementById('confirm-order');
    const subtotal = cart.reduce((total, item) => total + (item.price * (item.quantity || 1)), 0);

    cartContainer.innerHTML = '';
    emptyState.classList.toggle('hidden', cart.length > 0);
    confirmButton.disabled = cart.length === 0;
    confirmButton.classList.toggle('opacity-50', cart.length === 0);
    confirmButton.classList.toggle('cursor-not-allowed', cart.length === 0);

    cart.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'flex flex-wrap items-center justify-between gap-3 pt-3 first:pt-0';
        row.innerHTML = `
            <div>
                <h4 class="font-bold text-slate-800 text-sm">${item.name}</h4>
                <p class="text-xs text-slate-500">${item.shop || 'Food Court'} · ${formatCurrency(item.price)} each</p>
            </div>
            <div class="flex items-center gap-2">
                <button type="button" class="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors flex items-center justify-center" data-decrease="${item.id}">−</button>
                <span class="min-w-6 text-center font-bold text-xs">${item.quantity || 1}</span>
                <button type="button" class="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors flex items-center justify-center" data-increase="${item.id}">+</button>
                <button type="button" class="text-xs text-red-600 hover:text-red-800 ml-2 font-semibold" data-remove="${item.id}">Remove</button>
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
    const item = cart.find((cartItem) => String(cartItem.id) === String(itemId));
    if (item) {
        item.quantity = (item.quantity || 1) + difference;
    }
    savePreorderCart(cart.filter((cartItem) => cartItem.quantity > 0));
    renderPreorder();
}

function removeItem(itemId) {
    savePreorderCart(readPreorderCart().filter((item) => String(item.id) !== String(itemId)));
    renderPreorder();
}

document.getElementById('confirm-order').addEventListener('click', async () => {
    const cart = readPreorderCart();
    if (!cart.length) return;

    const confirmBtn = document.getElementById('confirm-order');
    const originalText = confirmBtn.innerHTML;
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Placing Order...';

    const selectedPayment = document.querySelector('input[name="paymentMethod"]:checked')?.value || 'Campus Wallet';

    try {
        const response = await fetch(`${API_BASE_URL}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                items: cart.map(item => ({ id: item.id, quantity: item.quantity || 1 })),
                payment_method: selectedPayment
            })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            const order = result.order;
            document.getElementById('order-reference').textContent = order.order_reference;
            document.getElementById('pickup-otp').textContent = order.pickup_otp;
            const shopEl = document.getElementById('order-shop');
            if (shopEl) shopEl.textContent = order.shop_name;

            const confirmationSec = document.getElementById('confirmation');
            confirmationSec.classList.remove('hidden');
            confirmationSec.scrollIntoView({ behavior: 'smooth' });

            // Clear Cart in localStorage after successful order placement
            savePreorderCart([]);
            renderPreorder();
        } else {
            alert(result.message || 'Failed to place order.');
        }
    } catch (e) {
        alert('Could not connect to server to place your order.');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = originalText;
    }
});

renderPreorder();
