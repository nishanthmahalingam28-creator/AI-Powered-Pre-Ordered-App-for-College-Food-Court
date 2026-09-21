const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

let serverCart = [];
let serverCartSummary = null;

function formatCurrency(value) {
    return `₹${parseFloat(value || 0).toFixed(2)}`;
}

async function fetchCartAndRender() {
    const cartContainer = document.getElementById('cart-items');
    const emptyState = document.getElementById('empty-cart');
    const subtotalElement = document.getElementById('cart-subtotal');
    const totalElement = document.getElementById('cart-total');
    const confirmButton = document.getElementById('confirm-order');

    try {
        const response = await fetch(`${API_BASE_URL}/cart`, { credentials: 'include' });
        if (response.status === 401) {
            window.location.href = '../auth/login.html';
            return;
        }

        const data = await response.json();
        if (data.success) {
            serverCart = data.cart || [];
            serverCartSummary = data.summary || {};
            renderCartUI();
        }
    } catch (e) {
        console.error('Error fetching cart:', e);
        if (cartContainer) {
            cartContainer.innerHTML = '<p class="text-xs text-red-500 py-3">Unable to connect to server to load cart.</p>';
        }
    }
}

function renderCartUI() {
    const cartContainer = document.getElementById('cart-items');
    const emptyState = document.getElementById('empty-cart');
    const subtotalElement = document.getElementById('cart-subtotal');
    const totalElement = document.getElementById('cart-total');
    const confirmButton = document.getElementById('confirm-order');
    const subtotal = serverCartSummary ? serverCartSummary.total_amount : serverCart.reduce((total, item) => total + (item.price * (item.quantity || 1)), 0);

    cartContainer.innerHTML = '';
    emptyState.classList.toggle('hidden', serverCart.length > 0);
    
    const isValid = serverCartSummary ? serverCartSummary.is_valid : true;
    confirmButton.disabled = serverCart.length === 0 || !isValid;
    confirmButton.classList.toggle('opacity-50', serverCart.length === 0 || !isValid);
    confirmButton.classList.toggle('cursor-not-allowed', serverCart.length === 0 || !isValid);

    // Display validation alerts if any items are invalid/out of stock
    if (serverCartSummary && serverCartSummary.validation_errors && serverCartSummary.validation_errors.length > 0) {
        const errorAlert = document.createElement('div');
        errorAlert.className = 'mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex flex-col gap-1';
        errorAlert.innerHTML = `
            <div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation"></i> Action Required:</div>
            ${serverCartSummary.validation_errors.map(err => `<div>• ${err}</div>`).join('')}
        `;
        cartContainer.appendChild(errorAlert);
    }

    serverCart.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'flex flex-wrap items-center justify-between gap-3 pt-3 first:pt-0';
        row.innerHTML = `
            <div>
                <h4 class="font-bold text-slate-800 text-sm">${item.name}</h4>
                <p class="text-xs text-slate-500">${item.shop_name || 'Food Court'} · ${formatCurrency(item.price)} each</p>
                ${!item.is_available ? '<span class="text-[10px] text-red-600 font-bold">Currently Unavailable</span>' : ''}
                ${item.stock_quantity < item.quantity ? `<span class="text-[10px] text-amber-600 font-bold">Only ${item.stock_quantity} left</span>` : ''}
            </div>
            <div class="flex items-center gap-2">
                <button type="button" class="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors flex items-center justify-center cursor-pointer" data-decrease="${item.item_id || item.id}">−</button>
                <span class="min-w-6 text-center font-bold text-xs">${item.quantity || 1}</span>
                <button type="button" class="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors flex items-center justify-center cursor-pointer" data-increase="${item.item_id || item.id}">+</button>
                <button type="button" class="text-xs text-red-600 hover:text-red-800 ml-2 font-semibold cursor-pointer" data-remove="${item.item_id || item.id}">Remove</button>
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

async function changeQuantity(itemId, difference) {
    const item = serverCart.find((c) => String(c.item_id || c.id) === String(itemId));
    if (!item) return;

    const newQty = (item.quantity || 1) + difference;

    try {
        let res;
        if (newQty <= 0) {
            res = await fetch(`${API_BASE_URL}/cart/${itemId}`, {
                method: 'DELETE',
                credentials: 'include'
            });
        } else {
            res = await fetch(`${API_BASE_URL}/cart/${itemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ quantity: newQty })
            });
        }

        const data = await res.json();
        if (data.success) {
            serverCart = data.cart || [];
            serverCartSummary = data.summary || {};
            renderCartUI();
        } else {
            alert(data.message || 'Unable to update quantity.');
        }
    } catch (e) {
        console.error('Update quantity error:', e);
        alert('Server communication error.');
    }
}

