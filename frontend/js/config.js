/**
 * Frontend Production Configuration
 * Dynamically resolves API Base URL based on hosting environment.
 */
(function () {
    if (!window.FOOD_COURT_API_BASE) {
        var origin = window.location.origin || "";
        var isLocalDev = (
            origin.indexOf(":5500") !== -1 ||
            origin.indexOf(":3000") !== -1 ||
            origin.indexOf(":8080") !== -1 ||
            origin.indexOf(":5000") !== -1 ||
            window.location.protocol === "file:"
        );

        if (isLocalDev) {
            window.FOOD_COURT_API_BASE = (origin.indexOf(":5000") !== -1)
                ? origin + "/api"
                : "http://127.0.0.1:5000/api";
        } else {
            window.FOOD_COURT_API_BASE = "https://college-food-court-api.onrender.com/api";
        }
    }

    // Public Razorpay Key for official client-side checkout modal
    // Note: NEVER place RAZORPAY_KEY_SECRET in frontend files.
    // Client-side checkout receives key_id dynamically from backend order response (/api/orders).
    if (!window.RAZORPAY_KEY_ID) {
        window.RAZORPAY_KEY_ID = "";
    }

    window.getApiUrl = function (path) {
        var base = window.FOOD_COURT_API_BASE.replace(/\/+$/, "");
        var cleanPath = (path || "").replace(/^\/+/, "");
        return base + "/" + cleanPath;
    };

    // Attach the signed auth token to API calls when the browser does not
    // persist the cross-origin Flask session cookie.
    var originalFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        init = init || {};
        var url = typeof input === "string" ? input : (input && input.url) || "";
        var apiBase = (window.FOOD_COURT_API_BASE || "").replace(/\/+$/, "");
        var token = null;
        try { token = localStorage.getItem("foodCourtAuthToken"); } catch (e) {}
        if (token && apiBase && url.indexOf(apiBase + "/") === 0) {
            var headers = new Headers(init.headers || {});
            if (!headers.has("Authorization")) {
                headers.set("Authorization", "Bearer " + token);
            }
            init.headers = headers;
        }
        return originalFetch(input, init).then(function (response) {
            if (apiBase && url.indexOf(apiBase + "/auth/logout") === 0) {
                try { localStorage.removeItem("foodCourtAuthToken"); } catch (e) {}
            }
            return response;
        });
    };
})();
