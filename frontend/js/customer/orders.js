const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

document.addEventListener('DOMContentLoaded', async () => {
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

                const card = document.createElement('article');
                card.className = 'bg-white rounded-3xl p-5 sm:p-6 border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between gap-4';
                card.innerHTML = `
                    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-black text-teal-700">#${order.order_reference}</span>
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${badge}">
                                    ${order.order_status}
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
                    <div class="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-500 gap-2">
                        <span>Total: <strong class="text-slate-900 font-bold">₹${parseFloat(order.total_amount).toFixed(2)}</strong> (${order.payment_method})</span>
                        <span class="text-[11px] text-slate-400">${order.created_at || 'Recent'}</span>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        container.innerHTML = '<p class="text-xs text-red-500 p-4 text-center">Unable to load orders right now.</p>';
    }
});
