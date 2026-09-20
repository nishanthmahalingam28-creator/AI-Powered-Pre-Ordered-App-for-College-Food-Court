const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

function money(value) {
    return `₹${Number(value || 0).toFixed(2)}`;
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

async function loadSalesAnalytics() {
    const refreshBtn = document.getElementById('refresh-btn');
    const errorBox = document.getElementById('error-box');
    if (refreshBtn) refreshBtn.disabled = true;
    if (errorBox) errorBox.classList.add('hidden');

    try {
        const authRes = await fetch(`${API_BASE_URL}/auth/me`, { credentials: 'include' });
        const auth = await authRes.json();
        if (!authRes.ok || !auth.authenticated || !auth.user || (auth.user.role !== 'vendor' && auth.user.role !== 'admin')) {
            window.location.href = 'login.html';
            return;
        }

        const shopRes = await fetch(`${API_BASE_URL}/vendor/shop`, { credentials: 'include' });
        const shopData = await shopRes.json();
        if (!shopRes.ok || !shopData.success || !shopData.shop) {
            throw new Error(shopData.message || 'Unable to resolve your assigned shop.');
        }

        document.getElementById('shop-name').textContent = shopData.shop.name || 'Shop';

        const analyticsRes = await fetch(`${API_BASE_URL}/vendor/analytics`, { credentials: 'include' });
        const data = await analyticsRes.json();
        if (!analyticsRes.ok || !data.success || !data.analytics || !data.analytics.today_sales) {
            throw new Error(data.message || 'Sales analytics are unavailable.');
        }

        const sales = data.analytics.today_sales;
        document.getElementById('report-date').textContent = sales.date;
        document.getElementById('total-food').textContent = sales.total_food_sold;
        document.getElementById('total-orders').textContent = sales.total_orders;
        document.getElementById('total-revenue').textContent = money(sales.total_revenue);
        document.getElementById('average-order').textContent = money(sales.average_order_value);
        document.getElementById('cancelled-orders').textContent = sales.cancelled_orders;

        const mealRows = sales.meal_periods || [];
        const table = document.getElementById('meal-table');
        const labels = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', unknown: 'Unclassified' };
        table.innerHTML = mealRows.map(row => `
            <tr class="border-b border-slate-100">
                <td class="px-5 py-3 font-bold">${labels[row.meal_period] || escapeHtml(row.meal_period)}</td>
                <td class="px-5 py-3 text-right">${row.food_sold}</td>
                <td class="px-5 py-3 text-right">${row.total_orders}</td>
                <td class="px-5 py-3 text-right font-bold">${money(row.revenue)}</td>
            </tr>
        `).join('');

        document.getElementById('meal-total-food').textContent = mealRows.reduce((sum, r) => sum + Number(r.food_sold || 0), 0);
        document.getElementById('meal-total-orders').textContent = sales.total_orders;
        document.getElementById('meal-total-revenue').textContent = money(sales.total_revenue);

        const top = document.getElementById('top-items');
        if (!sales.top_items || !sales.top_items.length) {
            top.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">No completed sales today.</p>';
        } else {
            const maxUnits = Math.max(...sales.top_items.map(x => Number(x.units_sold || 0)), 1);
            top.innerHTML = sales.top_items.map(item => `
                <div>
                    <div class="flex justify-between gap-3 text-xs mb-1">
                        <span class="font-bold truncate">${escapeHtml(item.item_name)}</span>
                        <span class="font-black">${item.units_sold} sold · ${money(item.revenue)}</span>
                    </div>
                    <div class="h-2 bg-slate-100 rounded-full overflow-hidden"><div class="h-full bg-blue-500 rounded-full" style="width:${Math.min(100, Math.round(Number(item.units_sold || 0) / maxUnits * 100))}%"></div></div>
                    <p class="text-[10px] text-slate-400 mt-1">${escapeHtml(labelsForMeal(item.meal_period))}</p>
                </div>
            `).join('');
        }

        const hourly = document.getElementById('hourly-sales');
        if (!sales.hourly_sales || !sales.hourly_sales.length) {
            hourly.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">No completed sales today.</p>';
        } else {
            hourly.innerHTML = sales.hourly_sales.map(row => `
                <div class="flex items-center gap-3 text-xs">
                    <span class="w-14 font-bold text-slate-500">${formatHour(row.hour)}</span>
                    <div class="flex-grow h-2 bg-slate-100 rounded-full overflow-hidden"><div class="h-full bg-emerald-500 rounded-full" style="width:${Math.min(100, Number(row.food_sold || 0) / Math.max(...sales.hourly_sales.map(x => Number(x.food_sold || 0)), 1) * 100)}%"></div></div>
                    <span class="w-24 text-right font-bold">${row.food_sold} · ${money(row.revenue)}</span>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Sales analytics error:', error);
        if (errorBox) {
            errorBox.textContent = error.message || 'Failed to load sales analytics.';
            errorBox.classList.remove('hidden');
        }
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function labelsForMeal(period) {
    return ({ breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', unknown: 'Unclassified' })[period] || period || 'Unclassified';
}

function formatHour(hour) {
    const h = Number(hour);
    const suffix = h >= 12 ? 'PM' : 'AM';
    const display = h % 12 || 12;
    return `${display}:00 ${suffix}`;
}

document.addEventListener('DOMContentLoaded', loadSalesAnalytics);
