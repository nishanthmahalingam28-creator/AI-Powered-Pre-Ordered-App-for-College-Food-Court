const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

let selectedShop = '';
let selectedCategory = 'all';
let searchQuery = '';

document.addEventListener('DOMContentLoaded', async () => {
    // Read query params from URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('shop')) {
        selectedShop = urlParams.get('shop');
    }
    if (urlParams.has('q')) {
        searchQuery = urlParams.get('q');
        const searchInput = document.getElementById('menu-search-input');
        if (searchInput) searchInput.value = searchQuery;
    }

    updateCartCount();
    await Promise.all([loadStallFilters(), loadCategoryFilters(), fetchAndRenderMenu()]);

    // Live search listener
    const searchInput = document.getElementById('menu-search-input');
    if (searchInput) {
        let timer = null;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                searchQuery = e.target.value.trim();
                fetchAndRenderMenu();
            }, 300);
        });
    }
});

let cachedCart = [];

async function updateCartCount() {
    try {
        const res = await fetch(`${API_BASE_URL}/cart`, { credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.summary) {
                cachedCart = data.cart || [];
                const badge = document.getElementById('cart-count');
                if (badge) badge.textContent = String(data.summary.total_items || 0);
            }
        }
    } catch (e) {
        // Silently catch network errors for public preview
    }
}

function readCart() {
    return cachedCart;
}

async function addToCart(item, btn) {
    if (btn) btn.disabled = true;

    try {
        let res = await fetch(`${API_BASE_URL}/cart`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ item_id: item.id, quantity: 1 })
        });

        if (res.status === 401) {
            const shouldLogin = confirm('Please log in to add items to your cart and place pre-orders. Would you like to log in now?');
            if (shouldLogin) {
                window.location.href = '../auth/login.html';
            }
            return;
        }

        let data = await res.json().catch(() => ({}));

        // Handle single-stall conflict: offer to clear conflicting stall and switch
        if (res.status === 409 && data.conflict) {
            const shouldSwitch = confirm(
                `${data.message}\n\nWould you like to clear your existing cart to start an order from ${data.new_shop_name || 'this stall'}?`
            );
            if (!shouldSwitch) {
                return;
            }

            res = await fetch(`${API_BASE_URL}/cart`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ item_id: item.id, quantity: 1, clear_conflicting_stall: true })
            });
            data = await res.json().catch(() => ({}));
        }

        if (res.ok && data.success) {
            cachedCart = data.cart || [];
            const badge = document.getElementById('cart-count');
            if (badge && data.summary) badge.textContent = String(data.summary.total_items || 0);

            if (btn) {
                const orig = btn.innerHTML;
                btn.innerHTML = '<i class="fa-solid fa-check mr-1"></i> Added';
                btn.classList.add('bg-emerald-600');
                setTimeout(() => {
                    btn.innerHTML = orig;
                    btn.classList.remove('bg-emerald-600');
                }, 900);
            }
        } else {
            alert(data.message || 'Unable to add item to cart. Please try again.');
        }
    } catch (err) {
        console.error('Add to cart API error:', err);
        alert('Could not connect to the server to update cart.');
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function loadStallFilters() {
    const container = document.getElementById('stall-filters');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE_URL}/shops`);
        const data = await res.json();
        if (data.success && data.shops) {
            container.innerHTML = '';

            // 'All Stalls' pill
            const allBtn = document.createElement('button');
            allBtn.className = `px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${!selectedShop ? 'bg-teal-700 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`;
            allBtn.textContent = 'All Stalls';
            allBtn.onclick = async () => {
                selectedShop = '';
                selectedCategory = 'all';
                updateStallActivePills();
                await loadCategoryFilters();
                fetchAndRenderMenu();
            };
            container.appendChild(allBtn);

            data.shops.forEach(stall => {
                const btn = document.createElement('button');
                const isActive = selectedShop.toLowerCase() === stall.name.toLowerCase();
                btn.className = `stall-pill px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${isActive ? 'bg-teal-700 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`;
                btn.textContent = stall.name;
                btn.dataset.stall = stall.name;
                btn.onclick = async () => {
                    selectedShop = stall.name;
                    selectedCategory = 'all';
                    updateStallActivePills();
                    await loadCategoryFilters();
                    fetchAndRenderMenu();
                };
                container.appendChild(btn);
            });
        }
    } catch (e) {}
}

function updateStallActivePills() {
    const container = document.getElementById('stall-filters');
    if (!container) return;
    container.querySelectorAll('button').forEach(btn => {
        const isAll = btn.textContent === 'All Stalls';
        const active = (isAll && !selectedShop) || (!isAll && btn.dataset.stall?.toLowerCase() === selectedShop.toLowerCase());
        btn.className = `px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${active ? 'bg-teal-700 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`;
    });
}

