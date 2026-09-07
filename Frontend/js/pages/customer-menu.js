const customerCartKey = 'kpriet-food-court-cart';

function readCustomerCart() {
    try {
        const storedCart = window.localStorage.getItem(customerCartKey);
        return storedCart ? JSON.parse(storedCart) : [];
    } catch (error) {
        console.error('Unable to read the demo cart.', error);
        return [];
    }
}

function saveCustomerCart(cart) {
    window.localStorage.setItem(customerCartKey, JSON.stringify(cart));
}

function updateCartSummary(cart) {
    const count = cart.reduce((total, item) => total + item.quantity, 0);
    const cartCount = document.getElementById('cart-count');
    if (cartCount) {
        cartCount.textContent = String(count);
    }
}

function addToCustomerCart(item) {
    const cart = readCustomerCart();
    const existingItem = cart.find((cartItem) => cartItem.id === item.id);

    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({ ...item, quantity: 1 });
    }

    saveCustomerCart(cart);
    updateCartSummary(cart);
}

document.querySelectorAll('[data-add-item]').forEach((button) => {
    button.addEventListener('click', () => {
        addToCustomerCart(JSON.parse(button.dataset.addItem));
        button.textContent = 'Added';
        window.setTimeout(() => {
            button.textContent = 'Add';
        }, 900);
    });
});

updateCartSummary(readCustomerCart());
