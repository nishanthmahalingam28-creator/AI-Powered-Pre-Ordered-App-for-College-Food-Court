const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

function formatCurrency(value) {
    return `₹${parseFloat(value || 0).toFixed(2)}`;
}

function closeBillModal() {
    const modal = document.getElementById('bill-modal');
    if (modal) modal.classList.add('hidden');
}

async function viewOrderBill(orderId) {
    try {
        const res = await fetch(`${API_BASE_URL}/orders/${orderId}/bill`, { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.success) {
            alert(data.message || 'Unable to fetch bill for this order.');
            return;
        }

        const bill = data.bill;
        document.getElementById('bill-shop-name').textContent = bill.shop_name;
        document.getElementById('bill-order-ref').textContent = `Ref: #${bill.order_reference}`;
        document.getElementById('bill-subtotal').textContent = formatCurrency(bill.subtotal);
        document.getElementById('bill-total').textContent = formatCurrency(bill.total_amount);
        document.getElementById('bill-payment-method').textContent = bill.payment_method;

        // Order & Payment Status Badges
        const ordStatusEl = document.getElementById('bill-order-status');
        ordStatusEl.textContent = bill.order_status.toUpperCase();

        const payStatusEl = document.getElementById('bill-payment-status');
        payStatusEl.textContent = bill.payment_status.toUpperCase();
        payStatusEl.className = `inline-block mt-1 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
            bill.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-800' :
            bill.payment_status === 'pending' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
        }`;

        // Populate Items Table
        const tbody = document.getElementById('bill-items-body');
        tbody.innerHTML = '';
        bill.items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="py-2.5 px-3 font-semibold text-slate-800">${item.item_name}</td>
                <td class="py-2.5 px-2 text-center text-slate-600">${item.quantity}</td>
                <td class="py-2.5 px-2 text-right text-slate-600">${formatCurrency(item.unit_price)}</td>
                <td class="py-2.5 px-3 text-right font-bold text-slate-800">${formatCurrency(item.subtotal)}</td>
            `;
            tbody.appendChild(tr);
        });

        // Timestamps
        const tsContainer = document.getElementById('bill-timestamps');
        tsContainer.innerHTML = '';
        const ts = bill.timestamps || {};
        const labels = [
            ['Order Placed', ts.created_at || ts.order_time],
            ['Payment Verified', ts.payment_time],
            ['Kitchen Preparing', ts.preparing_time],
            ['Ready for Pickup', ts.ready_time],
            ['Completed', ts.completed_time],
            ['Cancelled', ts.cancellation_time]
        ];

        labels.forEach(([label, timeVal]) => {
            if (timeVal) {
                const row = document.createElement('div');
                row.className = 'flex justify-between items-center';
                row.innerHTML = `<span>${label}:</span> <span class="font-medium text-slate-700">${timeVal}</span>`;
                tsContainer.appendChild(row);
            }
        });

        const modal = document.getElementById('bill-modal');
        if (modal) modal.classList.remove('hidden');
    } catch (e) {
        alert('Network error while retrieving order bill.');
    }
}

async function cancelOrder(orderId) {
    if (!confirm('Are you sure you want to cancel this order? Stock will be restored and any wallet deduction refunded.')) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/orders/${orderId}/cancel`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alert('✓ ' + data.message);
            await loadCustomerOrders();
        } else {
            alert(data.message || 'Failed to cancel order.');
        }
    } catch (e) {
        alert('Error communicating with server to cancel order.');
    }
}