async function removeItem(itemId) {
    try {
        const res = await fetch(`${API_BASE_URL}/cart/${itemId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await res.json();
        if (data.success) {
            serverCart = data.cart || [];
            serverCartSummary = data.summary || {};
            renderCartUI();
        } else {
            alert(data.message || 'Failed to remove item.');
        }
    } catch (e) {
        console.error('Remove item error:', e);
        alert('Server communication error.');
    }
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

async function loadGeneratedBill(orderId) {
    const itemsEl = document.getElementById('generated-bill-items');
    const totalEl = document.getElementById('bill-total');
    if (!itemsEl) return;
    try {
        const res = await fetch(`${API_BASE_URL}/orders/${orderId}/bill`, { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || 'Unable to generate bill.');
        const bill = data.bill || data.order || data;
        const items = bill.items || [];
        itemsEl.innerHTML = items.length ? items.map(item => `
            <div class="px-4 py-3 flex items-center justify-between gap-4">
                <div class="min-w-0">
                    <p class="text-xs font-black text-slate-800 truncate">${escapeHtml(item.name || item.item_name || 'Food item')}</p>
                    <p class="text-[11px] text-slate-400">${Number(item.quantity || 1)} × ${formatCurrency(item.unit_price || item.price || 0)}</p>
                </div>
                <strong class="text-xs font-black text-slate-800">${formatCurrency(item.subtotal || 0)}</strong>
            </div>`).join('') : '<p class="p-4 text-xs text-slate-400">No bill items found.</p>';
        const total = Number(bill.total_amount || order.total_amount || 0);
        if (totalEl) totalEl.textContent = formatCurrency(total);
    } catch (e) {
        console.error('Bill generation error:', e);
        itemsEl.innerHTML = '<p class="p-4 text-xs text-rose-600">Unable to load the bill. You can view it again from My Orders.</p>';
        if (totalEl) totalEl.textContent = formatCurrency(order.total_amount || 0);
    }
}

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
    let cachedUser = {};
    try {
        cachedUser = JSON.parse(sessionStorage.getItem('foodCourtUser') || '{}');
    } catch (e) {}

    const customerName = cachedUser.full_name || order.customer_name || 'College Student';
    const customerEmail = cachedUser.email || order.customer_email || 'student@campus.edu';
    const customerContact = cachedUser.mobile_number || order.customer_mobile || '';

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
            name: customerName,
            email: customerEmail,
            contact: customerContact
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
    if (!serverCart || !serverCart.length) return;

    const confirmBtn = document.getElementById('confirm-order');
    const originalText = confirmBtn.innerHTML;
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Placing Order...';

    const selectedPayment = document.querySelector('input[name="paymentMethod"]:checked')?.value || 'Pay at Counter';

    try {
        const response = await fetch(`${API_BASE_URL}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                items: serverCart.map(item => ({ id: item.item_id || item.id, quantity: item.quantity || 1 })),
                payment_method: selectedPayment
            })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            const order = result.order;
            activePendingOrder = order;

            document.getElementById('order-reference').textContent = order.order_reference;
            const createdAtEl = document.getElementById('order-created-at');
            if (createdAtEl) {
                const raw = String(order.created_at || '').trim();
                let normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
                if (raw && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) normalized += 'Z';
                const createdAt = raw ? new Date(normalized) : null;
                createdAtEl.textContent = createdAt && !Number.isNaN(createdAt.getTime())
                    ? new Intl.DateTimeFormat('en-IN', {
                        timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
                        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
                    }).format(createdAt)
                    : (order.created_at || '—');
            }
            document.getElementById('bill-total').textContent = formatCurrency(order.total_amount || 0);
            document.getElementById('pickup-otp').textContent = order.pickup_otp;
            const shopEl = document.getElementById('order-shop');
            if (shopEl) shopEl.textContent = order.shop_name;

            updatePaymentUI(order);

            const confirmationSec = document.getElementById('confirmation');
            confirmationSec.classList.remove('hidden');
            confirmationSec.scrollIntoView({ behavior: 'smooth' });

            await loadGeneratedBill(order.order_id);

            // Refresh cart from server (which was automatically cleared upon order placement)
            await fetchCartAndRender();

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

fetchCartAndRender();
