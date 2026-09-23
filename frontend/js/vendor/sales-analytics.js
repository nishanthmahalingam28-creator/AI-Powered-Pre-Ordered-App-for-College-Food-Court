const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

function money(value) {
    return `₹${Number(value || 0).toFixed(2)}`;
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

let latestSalesData = null;
let selectedPeriod = 'daily';
let vendorContext = null;

function getDateInput(id) {
    return document.getElementById(id)?.value || '';
}

function setDefaultCustomDates() {
    const start = document.getElementById('custom-start');
    const end = document.getElementById('custom-end');
    if (!start || !end) return;
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    end.value = `${yyyy}-${mm}-${dd}`;
    const weekAgo = new Date(today);
    weekAgo.setDate(today.getDate() - 6);
    start.value = `${weekAgo.getFullYear()}-${String(weekAgo.getMonth() + 1).padStart(2, '0')}-${String(weekAgo.getDate()).padStart(2, '0')}`;
}

function updatePeriodUI() {
    const customBox = document.getElementById('custom-range-box');
    if (customBox) customBox.classList.toggle('hidden', selectedPeriod !== 'custom');
    const customStart = getDateInput('custom-start');
    const customEnd = getDateInput('custom-end');
    const applyBtn = document.getElementById('apply-custom-btn');
    if (applyBtn) applyBtn.disabled = selectedPeriod === 'custom' && (!customStart || !customEnd);
}

async function applySalesPeriod(period) {
    selectedPeriod = period;
    updatePeriodUI();
    if (period !== 'custom') {
        await loadSalesAnalytics(period);
    }
}

async function applyCustomDateRange() {
    const start = getDateInput('custom-start');
    const end = getDateInput('custom-end');
    if (!start || !end) {
        alert('Please select both start and end dates.');
        return;
    }
    if (end < start) {
        alert('End date cannot be before start date.');
        return;
    }
    selectedPeriod = 'custom';
    await loadSalesAnalytics('custom', start, end);
}

async function loadSalesAnalytics(period = selectedPeriod, customStart = getDateInput('custom-start'), customEnd = getDateInput('custom-end')) {
    const refreshBtn = document.getElementById('refresh-btn');
    const errorBox = document.getElementById('error-box');
    if (refreshBtn) refreshBtn.disabled = true;
    if (errorBox) errorBox.classList.add('hidden');

    try {
        // Resolve the authenticated vendor/shop only once per page.
        // Period changes and refreshes reuse this context instead of making
        // another /auth/me + /vendor/shop round trip every time.
        if (!vendorContext) {
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

            vendorContext = { user: auth.user, shop: shopData.shop };
            document.getElementById('shop-name').textContent = shopData.shop.name || 'Shop';
        }

        const params = new URLSearchParams();
        params.set('period', period);
        if (period === 'custom') {
            if (!customStart || !customEnd) {
                throw new Error('Select a custom start date and end date.');
            }
            params.set('start_date', customStart);
            params.set('end_date', customEnd);
        }

        const analyticsRes = await fetch(`${API_BASE_URL}/vendor/analytics?${params.toString()}`, { credentials: 'include' });
        const data = await analyticsRes.json();
        if (!analyticsRes.ok || !data.success || !data.analytics || !data.analytics.today_sales) {
            throw new Error(data.message || 'Sales analytics are unavailable.');
        }

        const sales = data.analytics.today_sales;
        latestSalesData = sales;
        selectedPeriod = sales.period || period;

        document.getElementById('report-date').textContent = sales.range_label || sales.date;
        document.getElementById('period-label').textContent = periodLabel(sales.period);
        document.getElementById('total-food').textContent = sales.total_food_sold;
        document.getElementById('total-orders').textContent = sales.total_orders;
        document.getElementById('total-revenue').textContent = money(sales.total_revenue);
        document.getElementById('average-order').textContent = money(sales.average_order_value);
        document.getElementById('cancelled-orders').textContent = sales.cancelled_orders;
        const periodText = periodLabel(sales.period);
        const reportDateText = sales.range_label || sales.date;
        const filterSummary = document.getElementById('filter-summary');
        if (filterSummary) filterSummary.textContent = `Showing all completed sales for ${periodText.toLowerCase()} (${reportDateText}).`;
        const topPeriod = document.getElementById('top-items-period');
        if (topPeriod) topPeriod.textContent = `${periodText} completed sales.`;
        const hourlyPeriod = document.getElementById('hourly-period');
        if (hourlyPeriod) hourlyPeriod.textContent = `${periodText} sales, grouped by hour.`;

        renderMealPeriods(sales);
        renderTopItems(sales);
        renderFilteredSummary(sales);
        updatePeriodUI();
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

function periodLabel(period) {
    return ({
        daily: 'Today',
        weekly: 'This Week',
        monthly: 'This Month',
        yearly: 'This Year',
        custom: 'Custom Range'
    })[period] || 'Sales';
}

function renderMealPeriods(sales) {
    const mealRows = sales.meal_periods || [];
    const labels = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', unknown: 'Unclassified' };
    const table = document.getElementById('meal-table');
    if (table) {
        table.innerHTML = mealRows.map(row => `
            <tr class="border-b border-slate-100">
                <td class="px-5 py-3 font-bold">${labels[row.meal_period] || escapeHtml(row.meal_period)}</td>
                <td class="px-5 py-3 text-right">${row.food_sold}</td>
                <td class="px-5 py-3 text-right">${row.total_orders}</td>
                <td class="px-5 py-3 text-right font-bold">${money(row.revenue)}</td>
            </tr>
        `).join('');
    }
    const totalFood = mealRows.reduce((sum, r) => sum + Number(r.food_sold || 0), 0);
    if (document.getElementById('meal-total-food')) document.getElementById('meal-total-food').textContent = totalFood;
    if (document.getElementById('meal-total-orders')) document.getElementById('meal-total-orders').textContent = sales.total_orders;
    if (document.getElementById('meal-total-revenue')) document.getElementById('meal-total-revenue').textContent = money(sales.total_revenue);
}

function renderTopItems(sales) {
    const top = document.getElementById('top-items');
    if (!top) return;
    if (!sales.top_items || !sales.top_items.length) {
        top.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">No completed sales for this period.</p>';
        return;
    }
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

function labelsForMeal(period) {
    return ({ breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', unknown: 'Unclassified' })[period] || period || 'Unclassified';
}

function formatHour(hour) {
    const h = Number(hour);
    const suffix = h >= 12 ? 'PM' : 'AM';
    const display = h % 12 || 12;
    return `${display}:00 ${suffix}`;
}

function renderFilteredSummary(sales) {
    const summary = document.getElementById('filter-summary');
    if (summary) summary.textContent = `Showing all completed sales for ${periodLabel(sales.period).toLowerCase()} (${sales.range_label || sales.date}).`;
    const hourly = document.getElementById('hourly-sales');
    if (!hourly) return;
    if (!sales.hourly_sales || !sales.hourly_sales.length) {
        hourly.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">No completed sales for this period.</p>';
        return;
    }
    const maxFood = Math.max(...sales.hourly_sales.map(x => Number(x.food_sold || 0)), 1);
    hourly.innerHTML = sales.hourly_sales.map(row =>
        '<div class="flex items-center gap-3 text-xs">' +
        '<span class="w-20 font-bold text-slate-500">' + formatHour(row.hour) + '</span>' +
        '<div class="flex-grow h-2 bg-slate-100 rounded-full overflow-hidden"><div class="h-full bg-emerald-500 rounded-full" style="width:' +
        Math.min(100, Number(row.food_sold || 0) / maxFood * 100) + '%"></div></div>' +
        '<span class="w-32 text-right font-bold">' + row.food_sold + ' · ' + money(row.revenue) + '</span></div>'
    ).join('');
}

function downloadSalesReport(format) {
    if (!latestSalesData) {
        alert('Sales data is still loading. Please try again.');
        return;
    }
    const sales = latestSalesData;
    const shop = document.getElementById('shop-name')?.textContent || 'Shop';
    const rows = sales.hourly_sales || [];
    const safePeriod = (sales.period || 'sales') + '-' + (sales.start_date || sales.date).replace(/[^0-9A-Za-z_-]/g, '_');

    if (format === 'csv') {
        const lines = [
            ['Sales Report', shop],
            ['Period', periodLabel(sales.period)],
            ['Start Date', sales.start_date],
            ['End Date', sales.end_date],
            ['Timezone', sales.timezone],
            [],
            ['Meal Period','Food Sold','Orders','Revenue'],
            ...(sales.meal_periods || []).map(x => [x.meal_period,x.food_sold,x.total_orders,Number(x.revenue||0).toFixed(2)]),
            [],
            ['Total Food Sold',sales.total_food_sold],
            ['Total Orders',sales.total_orders],
            ['Total Revenue',Number(sales.total_revenue||0).toFixed(2)],
            ['Average Order Value',Number(sales.average_order_value||0).toFixed(2)],
            ['Cancelled Orders',sales.cancelled_orders],
            [],
            ['Hour','Food Sold','Orders','Revenue'],
            ...rows.map(x => [formatHour(x.hour),x.food_sold,x.total_orders,Number(x.revenue||0).toFixed(2)])
        ];
        const csv = lines.map(row => row.map(v => '"' + String(v ?? '').replace(/"/g,'""') + '"').join(',')).join('\n');
        triggerDownload(csv,'text/csv;charset=utf-8', `sales-report-${safePeriod}.csv`);
    } else {
        const reportRows=(sales.meal_periods||[]).map(x => '<tr><td>'+escapeHtml(x.meal_period)+'</td><td>'+x.food_sold+'</td><td>'+x.total_orders+'</td><td>₹'+Number(x.revenue||0).toFixed(2)+'</td></tr>').join('');
        const hourlyRows=rows.map(x => '<tr><td>'+formatHour(x.hour)+'</td><td>'+x.food_sold+'</td><td>'+x.total_orders+'</td><td>₹'+Number(x.revenue||0).toFixed(2)+'</td></tr>').join('');
        const html='<html><head><meta charset="UTF-8"><title>Sales Report</title><style>body{font-family:Arial;padding:32px;color:#1e293b}h1{margin-bottom:4px}table{border-collapse:collapse;width:100%;margin-top:18px}th,td{border:1px solid #ddd;padding:9px;text-align:left}th{background:#f1f5f9}</style></head><body><h1>Sales Report - '+escapeHtml(shop)+'</h1><p>Period: '+escapeHtml(periodLabel(sales.period))+' | '+escapeHtml(sales.start_date)+' to '+escapeHtml(sales.end_date)+' | '+escapeHtml(sales.timezone)+'</p><h2>Summary</h2><p>Food Sold: '+sales.total_food_sold+' | Orders: '+sales.total_orders+' | Revenue: ₹'+Number(sales.total_revenue||0).toFixed(2)+' | Average Order: ₹'+Number(sales.average_order_value||0).toFixed(2)+'</p><h2>Meal Period</h2><table><tr><th>Meal Period</th><th>Food Sold</th><th>Orders</th><th>Revenue</th></tr>'+reportRows+'</table><h2>Hourly Sales</h2><table><tr><th>Hour</th><th>Food Sold</th><th>Orders</th><th>Revenue</th></tr>'+hourlyRows+'</table></body></html>';
        triggerDownload(html,'text/html;charset=utf-8',`sales-report-${safePeriod}.html`);
    }
}

function triggerDownload(content,mime,filename) {
    const blob=new Blob([content],{type:mime});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;
    a.download=filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
}

document.addEventListener('DOMContentLoaded', () => {
    setDefaultCustomDates();
    updatePeriodUI();
    loadSalesAnalytics('daily');
});
