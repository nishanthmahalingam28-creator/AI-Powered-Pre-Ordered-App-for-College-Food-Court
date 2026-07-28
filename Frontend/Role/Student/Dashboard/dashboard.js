let menuData = [
    { id: 1, name: "Special Dish A", price: 120, category: "Main Course", quantity: 15, available: true },
    { id: 2, name: "Special Dish B", price: 80, category: "Snacks", quantity: 8, available: true },
    { id: 3, name: "Fresh Mango Juice", price: 50, category: "Beverages", quantity: 0, available: false }
];

let ordersData = [
    { id: "TK-201", items: "2x Special Meal Ticket", completed: false },
    { id: "TK-202", items: "1x Fresh Juice, 1x Snack Combo", completed: false }
];

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
    initShopName();
    renderMenuItems();
    renderOrders();
});

// Parse URL for Shop Name
function initShopName() {
    const urlParams = new URLSearchParams(window.location.search);
    const selectedShop = urlParams.get('shop') || 'YPR';

    document.getElementById('outlet-name').innerText = selectedShop + ' Stall';
    document.getElementById('title-shop-name').innerText = selectedShop;
}

// Render Menu Items with Quantity Controls
function renderMenuItems() {
    const container = document.getElementById("menu-items-list");
    container.innerHTML = "";

    menuData.forEach(item => {
        const itemEl = document.createElement("div");
        itemEl.className = "bg-slate-50 p-3 rounded-2xl border border-slate-100 flex items-center justify-between gap-2";
        
        const isOutOfStock = item.quantity <= 0 || !item.available;

        itemEl.innerHTML = `
            <div class="flex-grow">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-slate-800">${item.name}</span>
                    <span class="text-xs font-semibold text-blue-600">(₹${item.price})</span>
                </div>
                <div class="flex items-center gap-2 mt-0.5">
                    <span class="text-[10px] text-slate-400 font-medium">${item.category}</span>
                    ${isOutOfStock ? '<span class="text-[10px] bg-red-100 text-red-600 font-bold px-1.5 py-0.5 rounded-md">Out of Stock</span>' : ''}
                </div>
            </div>

            <!-- Quantity Controls -->
            <div class="flex items-center gap-1.5 bg-white px-2 py-1 rounded-xl border border-slate-200">
                <button onclick="updateQuantity(${item.id}, -1)" class="w-5 h-5 flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-bold transition-colors">
                    -
                </button>
                <span class="text-xs font-extrabold w-6 text-center ${item.quantity < 5 ? 'text-amber-600' : 'text-slate-800'}">
                    ${item.quantity}
                </span>
                <button onclick="updateQuantity(${item.id}, 1)" class="w-5 h-5 flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-bold transition-colors">
                    +
                </button>
            </div>

            <!-- Availability Toggle Switch -->
            <label class="relative inline-flex items-center cursor-pointer ml-1">
                <input type="checkbox" class="sr-only peer" ${item.available && item.quantity > 0 ? 'checked' : ''} onchange="toggleItemAvailability(${item.id})">
                <div class="w-8 h-4 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
        `;
        container.appendChild(itemEl);
    });
}

// Adjust Quantity with + / - Buttons
function updateQuantity(itemId, change) {
    const item = menuData.find(i => i.id === itemId);
    if (item) {
        item.quantity = Math.max(0, item.quantity + change);
        // Automatically set available to false if quantity reaches zero
        if (item.quantity === 0) {
            item.available = false;
        } else if (item.quantity > 0 && change > 0 && !item.available) {
            item.available = true; // Auto-enable if stock added
        }
        renderMenuItems();
    }
}

// Render Orders List
function renderOrders() {
    const container = document.getElementById("orders-list");
    container.innerHTML = "";

    const activeOrders = ordersData.filter(o => !o.completed);
    document.getElementById("active-orders-count").innerText = `${activeOrders.length} Active`;

    ordersData.forEach(order => {
        const orderEl = document.createElement("div");
        orderEl.className = "bg-slate-50 p-3.5 rounded-2xl border border-slate-100 flex items-center justify-between";
        orderEl.innerHTML = `
            <div>
                <span class="text-xs font-bold text-blue-900">#${order.id}</span>
                <p class="text-xs text-slate-600 font-medium">${order.items}</p>
            </div>
            <button 
                onclick="completeOrder('${order.id}')" 
                class="${order.completed ? 'bg-emerald-600' : 'bg-blue-600 hover:bg-blue-700'} text-white text-xs font-bold px-3 py-1.5 rounded-xl transition-colors"
                ${order.completed ? 'disabled' : ''}>
                ${order.completed ? 'Completed' : 'Complete'}
            </button>
        `;
        container.appendChild(orderEl);
    });
}

// Complete Order Action
function completeOrder(orderId) {
    const order = ordersData.find(o => o.id === orderId);
    if (order) {
        order.completed = true;
        renderOrders();
    }
}

// Toggle Item Availability State
function toggleItemAvailability(itemId) {
    const item = menuData.find(i => i.id === itemId);
    if (item) {
        item.available = !item.available;
        renderMenuItems();
    }
}

// Modal Visibility Control
function toggleModal(show) {
    const modal = document.getElementById("add-item-modal");
    if (show) {
        modal.classList.remove("hidden");
    } else {
        modal.classList.add("hidden");
        document.getElementById("add-item-form").reset();
    }
}

// Handle Form Submission for Adding New Item
function handleAddItem(event) {
    event.preventDefault();

    const name = document.getElementById("item-name").value.trim();
    const price = parseFloat(document.getElementById("item-price").value);
    const quantity = parseInt(document.getElementById("item-quantity").value) || 0;
    const category = document.getElementById("item-category").value;
    const available = document.getElementById("item-available").checked;

    if (!name || isNaN(price)) return;

    const newItem = {
        id: Date.now(),
        name,
        price,
        quantity,
        category,
        available: quantity > 0 ? available : false
    };

    menuData.push(newItem);
    renderMenuItems();
    toggleModal(false);
}