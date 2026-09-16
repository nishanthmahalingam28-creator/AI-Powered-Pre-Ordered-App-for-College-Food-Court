/**
 * Customer Notifications Controller
 * Provides real-time notification drawer, unread count polling (10s), and read management.
 */

(function () {
    const API_BASE = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';
    let pollingTimer = null;
    const POLLING_INTERVAL_MS = 10000; // 10 seconds

    // Icon mapping per notification type
    const NOTIF_ICONS = {
        ORDER_PLACED: { icon: 'fa-cart-shopping', color: 'text-blue-500', bg: 'bg-blue-50' },
        PAYMENT_SUCCESS: { icon: 'fa-circle-check', color: 'text-emerald-500', bg: 'bg-emerald-50' },
        PAYMENT_FAILED: { icon: 'fa-circle-exclamation', color: 'text-rose-500', bg: 'bg-rose-50' },
        ORDER_PREPARING: { icon: 'fa-fire-burner', color: 'text-amber-500', bg: 'bg-amber-50' },
        ORDER_READY: { icon: 'fa-bell', color: 'text-teal-500', bg: 'bg-teal-50' },
        ORDER_COMPLETED: { icon: 'fa-award', color: 'text-indigo-500', bg: 'bg-indigo-50' },
        ORDER_CANCELLED: { icon: 'fa-ban', color: 'text-slate-500', bg: 'bg-slate-100' },
        PICKUP_REMINDER: { icon: 'fa-clock', color: 'text-purple-500', bg: 'bg-purple-50' },
        SYSTEM: { icon: 'fa-circle-info', color: 'text-cyan-500', bg: 'bg-cyan-50' }
    };

    async function fetchUnreadCount() {
        try {
            const res = await fetch(`${API_BASE}/notifications/unread-count`, { credentials: 'include' });
            if (!res.ok) {
                if (res.status === 401) stopPolling();
                return;
            }
            const data = await res.json();
            if (data.success) {
                updateBadge(data.unread_count || 0);
            }
        } catch (e) {
            console.debug('Notification poll error:', e);
        }
    }

    function updateBadge(count) {
        const badgeEls = document.querySelectorAll('.notification-badge');
        badgeEls.forEach(el => {
            if (count > 0) {
                el.textContent = count > 99 ? '99+' : count;
                el.classList.remove('hidden');
            } else {
                el.textContent = '0';
                el.classList.add('hidden');
            }
        });
    }

    async function loadNotifications(unreadOnly = false) {
        const container = document.getElementById('notification-items-container');
        if (!container) return;

        container.innerHTML = `
            <div class="py-12 text-center text-slate-400">
                <i class="fa-solid fa-spinner fa-spin text-2xl mb-2 text-teal-600"></i>
                <p class="text-xs font-semibold">Loading notifications...</p>
            </div>
        `;

        try {
            const url = `${API_BASE}/notifications?limit=30${unreadOnly ? '&unread=true' : ''}`;
            const res = await fetch(url, { credentials: 'include' });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (!data.success || !data.notifications || data.notifications.length === 0) {
                container.innerHTML = `
                    <div class="py-12 text-center text-slate-400">
                        <i class="fa-regular fa-bell-slash text-3xl mb-2 text-slate-300"></i>
                        <p class="text-sm font-bold text-slate-600">No notifications yet</p>
                        <p class="text-xs text-slate-400 mt-1">Updates on orders and payments will appear here.</p>
                    </div>
                `;
                updateBadge(0);
                return;
            }

            updateBadge(data.unread_count || 0);
            renderNotificationList(data.notifications, container);
        } catch (e) {
            container.innerHTML = `
                <div class="py-8 text-center text-rose-500">
                    <i class="fa-solid fa-triangle-exclamation text-2xl mb-2"></i>
                    <p class="text-xs font-bold">Failed to load notifications.</p>
                </div>
            `;
        }
    }

    function renderNotificationList(notifications, container) {
        container.innerHTML = '';
        notifications.forEach(item => {
            const styling = NOTIF_ICONS[item.type] || NOTIF_ICONS.SYSTEM;
            const itemDiv = document.createElement('div');
            itemDiv.className = `p-4 rounded-2xl border transition-all duration-200 flex items-start gap-3.5 cursor-pointer relative ${
                item.is_read
                    ? 'bg-white border-slate-100 hover:border-slate-200'
                    : 'bg-teal-50/40 border-teal-200/80 shadow-sm hover:border-teal-300'
            }`;

            itemDiv.innerHTML = `
                <div class="w-10 h-10 rounded-xl ${styling.bg} ${styling.color} flex items-center justify-center shrink-0 text-base shadow-sm">
                    <i class="fa-solid ${styling.icon}"></i>
                </div>
                <div class="flex-grow min-w-0">
                    <div class="flex items-center justify-between gap-2 mb-1">
                        <h4 class="text-xs font-black text-slate-900 truncate">${escapeHtml(item.title)}</h4>
                        <span class="text-[10px] text-slate-400 whitespace-nowrap">${formatTime(item.created_at)}</span>
                    </div>
                    <p class="text-xs text-slate-600 leading-relaxed break-words">${escapeHtml(item.message)}</p>
                </div>
                ${!item.is_read ? '<span class="w-2.5 h-2.5 bg-teal-500 rounded-full shrink-0 mt-1 shadow-sm shadow-teal-500/50"></span>' : ''}
            `;

            itemDiv.addEventListener('click', async () => {
                if (!item.is_read) {
                    await markAsRead(item.id);
                    item.is_read = true;
                    itemDiv.className = 'p-4 rounded-2xl border transition-all duration-200 flex items-start gap-3.5 cursor-pointer relative bg-white border-slate-100';
                    const dot = itemDiv.querySelector('.bg-teal-500');
                    if (dot) dot.remove();
                }
            });

            container.appendChild(itemDiv);
        });
    }

    async function markAsRead(notifId) {
        try {
            const res = await fetch(`${API_BASE}/notifications/${notifId}/read`, {
                method: 'PUT',
                credentials: 'include'
            });
            if (res.ok) {
                const data = await res.json();
                updateBadge(data.unread_count || 0);
            }
        } catch (e) {
            console.error('Failed to mark read:', e);
        }
    }

    async function markAllAsRead() {
        const btn = document.getElementById('notif-mark-all-btn');
        if (btn) btn.disabled = true;

        try {
            const res = await fetch(`${API_BASE}/notifications/read-all`, {
                method: 'PUT',
                credentials: 'include'
            });
            if (res.ok) {
                updateBadge(0);
                await loadNotifications();
            }
        } catch (e) {
            console.error('Failed to mark all read:', e);
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    function toggleNotificationDrawer(show) {
        const drawer = document.getElementById('notification-drawer');
        const backdrop = document.getElementById('notification-backdrop');
        if (!drawer || !backdrop) return;

        if (show) {
            drawer.classList.remove('translate-x-full');
            backdrop.classList.remove('hidden');
            loadNotifications();
        } else {
            drawer.classList.add('translate-x-full');
            backdrop.classList.add('hidden');
        }
    }

    function startPolling() {
        stopPolling();
        fetchUnreadCount();
        pollingTimer = setInterval(fetchUnreadCount, POLLING_INTERVAL_MS);
    }

    function stopPolling() {
        if (pollingTimer) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }
    }

    function formatTime(dtStr) {
        if (!dtStr) return '';
        try {
            const d = new Date(dtStr.replace(' ', 'T'));
            if (isNaN(d.getTime())) return dtStr;
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return dtStr;
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Expose API to window for button clicks and dashboard integration
    window.NotificationCenter = {
        toggleDrawer: toggleNotificationDrawer,
        markAllRead: markAllAsRead,
        loadNotifications: loadNotifications,
        refreshBadge: fetchUnreadCount,
        startPolling: startPolling,
        stopPolling: stopPolling
    };

    // Auto-init on page load
    document.addEventListener('DOMContentLoaded', () => {
        const triggerBtns = document.querySelectorAll('.notification-bell-trigger');
        triggerBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                toggleNotificationDrawer(true);
            });
        });

        const closeBtn = document.getElementById('close-notif-drawer-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => toggleNotificationDrawer(false));
        }

        const backdrop = document.getElementById('notification-backdrop');
        if (backdrop) {
            backdrop.addEventListener('click', () => toggleNotificationDrawer(false));
        }

        const markAllBtn = document.getElementById('notif-mark-all-btn');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', markAllAsRead);
        }

        // Start controlled polling
        startPolling();
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', stopPolling);
})();
