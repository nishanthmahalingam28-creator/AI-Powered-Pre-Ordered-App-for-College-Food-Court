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

    // Public Google OAuth 2.0 Client ID for Google Identity Services (GIS)
    // Note: Google Client ID is safe for public client-side exposure (unlike Client Secret).
    // The backend /api/auth/google/config endpoint is the primary source; this serves as an optional fallback.
    if (!window.GOOGLE_CLIENT_ID) {
        window.GOOGLE_CLIENT_ID = "";
    }

    window.getApiUrl = function (path) {
        var base = window.FOOD_COURT_API_BASE.replace(/\/+$/, "");
        var cleanPath = (path || "").replace(/^\/+/, "");
        return base + "/" + cleanPath;
    };
})();