async function loadCustomerOrders() {
    const container = document.getElementById('orders-container');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/orders/my-orders`, { credentials: 'include' });
        const data = await res.json();

        if (data.success && data.orders) {
            container.innerHTML = '';

            if (data.orders.length === 0) {
                container.innerHTML = `
                    <div class="bg-white p-12 rounded-3xl border border-slate-200 text-center py-12">
                        <i class="fa-solid fa-receipt text-4xl text-slate-300 mb-3"></i>
                        <h3 class="font-bold text-slate-800 text-lg">No orders placed yet</h3>
                        <p class="text-xs text-slate-400 mt-1">Explore our digital food court menu to place your first pre-order.</p>
                        <a href="menu.html" class="inline-block mt-4 px-5 py-2.5 rounded-xl bg-teal-700 text-white font-bold text-xs hover:bg-teal-800 transition-all">Browse Menu →</a>
                    </div>
                `;
                return;
            }

            data.orders.forEach(order => {
                const statusStyles = {
                    pending: 'bg-amber-100 text-amber-800 border-amber-200',
                    preparing: 'bg-blue-100 text-blue-800 border-blue-200',
                    ready: 'bg-emerald-100 text-emerald-800 border-emerald-200',
                    completed: 'bg-slate-100 text-slate-700 border-slate-200',
                    cancelled: 'bg-red-100 text-red-700 border-red-200',
                };
                const badge = statusStyles[order.order_status] || 'bg-slate-100 text-slate-700';

                const payBadgeStyle = 
                    order.payment_status === 'paid' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' :
                    order.payment_status === 'pending' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                    'bg-red-100 text-red-700 border-red-200';

                const card = document.createElement('article');
                card.className = 'bg-white rounded-3xl p-5 sm:p-6 border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between gap-4';
                card.innerHTML = `
                    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                        <div>
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="text-xs font-black text-teal-700">#${order.order_reference}</span>
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${badge}">
                                    ${order.order_status}
                                </span>
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase border ${payBadgeStyle}">
                                    Pay: ${order.payment_status}
                                </span>
                            </div>
                            <h3 class="font-black text-slate-900 text-lg mt-1">${order.shop_name}</h3>
                            <p class="text-xs text-slate-600 mt-0.5">${order.items_summary || 'Order Items'}</p>
                        </div>
                        <div class="bg-slate-50 p-3 rounded-2xl border border-slate-200 text-center sm:text-right shrink-0">
                            <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Pickup OTP</span>
                            <strong class="text-xl font-black text-slate-800 tracking-widest block">${order.pickup_otp}</strong>
                            <span class="text-[10px] text-slate-500">${order.order_status === 'completed' ? 'Order Fulfilled ✓' : 'Show at stall'}</span>
                        </div>
                    </div>
                    <div class="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-3">
                        <div class="flex items-center gap-3">
                            <span>Total: <strong class="text-slate-900 font-bold">${formatCurrency(order.total_amount)}</strong> (${order.payment_method})</span>
                            <span class="text-[11px] text-slate-400">${order.created_at || 'Recent'}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <button onclick="viewOrderBill(${order.order_id})" class="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs transition-colors flex items-center gap-1">
                                <i class="fa-solid fa-receipt text-[11px]"></i> Bill
                            </button>
                            ${order.payment_status === 'pending' && (order.payment_method.includes('Online') || order.payment_method.includes('UPI')) ? `
                                <button onclick="payPendingOrder(${order.order_id})" class="px-3 py-1.5 rounded-xl bg-teal-700 hover:bg-teal-800 text-white font-bold text-xs transition-colors shadow-sm">
                                    Pay Now
                                </button>
                            ` : ''}
                            ${order.order_status === 'pending' ? `
                                <button onclick="cancelOrder(${order.order_id})" class="px-3 py-1.5 rounded-xl bg-red-50 hover:bg-red-100 text-red-600 font-bold text-xs transition-colors border border-red-200">
                                    Cancel Order
                                </button>
                            ` : ''}
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        container.innerHTML = '<p class="text-xs text-red-500 p-4 text-center">Unable to load orders right now.</p>';
    }
}

async function payPendingOrder(orderId) {
    try {
        const res = await fetch(`${API_BASE_URL}/payments/${orderId}/status`, { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.success || !data.payment) {
            alert('Unable to load payment details.');
            return;
        }

        const payment = data.payment;
        if (payment.status === 'successful' || data.payment_status === 'paid') {
            alert('This order is already paid!');
            await loadCustomerOrders();
            return;
        }

        if (typeof Razorpay === 'undefined') {
            alert('Payment gateway library is loading. Please try again in a moment.');
            return;
        }

        const options = {
            key: payment.key_id || window.RAZORPAY_KEY_ID || '',
            amount: Math.round(payment.amount * 100),
            currency: 'INR',
            name: 'KPR Food Court',
            description: `Order #${orderId}`,
            order_id: payment.gateway_order_id,
            handler: async function (response) {
                const verifyRes = await fetch(`${API_BASE_URL}/orders/${orderId}/verify-payment`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        razorpay_order_id: response.razorpay_order_id,
                        razorpay_payment_id: response.razorpay_payment_id,
                        razorpay_signature: response.razorpay_signature
                    })
                });
                const verifyData = await verifyRes.json();
                if (verifyRes.ok && verifyData.success) {
                    alert('✓ Payment confirmed! Your order is now paid.');
                    await loadCustomerOrders();
                } else {
                    alert(verifyData.message || 'Payment verification failed.');
                }
            },
            prefill: {
                name: 'College Customer',
                email: 'student@kpriet.ac.in',
                contact: '9876543210'
            },
            theme: { color: '#0f766e' }
        };
        new Razorpay(options).open();
    } catch (e) {
        alert('Failed to initiate payment.');
    }
}

document.addEventListener('DOMContentLoaded', loadCustomerOrders);
window.viewOrderBill = viewOrderBill;
window.cancelOrder = cancelOrder;
window.closeBillModal = closeBillModal;
window.payPendingOrder = payPendingOrder;
