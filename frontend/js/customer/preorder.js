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

let activePendingOrder = null;

function updatePaymentUI(order) {
    const statusEl = document.getElementById('order-payment-status');
    const methodEl = document.getElementById('order-payment-method');
    const pendingAction = document.getElementById('pending-pay-action');

    if (methodEl) {
        methodEl.textContent = `· ${order.payment_method}`;
    }

    if (statusEl) {
        if (order.payment_status === 'paid') {
            statusEl.className = 'px-2.5 py-0.5 rounded-full text-xs font-black uppercase bg-emerald-100 text-emerald-800';
            statusEl.textContent = 'PAID';
            if (pendingAction) pendingAction.classList.add('hidden');
        } else if (order.payment_status === 'pending') {
            statusEl.className = 'px-2.5 py-0.5 rounded-full text-xs font-black uppercase bg-amber-100 text-amber-800';
            statusEl.textContent = order.payment_method === 'Pay at Counter' ? 'PAY AT COUNTER' : 'PAYMENT PENDING';
            if (pendingAction && order.payment_method === 'UPI / Online') {
                pendingAction.classList.remove('hidden');
            } else if (pendingAction) {
                pendingAction.classList.add('hidden');
            }
        } else {
            statusEl.className = 'px-2.5 py-0.5 rounded-full text-xs font-black uppercase bg-red-100 text-red-800';
            statusEl.textContent = order.payment_status.toUpperCase();
            if (pendingAction) pendingAction.classList.add('hidden');
        }
    }
}

function showProcessingModal(order, paymentId) {
    const modal = document.getElementById('payment-processing-modal');
    const titleEl = document.getElementById('payment-processing-title');
    const descEl = document.getElementById('payment-processing-desc');
    const refEl = document.getElementById('proc-order-ref');
    const payIdEl = document.getElementById('proc-payment-id');
    const actionEl = document.getElementById('payment-processing-action');
    const iconEl = document.getElementById('payment-spinner-icon');

    if (refEl) refEl.textContent = `#${order.order_reference}`;
    if (payIdEl) payIdEl.textContent = paymentId || 'Processing...';
    if (titleEl) titleEl.textContent = 'Verifying Payment...';
    if (descEl) descEl.textContent = 'Authorizing cryptographic signature with server gateway. Please do not close or refresh.';
    if (actionEl) actionEl.classList.add('hidden');
    if (iconEl) {
        iconEl.className = 'w-16 h-16 bg-teal-50 text-teal-700 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4';
        iconEl.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
    }
    if (modal) modal.classList.remove('hidden');
}

function hideProcessingModal() {
    const modal = document.getElementById('payment-processing-modal');
    if (modal) modal.classList.add('hidden');
}

document.getElementById('payment-close-modal-btn')?.addEventListener('click', () => {
    hideProcessingModal();
});

async function verifyPaymentWithBackend(order, razorpayResponse) {
    try {
        const res = await fetch(`${API_BASE_URL}/orders/${order.order_id}/verify-payment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                razorpay_order_id: razorpayResponse.razorpay_order_id,
                razorpay_payment_id: razorpayResponse.razorpay_payment_id,
                razorpay_signature: razorpayResponse.razorpay_signature
            })
        });

        const data = await res.json();
        const titleEl = document.getElementById('payment-processing-title');
        const descEl = document.getElementById('payment-processing-desc');
        const iconEl = document.getElementById('payment-spinner-icon');
        const actionEl = document.getElementById('payment-processing-action');

        if (res.ok && data.success) {
            order.payment_status = 'paid';
            updatePaymentUI(order);

            if (titleEl) titleEl.textContent = 'Payment Confirmed!';
            if (descEl) descEl.textContent = 'Server signature verified successfully. Your order is confirmed and sent to kitchen.';
            if (iconEl) {
                iconEl.className = 'w-16 h-16 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4';
                iconEl.innerHTML = '<i class="fa-solid fa-check"></i>';
            }
            setTimeout(() => {
                hideProcessingModal();
            }, 2000);
        } else {
            if (titleEl) titleEl.textContent = 'Verification Failed';
            if (descEl) descEl.textContent = data.message || 'Payment signature verification failed. Please contact support.';
            if (iconEl) {
                iconEl.className = 'w-16 h-16 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4';
                iconEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
            }
            if (actionEl) actionEl.classList.remove('hidden');
        }
    } catch (e) {
        console.error('Error verifying payment with server:', e);
        const titleEl = document.getElementById('payment-processing-title');
        const descEl = document.getElementById('payment-processing-desc');
        const actionEl = document.getElementById('payment-processing-action');
        if (titleEl) titleEl.textContent = 'Verification Error';
        if (descEl) descEl.textContent = 'Network error while contacting payment verification service.';
        if (actionEl) actionEl.classList.remove('hidden');
    }
}

function initiateRazorpayPayment(order) {
    activePendingOrder = order;

    if (typeof Razorpay === 'undefined') {
        alert('Payment gateway library is loading. Please check your internet connection or try again in a moment.');
        return;
    }

    const gatewayOrderId = order.payment?.razorpay_order_id || order.razorpay_order_id || order.payment?.gateway_order_id;
    const keyId = order.payment?.key_id || order.key_id || window.RAZORPAY_KEY_ID || '';
    const amountPaise = order.payment?.amount_paise || order.amount_paise || Math.round(order.total_amount * 100);

    const options = {
        key: keyId,
        amount: amountPaise,
        currency: order.currency || 'INR',
        name: 'KPR Food Court',
        description: `Order #${order.order_reference} - ${order.shop_name || 'Express Order'}`,
        order_id: gatewayOrderId,
        handler: function (response) {
            showProcessingModal(order, response.razorpay_payment_id);
            verifyPaymentWithBackend(order, response);
        },
        prefill: {
            name: 'College Customer',
            email: 'student@kpriet.ac.in',
            contact: '9876543210'
        },
        theme: {
            color: '#0f766e'
        },
        modal: {
            ondismiss: function () {
                console.log('Customer dismissed Razorpay Checkout.');
                updatePaymentUI(order);
            }
        }
    };

    const rzp = new Razorpay(options);
    rzp.on('payment.failed', function (response) {
        console.error('Razorpay payment failed:', response.error);
        alert(`Payment failed: ${response.error.description || 'Transaction unsuccessful'}`);
        updatePaymentUI(order);
    });
    rzp.open();
}

document.getElementById('complete-pending-pay-btn')?.addEventListener('click', () => {
    if (activePendingOrder) {
        initiateRazorpayPayment(activePendingOrder);
    }
});

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
            activePendingOrder = order;

            document.getElementById('order-reference').textContent = order.order_reference;
            document.getElementById('pickup-otp').textContent = order.pickup_otp;
            const shopEl = document.getElementById('order-shop');
            if (shopEl) shopEl.textContent = order.shop_name;

            updatePaymentUI(order);

            const confirmationSec = document.getElementById('confirmation');
            confirmationSec.classList.remove('hidden');
            confirmationSec.scrollIntoView({ behavior: 'smooth' });

            // Clear Cart in localStorage after successful order placement
            savePreorderCart([]);
            renderPreorder();

            // If UPI / Online was selected, launch the Razorpay Checkout modal
            if (selectedPayment === 'UPI / Online' && order.payment_status === 'pending') {
                initiateRazorpayPayment(order);
            }
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