async function loadCategoryFilters() {
    const container = document.getElementById('category-filters');
    if (!container) return;

    let categories = ['all'];
    try {
        const url = selectedShop 
            ? `${API_BASE_URL}/categories?shop=${encodeURIComponent(selectedShop)}`
            : `${API_BASE_URL}/categories`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.success && Array.isArray(data.categories)) {
            categories = ['all', ...data.categories];
        }
    } catch (e) {
        console.warn('Failed to load categories from server:', e);
    }

    // Reset selectedCategory if not in the new category list
    if (selectedCategory !== 'all' && !categories.includes(selectedCategory)) {
        selectedCategory = 'all';
    }

    container.innerHTML = '';

    categories.forEach(cat => {
        const btn = document.createElement('button');
        const isActive = selectedCategory.toLowerCase() === cat.toLowerCase();
        btn.className = `cat-pill px-3 py-1 rounded-xl text-[11px] font-bold transition-all ${isActive ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`;
        btn.textContent = cat === 'all' ? 'All Categories' : cat;
        btn.dataset.cat = cat;
        btn.onclick = () => {
            selectedCategory = cat;
            container.querySelectorAll('.cat-pill').forEach(b => {
                const act = b.dataset.cat.toLowerCase() === selectedCategory.toLowerCase();
                b.className = `cat-pill px-3 py-1 rounded-xl text-[11px] font-bold transition-all ${act ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`;
            });
            fetchAndRenderMenu();
        };
        container.appendChild(btn);
    });
}

async function fetchAndRenderMenu() {
    const grid = document.getElementById('dishes-grid');
    const countBadge = document.getElementById('items-count-badge');
    const headerTitle = document.getElementById('menu-results-header');
    if (!grid) return;

    let queryParams = new URLSearchParams();
    if (selectedShop) queryParams.append('shop', selectedShop);
    if (selectedCategory && selectedCategory !== 'all') queryParams.append('category', selectedCategory);
    if (searchQuery) queryParams.append('q', searchQuery);

    try {
        const res = await fetch(`${API_BASE_URL}/menu?${queryParams.toString()}`);
        const data = await res.json();

        if (headerTitle) {
            headerTitle.textContent = selectedShop ? `${selectedShop} Menu` : 'Available Food Court Dishes';
        }

        if (data.success && data.items) {
            if (countBadge) countBadge.textContent = `${data.items.length} Dishes Found`;
            grid.innerHTML = '';

            if (data.items.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-3 bg-white p-12 rounded-3xl border border-slate-100 text-center py-12">
                        <i class="fa-solid fa-utensils text-4xl text-slate-300 mb-3"></i>
                        <h3 class="font-bold text-slate-800 text-lg">No dishes found</h3>
                        <p class="text-xs text-slate-400 mt-1">Try changing stall or category filters.</p>
                    </div>
                `;
                return;
            }

            data.items.forEach(item => {
                const isAvailable = item.is_available && item.quantity > 0;
                const card = document.createElement('article');
                card.className = 'bg-white rounded-3xl p-5 border border-slate-100 shadow-sm hover:shadow-md transition-all flex flex-col justify-between';
                card.innerHTML = `
                    <div>
                        <div class="flex items-start justify-between gap-3 mb-2">
                            <div>
                                <span class="text-[10px] font-black uppercase tracking-wider text-teal-700 bg-teal-50 px-2 py-0.5 rounded-md border border-teal-100">
                                    ${item.shop_name}
                                </span>
                                <h3 class="font-bold text-base text-slate-800 mt-1.5">${item.name}</h3>
                            </div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${isAvailable ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-700'}">
                                ${isAvailable ? 'In Stock' : 'OUT OF STOCK'}
                            </span>
                        </div>
                        <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed mt-1">${item.description || item.category}</p>
                    </div>
                    <div class="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
                        <strong class="text-lg font-black text-slate-900">₹${parseFloat(item.price).toFixed(2)}</strong>
                        <button type="button" 
                            class="font-bold text-xs px-4 py-2.5 rounded-xl transition-all shadow-sm ${isAvailable ? 'bg-teal-700 hover:bg-teal-800 text-white cursor-pointer active:scale-95' : 'bg-slate-100 text-slate-400 cursor-not-allowed'}"
                            ${!isAvailable ? 'disabled' : ''}
                            onclick='addToCart(${JSON.stringify({ id: item.id, name: item.name, shop: item.shop_name, price: item.price })}, this)'>
                            ${isAvailable ? '<i class="fa-solid fa-plus text-[10px] mr-1"></i> Add' : 'OUT OF STOCK'}
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
        }
    } catch (e) {
        grid.innerHTML = '<p class="text-xs text-red-500 p-4 col-span-3 text-center">Unable to load menu. Ensure the Flask backend is running.</p>';
    }
}
