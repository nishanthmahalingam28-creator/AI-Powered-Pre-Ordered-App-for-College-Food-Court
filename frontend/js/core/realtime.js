/* Real-time Food Court events. Never reloads the page. */
(function () {
    const apiBase = window.FOOD_COURT_API_BASE ||
        (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
    const socketOrigin = apiBase.replace(/\/api\/?$/, '');

    function toast(message) {
        let el = document.getElementById('realtime-toast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'realtime-toast';
            el.className = 'fixed top-5 right-5 z-[100] max-w-sm rounded-2xl bg-slate-900 text-white px-4 py-3 shadow-2xl text-xs font-bold opacity-0 pointer-events-none transition-opacity duration-200';
            document.body.appendChild(el);
        }
        el.textContent = message;
        el.classList.remove('opacity-0');
        clearTimeout(window.__realtimeToastTimer);
        window.__realtimeToastTimer = setTimeout(function () {
            el.classList.add('opacity-0');
        }, 2600);
    }

    function refreshPageData() {
        if (typeof window.loadOrders === 'function') window.loadOrders();
        if (typeof window.renderOrders === 'function') window.renderOrders();
        if (typeof window.loadCustomerOrders === 'function') window.loadCustomerOrders();
        if (typeof window.refreshRealtimeOrderData === 'function') window.refreshRealtimeOrderData();
    }

    function connect() {
        if (typeof window.io !== 'function') {
            console.warn('Socket.IO client library is not available.');
            return;
        }

        const socket = window.io(socketOrigin, {
            withCredentials: true,
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            timeout: 10000
        });

        socket.on('connect', function () {
            window.__foodCourtRealtimeConnected = true;
            document.documentElement.dataset.realtime = 'connected';
            console.info('[Food Court] Real-time connection established.');
        });

        socket.on('disconnect', function () {
            window.__foodCourtRealtimeConnected = false;
            document.documentElement.dataset.realtime = 'disconnected';
        });

        socket.on('connect_error', function (error) {
            console.warn('[Food Court] Real-time connection error:', error.message);
        });

        socket.on('order:created', function (data) {
            toast('New order received — updating live.');
            refreshPageData();
            window.dispatchEvent(new CustomEvent('foodcourt:order-created', { detail: data }));
        });

        socket.on('order:status', function (data) {
            const raw = String(data.order_status || '');
            const label = raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : 'Updated';
            toast('Order #' + (data.order_reference || data.order_id) + ' is now ' + label + '.');
            refreshPageData();
            window.dispatchEvent(new CustomEvent('foodcourt:order-status', { detail: data }));
        });

        socket.on('order:cancelled', function (data) {
            toast('Order #' + (data.order_reference || data.order_id) + ' was cancelled.');
            refreshPageData();
            window.dispatchEvent(new CustomEvent('foodcourt:order-cancelled', { detail: data }));
        });

        window.foodCourtSocket = socket;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', connect, { once: true });
    } else {
        connect();
    }
})();
