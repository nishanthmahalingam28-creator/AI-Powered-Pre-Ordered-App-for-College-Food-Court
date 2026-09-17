/**
 * Production Google Identity Services (GIS) Client Controller.
 *
 * Requirements:
 * 1. Strictly server-side verification: sends Google ID token to backend /api/auth/google.
 * 2. Zero fake/demo fallback: failures, cancellations, and missing config display helpful UI errors.
 * 3. Never trust client-decoded JWT claims.
 * 4. Never expose client secrets.
 */

(function () {
    'use strict';

    const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';
    let googleConfig = null;
    let isGsiInitialized = false;

    // Retrieve or create an alert banner on the current authentication form
    function getAlertContainer() {
        const existing = (
            document.getElementById('google-auth-alert') ||
            document.getElementById('guest-login-alert') ||
            document.getElementById('faculty-login-alert') ||
            document.getElementById('login-alert')
        );
        if (existing) return existing;

        const form = (
            document.getElementById('loginForm') ||
            document.getElementById('guestLoginForm') ||
            document.getElementById('facultyLoginForm') ||
            document.getElementById('signupForm') ||
            document.getElementById('guestSignUpForm') ||
            document.getElementById('facultySignUpForm')
        );
        if (!form) return null;

        const alertBox = document.createElement('div');
        alertBox.id = 'google-auth-alert';
        alertBox.className = 'hidden p-3.5 mb-4 rounded-xl text-xs font-semibold flex items-center gap-2';
        form.parentNode.insertBefore(alertBox, form);
        return alertBox;
    }

    function showAuthNotice(message, type) {
        const container = getAlertContainer();
        if (!container) {
            alert(message);
            return;
        }

        container.classList.remove('hidden');
        if (type === 'error') {
            container.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-red-50 text-red-700 border border-red-200 flex items-center gap-2';
            container.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> <span>${message}</span>`;
        } else if (type === 'success') {
            container.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-2';
            container.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>${message}</span>`;
        } else {
            container.className = 'p-3.5 mb-4 rounded-xl text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-2';
            container.innerHTML = `<i class="fa-solid fa-circle-info"></i> <span>${message}</span>`;
        }
    }

    function detectCustomerType() {
        const select = document.getElementById('customerType');
        if (select && select.value) return select.value;

        const path = window.location.pathname.toLowerCase();
        if (path.includes('guest')) return 'guest';
        if (path.includes('faculty')) return 'faculty';
        return 'student';
    }

    // Dynamic GIS Library Loader
    function loadGsiScript() {
        return new Promise((resolve, reject) => {
            if (window.google && window.google.accounts && window.google.accounts.id) {
                return resolve();
            }

            const existingScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
            if (existingScript) {
                existingScript.addEventListener('load', resolve);
                existingScript.addEventListener('error', () => reject(new Error('Failed to load Google Identity Services library.')));
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://accounts.google.com/gsi/client';
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = () => reject(new Error('Failed to load Google Identity Services library.'));
            document.head.appendChild(script);
        });
    }

    // Fetch public configuration from backend
    async function fetchGoogleConfig() {
        try {
            const res = await fetch(`${API_BASE_URL}/auth/google/config`);
            if (res.ok) {
                googleConfig = await res.json();
                return googleConfig;
            }
        } catch (e) {
            console.warn('[GoogleAuth] Failed to load server Google OAuth config:', e);
        }
        return { success: false, client_id: '', enabled: false };
    }

    // Authoritative credential verification callback
    async function handleCredentialResponse(response) {
        if (!response || !response.credential) {
            showAuthNotice('Google Sign-In failed: No credential received from Google.', 'error');
            return;
        }

        showAuthNotice('Verifying Google credentials with campus server...', 'info');

        try {
            const res = await fetch(`${API_BASE_URL}/auth/google`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    credential: response.credential,
                    customerType: detectCustomerType()
                })
            });

            const data = await res.json();

            if (!res.ok || !data.success) {
                // Show real server rejection error; NEVER fall back to a demo account
                showAuthNotice(data.message || 'Google authentication failed server verification.', 'error');
                return;
            }

            // Real authentication succeeded
            showAuthNotice('Google authentication verified! Entering food court...', 'success');
            if (data.user) {
                sessionStorage.setItem('foodCourtUser', JSON.stringify(data.user));
            }

            setTimeout(() => {
                window.location.href = data.redirect || '../customer/dashboard.html';
            }, 600);

        } catch (err) {
            showAuthNotice('Unable to connect to authentication server for verification. Please check your network connection.', 'error');
        }
    }

    // Initialize GIS and bind trigger buttons
    async function initGoogleAuth() {
        const buttons = [
            document.getElementById('googleLoginBtn'),
            document.getElementById('googleGuestBtn'),
            document.getElementById('googleGuestSignUpBtn'),
            document.getElementById('googleSignUpBtn')
        ].filter(Boolean);

        if (buttons.length === 0) return;

        const config = await fetchGoogleConfig();

        try {
            await loadGsiScript();
        } catch (scriptErr) {
            console.warn('[GoogleAuth] GSI library load error:', scriptErr);
        }

        if (window.google && window.google.accounts && window.google.accounts.id && config && config.client_id) {
            try {
                window.google.accounts.id.initialize({
                    client_id: config.client_id,
                    callback: handleCredentialResponse,
                    auto_select: false,
                    cancel_on_tap_outside: true,
                    context: 'signin'
                });
                isGsiInitialized = true;
            } catch (initErr) {
                console.warn('[GoogleAuth] GSI initialize error:', initErr);
            }
        }

        buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();

                if (!config || !config.client_id) {
                    showAuthNotice(
                        'Google Sign-In is not configured on this server. Set GOOGLE_CLIENT_ID in your environment (.env) configuration.',
                        'error'
                    );
                    return;
                }

                if (!window.google || !window.google.accounts || !isGsiInitialized) {
                    showAuthNotice(
                        'Google Identity Services is unavailable or blocked by your browser. Please ensure accounts.google.com is not blocked.',
                        'error'
                    );
                    return;
                }

                // Trigger Google GIS Prompt with strict cancellation handling
                window.google.accounts.id.prompt((notification) => {
                    if (notification.isNotDisplayed()) {
                        const reason = notification.getNotDisplayedReason();
                        console.info('[GoogleAuth] Prompt not displayed:', reason);
                        showAuthNotice(`Google Sign-In prompt could not be displayed (${reason}). Please allow third-party cookies or try again.`, 'error');
                    } else if (notification.isSkippedMoment()) {
                        const reason = notification.getSkippedReason();
                        console.info('[GoogleAuth] Prompt skipped:', reason);
                        if (reason === 'user_cancel') {
                            showAuthNotice('Google Sign-In was cancelled.', 'error');
                        } else {
                            showAuthNotice(`Google Sign-In was cancelled (${reason}).`, 'error');
                        }
                    } else if (notification.isDismissedMoment()) {
                        const reason = notification.getDismissedReason();
                        console.info('[GoogleAuth] Prompt dismissed:', reason);
                        if (reason !== 'credential_returned') {
                            showAuthNotice('Google Sign-In was closed without signing in.', 'error');
                        }
                    }
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGoogleAuth);
    } else {
        initGoogleAuth();
    }

    window.GoogleAuthModule = {
        fetchConfig: fetchGoogleConfig,
        handleCredentialResponse: handleCredentialResponse
    };
})();
