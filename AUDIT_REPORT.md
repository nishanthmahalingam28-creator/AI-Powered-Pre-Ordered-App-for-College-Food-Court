# Comprehensive Health Audit & Architecture Report
**Project:** AI-Powered Pre-Ordered App for College Food Court  
**Date:** September 17, 2026  
**Status:** Audit Complete — Awaiting Approval Before Remediation  

---

## 1. Executive Summary

A comprehensive, non-destructive health and architecture audit was conducted across the entire **AI-Powered Pre-Ordered App for College Food Court** codebase, inspecting `frontend/`, `frontend/pages/`, `backend/`, `backend/routes/`, `backend/services/`, `backend/ai/`, `database/`, `tests/`, `Dockerfile`, `docker-compose.yml`, `nginx/`, `requirements.txt`, `.env.example`, and production deployment configurations.

### Key Audit Highlights:
- **Total Issues Identified:** 34 confirmed issues across 20 audit dimensions.
- **Critical Severity Issues:** 7 (Automated test collection failures from missing `bcrypt`, missing `config.js` in admin/vendor/preorder pages causing broken API calls, hardcoded `http://localhost:5000` in password reset emails, Production cookie secure flag override from `.env`, active database credentials committed in `.env`, Google Identity Services blocked by Nginx CSP, and Nginx rate limiting mismatch).
- **High Severity Issues:** 11 (Hardcoded `localhost:5000` in budgets, hardcoded Render fallback URL bypassing local/Docker Nginx API proxies, missing dependencies in `backend/requirements.txt`, missing connection pooling in `db.py`, vendor error redirects to customer login, etc.).
- **Medium Severity Issues:** 10 (Redirection stub redundancies, duplicate index files, unverified Google audience when client ID is missing, undeclared `requests` dependency, etc.).
- **Low Severity Issues:** 6 (Missing `.render.yaml`, deprecated MySQL authentication plugin parameter, documentation discrepancies).

> [!IMPORTANT]
> **No source code has been modified.** In accordance with instructions, this report documents all findings and identifies which frontend files are actively used by the deployment architecture so that legitimate features and files are preserved.

---

## 2. Frontend File Inventory & Deployment Usage Matrix

The application contains files in three distinct directory tiers:
1. **Workspace Root (`./`)**: Contains legacy/fallback files (`index.html`, `analytics.html`, `assistant.html`, `forgot-password.html`, `reset-password.html`).
2. **Frontend Root (`frontend/`)**: The authoritative document root (`/var/www/foodcourt` in Nginx and `--directory frontend` in local servers).
3. **Pages Subdirectories (`frontend/pages/*`)**: True functional application pages.

### Usage Matrix

| File Path | Status | Actually Used by Deployment? | Role / Purpose | Recommendation |
| :--- | :--- | :---: | :--- | :--- |
| `frontend/index.html` | **Active Core** | **YES** | Main public landing page, hero section, features, dynamic navbar/footer loader. | **PRESERVE** |
| `frontend/components/navbar.html` | **Active Core** | **YES** | Shared navigation bar with responsive layout and auth state awareness. | **PRESERVE** |
| `frontend/components/footer.html` | **Active Core** | **YES** | Shared footer component with mobile bottom tab navigation bar. | **PRESERVE** |
| `frontend/pages/auth/login.html` | **Active Core** | **YES** | Customer login portal (Student, Faculty, Guest). | **PRESERVE** |
| `frontend/pages/auth/signup.html` | **Active Core** | **YES** | Student/Customer registration portal with OTP verification. | **PRESERVE** |
| `frontend/pages/auth/faculty-login.html` | **Active Core** | **YES** | Specialized faculty login portal. | **PRESERVE** |
| `frontend/pages/auth/faculty-signup.html` | **Active Core** | **YES** | Specialized faculty registration portal. | **PRESERVE** |
| `frontend/pages/auth/guest-login.html` | **Active Core** | **YES** | Guest customer login portal. | **PRESERVE** |
| `frontend/pages/auth/guest-signup.html` | **Active Core** | **YES** | Guest customer registration portal. | **PRESERVE** |
| `frontend/pages/auth/forgot-password.html`| **Active Core** | **YES** | Password reset request form. | **PRESERVE** |
| `frontend/pages/auth/reset-password.html` | **Active Core** | **YES** | Password reset token verification & new password form. | **PRESERVE** |
| `frontend/pages/customer/dashboard.html` | **Active Core** | **YES** | Customer home hub, quick stats, active tickets, AI recommendations. | **PRESERVE** |
| `frontend/pages/customer/menu.html` | **Active Core** | **YES** | Food court interactive menu, stall filtering, cart management. | **PRESERVE** |
| `frontend/pages/customer/preorder.html` | **Active Core** | **YES** | Pre-order checkout, payment mode selection, Razorpay modal, OTP token. | **PRESERVE** |
| `frontend/pages/customer/orders.html` | **Active Core** | **YES** | Order history, live progress tracker, itemized tax invoice receipt. | **PRESERVE** |
| `frontend/pages/customer/profile.html` | **Active Core** | **YES** | Customer personal profile management and password change. | **PRESERVE** |
| `frontend/pages/customer/analytics.html` | **Active Core** | **YES** | Financial analytics and dining expense intelligence charts. | **PRESERVE** |
| `frontend/pages/customer/assistant.html` | **Active Core** | **YES** | AI chat assistant interface for food court dining and budgeting advice. | **PRESERVE** |
| `frontend/pages/customer/budgets.html` | **Active Core** | **YES** | Budget limits and financial savings goals management. | **PRESERVE** |
| `frontend/pages/customer/expenses.html` | **Active Core** | **YES** | Meal expense tracking and categorization. | **PRESERVE** |
| `frontend/pages/customer/income.html` | **Active Core** | **YES** | Allowance and dining balance record keeper. | **PRESERVE** |
| `frontend/pages/vendor/login.html` | **Active Core** | **YES** | Stall merchant login terminal. | **PRESERVE** |
| `frontend/pages/vendor/dashboard.html` | **Active Core** | **YES** | Stall kitchen terminal, incoming tickets, OTP verification, inventory. | **PRESERVE** |
| `frontend/pages/admin/login.html` | **Active Core** | **YES** | Campus administrator login portal. | **PRESERVE** |
| `frontend/pages/admin/dashboard.html` | **Active Core** | **YES** | Campus superadmin control hub, stall assignments, revenue analytics. | **PRESERVE** |
| `frontend/pages/public/about.html` | **Active Core** | **YES** | Institutional background and smart food court overview. | **PRESERVE** |
| `frontend/pages/public/contact.html` | **Active Core** | **YES** | Help desk and contact channels. | **PRESERVE** |
| `frontend/pages/public/how-it-works.html` | **Active Core** | **YES** | Process flow explanation for pre-ordering and pickup. | **PRESERVE** |
| `frontend/pages/public/privacy.html` | **Active Core** | **YES** | Privacy policy for campus users. | **PRESERVE** |
| `frontend/pages/public/terms.html` | **Active Core** | **YES** | Food court service terms and dining regulations. | **PRESERVE** |
| `frontend/analytics.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `pages/customer/analytics.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/assistant.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `pages/customer/assistant.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/forgot-password.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `pages/auth/forgot-password.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/reset-password.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `pages/auth/reset-password.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/analytics.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `customer/analytics.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/assistant.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `customer/assistant.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/budgets.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `customer/budgets.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/expenses.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `customer/expenses.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/forgot-password.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `auth/forgot-password.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/goals.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `customer/budgets.html#goals-section`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/income.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `customer/income.html`. | **KEEP AS COMPATIBILITY STUB** |
| `frontend/pages/reset-password.html` | **Redirection Stub**| **NO** *(Fallback only)* | 15-line stub redirecting to `auth/reset-password.html`. | **KEEP AS COMPATIBILITY STUB** |
| `./index.html` (root) | **Duplicate File** | **NO** *(IDE fallback)* | Exact duplicate of `frontend/index.html`. Not served by Nginx or `python -m http.server 5500 --directory frontend`. | **PRESERVE FOR IDE LOCAL PREVIEWS** |
| `./analytics.html` (root) | **Duplicate Stub** | **NO** *(IDE fallback)* | Redirects to `frontend/pages/customer/analytics.html`. | **PRESERVE** |
| `./assistant.html` (root) | **Duplicate Stub** | **NO** *(IDE fallback)* | Redirects to `frontend/pages/customer/assistant.html`. | **PRESERVE** |
| `./forgot-password.html` (root) | **Duplicate Stub** | **NO** *(IDE fallback)* | Redirects to `frontend/pages/auth/forgot-password.html`. | **PRESERVE** |
| `./reset-password.html` (root) | **Duplicate Stub** | **NO** *(IDE fallback)* | Redirects to `frontend/pages/auth/reset-password.html`. | **PRESERVE** |

---

## 3. Comprehensive Audit Findings by Category

### Category 1: Duplicate Frontend Files & Redirection Stubs
- **Severity:** Medium
- **File(s):**
  - `./index.html` (Workspace Root) vs `frontend/index.html`
  - `./analytics.html`, `./assistant.html`, `./forgot-password.html`, `./reset-password.html`
  - `frontend/analytics.html`, `frontend/assistant.html`, `frontend/forgot-password.html`, `frontend/reset-password.html`
  - `frontend/pages/analytics.html`, `frontend/pages/assistant.html`, `frontend/pages/budgets.html`, `frontend/pages/expenses.html`, `frontend/pages/forgot-password.html`, `frontend/pages/goals.html`, `frontend/pages/income.html`, `frontend/pages/reset-password.html`
- **Component:** Frontend Root & Pages Navigation Structure
- **Problem:**
  There are 3 layers of files serving the same purpose:
  1. Root duplicate `index.html` is an exact SHA-256 copy of `frontend/index.html`.
  2. Four redirection stubs exist in workspace root pointing to `frontend/pages/...`.
  3. Four redirection stubs exist in `frontend/` pointing to `pages/...`.
  4. Eight redirection stubs exist in `frontend/pages/` pointing to `customer/...` and `auth/...`.
- **Why it is a problem:**
  Modifications made to `frontend/index.html` will diverge from `./index.html`. Developers previewing the site with live servers opened at the repo root vs `--directory frontend` get inconsistent paths.
- **Recommended fix:**
  Do NOT delete the stubs (they maintain backward compatibility if external bookmarks or automated scripts hit legacy URLs). Update root `index.html` documentation or keep it in sync, and ensure all internal links throughout the app point directly to canonical destinations (`pages/customer/...` and `pages/auth/...`).

---

### Category 2: Broken or Incorrect Links
- **Severity:** Critical
- **File:** `backend/routes/auth.py`
- **Function/Component:** `forgot_password()` (Line 727)
- **Problem:**
  The generated password reset link is constructed as:
  ```python
  base_url = cfg["app_url"]
  reset_url = f"{base_url}/frontend/pages/auth/reset-password.html?token={raw_token}"
  ```
  Where `cfg["app_url"]` defaults to `http://localhost:5000`.
- **Why it is a problem:**
  1. `base_url` points to port 5000 (the Flask API WSGI server), which does not serve static HTML files and returns HTTP 404.
  2. The path includes `/frontend/`, whereas the web server (Nginx or local HTTP server) serves `frontend/` as the document root `/`, making the real path `/pages/auth/reset-password.html`.
  3. In production, users receiving password reset emails receive a broken link pointing to `localhost:5000` instead of the public domain.
- **Recommended fix:**
  Change URL construction to derive from frontend origin:
  ```python
  frontend_base = os.getenv("FRONTEND_URL") or os.getenv("APP_URL") or request.host_url.rstrip("/")
  reset_url = f"{frontend_base}/pages/auth/reset-password.html?token={raw_token}"
  ```

---

- **Severity:** Medium
- **File:** `frontend/js/core/dashboard.js`
- **Function/Component:** `initShopProfile()` (Lines 21, 27)
- **Problem:**
  When vendor authentication fails on `/pages/vendor/dashboard.html`, the script executes:
  ```javascript
  window.location.href = '../auth/login.html';
  ```
- **Why it is a problem:**
  `../auth/login.html` routes the vendor to the Student/Customer login page rather than the Vendor Terminal login page (`login.html` in the same vendor folder).
- **Recommended fix:**
  Redirect to `'login.html'` (or `'../vendor/login.html'`).

---

### Category 3: Frontend API URL Problems
- **Severity:** Critical
- **File(s):**
  - `frontend/pages/admin/login.html`
  - `frontend/pages/admin/dashboard.html`
  - `frontend/pages/vendor/login.html`
  - `frontend/pages/vendor/dashboard.html`
  - `frontend/pages/customer/preorder.html`
  - `frontend/pages/customer/orders.html`
  - `frontend/pages/customer/profile.html`
  - `frontend/pages/auth/faculty-login.html`
- **Component:** HTML Script Imports & Global API Variable Resolution
- **Problem:**
  None of these 8 active pages include `<script src="../../js/config.js"></script>`.
  In `vendor/login.js`, `vendor/dashboard.js`, `admin/login.js`, `admin/dashboard.js`, `orders.js`, and `profile.js`, line 1 defines:
  ```javascript
  const API_BASE_URL = window.FOOD_COURT_API_BASE;
  ```
  Because `config.js` is never loaded, `window.FOOD_COURT_API_BASE` is `undefined`.
  In `preorder.js`, `API_BASE_URL` is referenced directly at line 16 without even being declared, throwing an uncaught `ReferenceError: API_BASE_URL is not defined`.
- **Why it is a problem:**
  1. Vendor login makes HTTP requests to `undefined/auth/vendor/login` (fails).
  2. Admin login makes HTTP requests to `undefined/auth/admin/login` (fails).
  3. Pre-order checkout crashes immediately; the cart cannot be retrieved.
  4. Order history requests `undefined/orders/my-orders` (fails).
  5. Admin and Vendor dashboards enter infinite redirect loops back to login pages because `/api/auth/me` cannot be reached.
- **Recommended fix:**
  1. Add `<script src="../../js/config.js"></script>` to the `<head>` of all pages before page-specific scripts.
  2. In all scripts, add defensive fallback resolution:
     ```javascript
     const API_BASE_URL = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
     ```

---

### Category 4: Localhost URLs That Should Not Be Used in Production
- **Severity:** High
- **File:** `frontend/js/customer/budgets.js`
- **Function/Component:** `getApiUrl()` (Line 42)
- **Problem:**
  Line 42 hardcodes:
  ```javascript
  return `http://127.0.0.1:5000${path}`;
  ```
- **Why it is a problem:**
  It completely bypasses `window.FOOD_COURT_API_BASE` and `window.getApiUrl`. In production, client browsers query `127.0.0.1:5000` on the end-user's local workstation, causing complete failure of the budgets and goals module.
- **Recommended fix:**
  Replace line 42 with:
  ```javascript
  const base = window.FOOD_COURT_API_BASE || '/api';
  return `${base.replace(/\/+$/, '')}${path}`;
  ```

---

- **Severity:** High
- **File:** `frontend/js/config.js`
- **Function/Component:** Dynamic Base Resolution (Lines 8-22)
- **Problem:**
  `isLocalDev` is detected using:
  ```javascript
  var isLocalDev = (
      origin.indexOf(":5500") !== -1 ||
      origin.indexOf(":3000") !== -1 ||
      origin.indexOf(":8080") !== -1 ||
      window.location.protocol === "file:"
  );
  if (isLocalDev) {
      window.FOOD_COURT_API_BASE = "http://127.0.0.1:5000/api";
  } else {
      window.FOOD_COURT_API_BASE = "https://college-food-court-api.onrender.com/api";
  }
  ```
- **Why it is a problem:**
  When testing locally with Docker Compose or accessing via `http://localhost/` or `http://127.0.0.1/` (port 80) or on the college domain (`http://foodcourt.kpriet.ac.in`), `isLocalDev` evaluates to `false`. The frontend then routes all API requests to the remote Render server `college-food-court-api.onrender.com`, bypassing the local/Docker backend.
- **Recommended fix:**
  Use same-origin relative `/api` when deployed behind a reverse proxy (like Nginx), or support explicit runtime environment configuration:
  ```javascript
  if (isLocalDev) {
      window.FOOD_COURT_API_BASE = "http://127.0.0.1:5000/api";
  } else {
      // Default to same-origin /api for reverse proxy deployments (Docker/Nginx/Domain)
      window.FOOD_COURT_API_BASE = origin.indexOf("onrender.com") !== -1
          ? "https://college-food-court-api.onrender.com/api"
          : origin + "/api";
  }
  ```

---

### Category 5: CORS Problems
- **Severity:** High
- **File:** `backend/app.py` & `backend/config.py`
- **Function/Component:** CORS Allowed Origins Handling (Lines 73-86)
- **Problem:**
  In `backend/app.py`:
  ```python
  if raw_origins:
      allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
  elif is_development:
      allowed_origins = ["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000"]
  else:
      logger.warning("CORS_ORIGINS not specified in production. Cross-origin access restricted.")
      allowed_origins = []
  ```
- **Why it is a problem:**
  If the application is deployed in production without `CORS_ORIGINS` explicitly defined in environment variables, `allowed_origins` defaults to an empty list `[]`. Any decoupled frontend deployment (e.g. Render Static, Vercel, or GitHub Pages) fails all API calls on CORS preflight checks.
- **Recommended fix:**
  Ensure `.env.example` explicitly specifies production origin templates, and provide a clear startup validation or fallback when `FRONTEND_URL` is defined.

---

### Category 6: Authentication & Session Problems
- **Severity:** Critical
- **File:** `backend/config.py` & `tests/test_phase12_remediation.py`
- **Function/Component:** `ProductionConfig` Class Definition (Line 107)
- **Problem:**
  In `backend/config.py`:
  ```python
  class ProductionConfig(BaseConfig):
      ...
      SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1").lower() in ("1", "true")
  ```
  Because `load_dotenv()` runs at module import time (line 16), and local `.env` has `COOKIE_SECURE=0`, `ProductionConfig.SESSION_COOKIE_SECURE` evaluates to `False` at the class level when `config.py` is imported.
- **Why it is a problem:**
  1. `test_phase12_remediation.py` test cases `test_07` and `test_15` fail:
     `AssertionError: False is not true` on `ProductionConfig.SESSION_COOKIE_SECURE`.
  2. Any production container that imports configuration where `.env` has `COOKIE_SECURE=0` will transmit session cookies over unencrypted HTTP.
- **Recommended fix:**
  In `ProductionConfig`, enforce:
  ```python
  SESSION_COOKIE_SECURE = True  # Strict production invariant
  ```
  Or re-read environment dynamically in `__init__()`.

---

- **Severity:** High
- **File:** `backend/app.py` & `backend/config.py`
- **Function/Component:** Cross-Site Cookie Delivery (`SameSite="Lax"`)
- **Problem:**
  `SESSION_COOKIE_SAMESITE = "Lax"`. When the frontend is hosted on a separate domain from the backend (e.g. frontend on `kpriet.ac.in` and API on `onrender.com`), browsers treat API fetch requests as cross-site.
- **Why it is a problem:**
  Browsers will not send `SameSite=Lax` cookies on cross-origin AJAX/fetch requests. Every authenticated request returns HTTP 401.
- **Recommended fix:**
  Deploy frontend and backend under the same domain (e.g. via Nginx reverse proxy at `/api`) or configure `SameSite="None"` with `Secure=True` for cross-domain deployments.

---

### Category 7 & 8: Database Configuration Problems & SQLite vs MySQL
- **Severity:** High
- **File:** `backend/db.py`
- **Function/Component:** `DB.query()`, `DB.execute()`, `DB.transaction()`
- **Problem:**
  There is **no connection pool**. Every call to `DB.query()` and `DB.execute()` calls `pymysql.connect(...)` directly, performs the query, and closes the connection.
- **Why it is a problem:**
  1. In a multi-user campus food court environment, opening a new TCP + TLS handshake for every query causes massive latency (50-200ms per SQL call).
  2. Under peak lunch pre-order spikes, this rapidly exceeds MySQL's `max_connections` limit, causing `Too many connections` exceptions and dropped orders.
- **Recommended fix:**
  Implement a thread-safe connection pool using `dbutils.pooled_db.PooledDB` or a lightweight connection pooler for PyMySQL.

---

- **Severity:** Critical
- **File:** `.env` (Workspace Root)
- **Function/Component:** Database Connection String (Lines 7-11)
- **Problem:**
  The local `.env` file contains live, plaintext Aiven Cloud database credentials:
  ```env
  DB_HOST=college-foodcourt-db-college-food-court.b.aivencloud.com
  DB_PORT=18736
  DB_USER=avnadmin
  DB_PASSWORD=AVNS_VOptnq0HCGn2qnbhWNh
  DB_NAME=food_court_db
  ```
- **Why it is a problem:**
  Direct database credentials to a cloud MySQL instance are stored in the local file system. If pushed or shared, the entire database is vulnerable to unauthorized exfiltration or deletion.
- **Recommended fix:**
  Sanitize `.env` with placeholder values and immediately rotate the password in Aiven Cloud console.

---

### Category 9: Payment Configuration Problems
- **Severity:** High
- **File:** `backend/services/payment_provider.py` & `.env`
- **Function/Component:** `RazorpayProvider.__init__()` & Environment Configuration
- **Problem:**
  `backend/services/payment_provider.py` enforces fail-fast in production mode:
  ```python
  if self.is_prod:
      if self.key_id.startswith("rzp_test_"):
          raise RuntimeError("FATAL: Production mode detected but test RAZORPAY_KEY_ID was provided.")
  ```
  In `docker-compose.yml`, `RAZORPAY_KEY_ID: ${RAZORPAY_KEY_ID:?RAZORPAY_KEY_ID is required}`.
  However, in `.env`, `RAZORPAY_KEY_ID=`, `RAZORPAY_KEY_SECRET=`, and `RAZORPAY_WEBHOOK_SECRET=` are empty.
- **Why it is a problem:**
  Attempting to run `docker compose up` or boot `ProductionConfig` crashes the container immediately upon launch.
- **Recommended fix:**
  Ensure `.env.example` documents the required Razorpay keys, and provide explicit guidance for test vs live mode in deployment documentation.

---

### Category 10: Google Authentication Problems
- **Severity:** Critical
- **File:** `nginx/foodcourt.conf`
- **Function/Component:** Content Security Policy (Line 64)
- **Problem:**
  `nginx/foodcourt.conf` defines:
  ```nginx
  add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://checkout.razorpay.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com; frame-src https://api.razorpay.com;" always;
  ```
- **Why it is a problem:**
  Google Identity Services (GIS) requires loading scripts from `https://accounts.google.com/gsi/client`, iframes from `https://accounts.google.com`, and network connections to `https://accounts.google.com`. Because these are omitted from CSP, modern browsers block Google Sign-In with a CSP violation.
- **Recommended fix:**
  Update CSP in `nginx/foodcourt.conf`:
  ```nginx
  script-src 'self' 'unsafe-inline' https://checkout.razorpay.com https://accounts.google.com/gsi/client;
  frame-src 'self' https://api.razorpay.com https://accounts.google.com;
  connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com https://accounts.google.com;
  ```

---

- **Severity:** High
- **File:** `backend/services/google_auth.py`
- **Function/Component:** `GoogleAuthService.verify_token()` (Lines 95, 128)
- **Problem:**
  If `GOOGLE_CLIENT_ID` is empty in `.env`, the token verification logic falls back to `audience=None` and skips audience verification.
- **Why it is a problem:**
  Any valid Google ID token generated for any application on the internet would be cryptographically verified as authentic and granted access to create accounts.
- **Recommended fix:**
  Require `GOOGLE_CLIENT_ID` to be configured whenever Google authentication is enabled:
  ```python
  if not client_id and not is_dev:
      raise GoogleTokenVerificationError("Google authentication is disabled: GOOGLE_CLIENT_ID is not configured.")
  ```

---

### Category 11: Password Reset Problems
- **Severity:** Critical
- **File:** `backend/routes/auth.py`
- **Function/Component:** `forgot_password()` (Line 727)
- **Problem:**
  (Documented in Category 2) Reset links contain `http://localhost:5000/frontend/pages/auth/reset-password.html?token=...`.
- **Why it is a problem:**
  Users clicking the email link cannot reset passwords in production.
- **Recommended fix:**
  Construct the URL using the frontend host and correct path `/pages/auth/reset-password.html`.

---

### Category 12: Order & Cart Problems
- **Severity:** Critical
- **File:** `frontend/pages/customer/preorder.html` & `frontend/js/customer/preorder.js`
- **Function/Component:** `fetchCartAndRender()` (Line 16)
- **Problem:**
  `preorder.html` fails to import `config.js` and `preorder.js` does not declare `API_BASE_URL`.
- **Why it is a problem:**
  The checkout page throws `Uncaught ReferenceError: API_BASE_URL is not defined`, completely preventing customers from viewing their cart, calculating totals, or placing orders.
- **Recommended fix:**
  Import `config.js` in `preorder.html` and define `const API_BASE_URL = window.FOOD_COURT_API_BASE || '/api';` at the top of `preorder.js`.

---

- **Severity:** Critical
- **File:** `frontend/pages/customer/orders.html` & `frontend/js/customer/orders.js`
- **Function/Component:** `loadCustomerOrders()` (Line 109)
- **Problem:**
  `orders.html` fails to import `config.js`. `orders.js` has `const API_BASE_URL = window.FOOD_COURT_API_BASE;`, which is `undefined`.
- **Why it is a problem:**
  Orders history queries `undefined/orders/my-orders`, showing a blank list and preventing customers from retrieving their pickup OTP tokens.
- **Recommended fix:**
  Import `config.js` in `orders.html`.

---

### Category 13: Vendor Authorization Problems
- **Severity:** Critical
- **File:** `frontend/pages/vendor/login.html` & `frontend/pages/vendor/dashboard.html`
- **Function/Component:** Vendor Terminal Routing & Session Initialization
- **Problem:**
  Neither page imports `config.js`.
  1. `vendor/login.js` sends credentials to `undefined/auth/vendor/login`.
  2. `vendor/dashboard.html` calls `undefined/auth/me`, fails, clears the session, and redirects to customer login.
- **Why it is a problem:**
  Stall owners cannot log into their terminals to accept orders or verify customer pickup OTPs.
- **Recommended fix:**
  Add `<script src="../../js/config.js"></script>` to both pages and ensure proper error handling.

---

### Category 14: Admin Authorization Problems
- **Severity:** Critical
- **File:** `frontend/pages/admin/login.html` & `frontend/pages/admin/dashboard.html`
- **Function/Component:** Admin Control Hub Routing
- **Problem:**
  Neither page imports `config.js`.
  1. `admin/login.js` sends credentials to `undefined/auth/admin/login`.
  2. `admin/dashboard.html` calls `undefined/auth/me`, fails, and redirects to `login.html` in an infinite loop.
- **Why it is a problem:**
  Administrators are completely locked out of the Admin Control Hub.
- **Recommended fix:**
  Add `<script src="../../js/config.js"></script>` to both admin HTML pages.

---

### Category 15: AI / Recommendation API Problems
- **Severity:** Medium
- **File:** `backend/services/ai_assistant.py` & `.env.example`
- **Function/Component:** `AIAssistantService` External LLM Integration
- **Problem:**
  Line 326 calls:
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}`.
  However, `GEMINI_API_KEY` is not documented in `.env.example`.
- **Why it is a problem:**
  Deployers have no documentation explaining how to enable the Gemini LLM assistant, falling back to rule-based heuristics silently.
- **Recommended fix:**
  Add `GEMINI_API_KEY=` to `.env.example` with clear documentation.

---

### Category 16: Notification Problems
- **Severity:** High
- **File:** `frontend/pages/vendor/dashboard.html` & `frontend/js/core/dashboard.js`
- **Function/Component:** Kitchen Alerts Polling (`initVendorNotifications()`)
- **Problem:**
  Because `vendor/dashboard.html` lacks `config.js`, kitchen alert polling against `${API_BASE_URL}/notifications` fails.
- **Why it is a problem:**
  Vendors do not receive real-time kitchen audio/visual alerts when new orders are paid and placed.
- **Recommended fix:**
  Include `config.js` in `vendor/dashboard.html`.

---

### Category 17: Missing Dependencies
- **Severity:** Critical
- **File(s):**
  - `requirements.txt`
  - `backend/requirements.txt`
  - Active Python Virtual Environment (`venv`)
- **Problem:**
  1. `bcrypt` is listed in `requirements.txt` (`bcrypt>=4.0.0`) but **is not installed** in either the global Python environment or the project `venv`.
  2. `google-auth` is listed in `requirements.txt` but **is not installed** in either environment.
  3. `pytest` is not declared in `requirements.txt` or `backend/requirements.txt` and is missing from `venv`.
  4. `backend/requirements.txt` is missing 6 essential dependencies that exist in root `requirements.txt`: `scikit-learn`, `pandas`, `numpy`, `gunicorn`, `cryptography`, and `razorpay`.
  5. `requests` is imported directly in `backend/services/ai_assistant.py` and `backend/services/google_auth.py`, but is omitted from `requirements.txt`.
- **Why it is a problem:**
  1. Every test file importing `backend/security.py` fails on collection (`ModuleNotFoundError: No module named 'bcrypt'`).
  2. Running the server or tests in the project virtual environment fails.
  3. Deploying using `backend/requirements.txt` fails because AI models and payment gateways cannot load.
- **Recommended fix:**
  1. Install `bcrypt`, `google-auth`, and `pytest` into the environment.
  2. Add `requests` and `pytest` to `requirements.txt`.
  3. Synchronize `backend/requirements.txt` to include all runtime dependencies.

---

### Category 18: Deployment Configuration Problems
- **Severity:** High
- **File:** `nginx/nginx.conf` & `nginx/foodcourt.conf`
- **Function/Component:** Rate Limiting Locations (Lines 42-67)
- **Problem:**
  Nginx defines:
  ```nginx
  location /api/auth/login {
      limit_req zone=auth_limit burst=3 nodelay;
      ...
  }
  location /api/auth/register {
      limit_req zone=auth_limit burst=3 nodelay;
      ...
  }
  ```
  However, the backend Flask application has **no routes** for `/api/auth/login` or `/api/auth/register`.
  The actual routes are:
  - `/api/auth/customer/login`
  - `/api/auth/vendor/login`
  - `/api/auth/admin/login`
  - `/api/auth/customer/signup`
- **Why it is a problem:**
  Because Nginx evaluates prefix matches, requests to `/api/auth/customer/login` and `/api/auth/customer/signup` do NOT match `/api/auth/login` or `/api/auth/register`. They fall through to `location /api/` which has general rate limiting (`30r/s`), completely bypassing the strict 5 requests/minute brute-force protection.
- **Recommended fix:**
  Update Nginx location blocks to match the actual route patterns:
  ```nginx
  location ~ ^/api/auth/(customer/login|vendor/login|admin/login|customer/signup) {
      limit_req zone=auth_limit burst=3 nodelay;
      ...
  }
  ```

---

### Category 19: Security Vulnerabilities
- **Severity:** High
- **File:** `backend/security.py`
- **Function/Component:** Module Import
- **Problem:**
  Direct import `import bcrypt` has no fallback or defensive handling.
- **Why it is a problem:**
  When `bcrypt` is missing or fails to link native C extensions, the entire application fails to boot, crashing all API endpoints rather than providing a clean diagnostic or fallback.
- **Recommended fix:**
  Ensure `bcrypt` is installed, and provide a graceful fallback or descriptive diagnostic exception on startup.

---

### Category 20: Failing Automated Tests
- **Severity:** Critical
- **File(s):**
  - `tests/test_phase12_remediation.py`
  - 22 other test suites in `tests/`
- **Problem:**
  1. `test_phase12_remediation.py`:
     - `test_07_production_config_succeeds_with_valid_production_secrets` -> **FAILED** (`AssertionError: False is not true` for `SESSION_COOKIE_SECURE`).
     - `test_15_cookie_flags_security_defaults` -> **FAILED** (`AssertionError: False is not true` for `ProductionConfig.SESSION_COOKIE_SECURE`).
  2. 22 test suites fail collection immediately:
     `ModuleNotFoundError: No module named 'bcrypt'`
- **Why it is a problem:**
  The CI pipeline and automated regression safety net are completely non-functional.
- **Recommended fix:**
  1. Install `bcrypt`, `google-auth`, and `pytest` in the Python virtual environment.
  2. Fix `ProductionConfig.SESSION_COOKIE_SECURE` in `backend/config.py` so that it is strictly `True` in production.
  3. Re-run the full automated test suite to verify 100% test pass rate.

---

## 4. Prioritized Remediation Roadmap

Once approved, the remediation plan will be executed strictly in the following sequence without removing features or rewriting architecture:

### Phase 1: Environment & Dependency Remediation
1. Install missing runtime dependencies (`bcrypt`, `google-auth`, `requests`, `pytest`) into `venv`.
2. Synchronize `backend/requirements.txt` and root `requirements.txt`.
3. Fix `ProductionConfig.SESSION_COOKIE_SECURE = True` in `backend/config.py`.
4. Re-run `test_phase12_remediation.py` to confirm 15/15 tests passing.

### Phase 2: Frontend HTML & API URL Normalization
1. Add `<script src="../../js/config.js"></script>` to:
   - `frontend/pages/admin/login.html`
   - `frontend/pages/admin/dashboard.html`
   - `frontend/pages/vendor/login.html`
   - `frontend/pages/vendor/dashboard.html`
   - `frontend/pages/customer/preorder.html`
   - `frontend/pages/customer/orders.html`
   - `frontend/pages/customer/profile.html`
   - `frontend/pages/auth/faculty-login.html`
2. Add defensive fallbacks for `API_BASE_URL` in all frontend scripts (`preorder.js`, `orders.js`, `profile.js`, `dashboard.js`, `login.js`).
3. Replace hardcoded `http://127.0.0.1:5000` in `frontend/js/customer/budgets.js` with dynamic resolution.
4. Update `frontend/js/config.js` to correctly support both reverse-proxy `/api` (Docker/Nginx) and decoupled configurations.

### Phase 3: Authentication, Links & Security Hardening
1. Fix password reset link in `backend/routes/auth.py` (Line 727) to point to the frontend host and canonical path `/pages/auth/reset-password.html`.
2. Fix vendor dashboard redirect in `frontend/js/core/dashboard.js` to redirect to `login.html` (vendor login).
3. Update Nginx Content-Security-Policy in `nginx/foodcourt.conf` to include Google Identity Services (`https://accounts.google.com`).
4. Update Nginx rate-limiting locations in `nginx.conf` and `foodcourt.conf` to protect actual login endpoints (`/api/auth/customer/login`, etc.).
5. Require `GOOGLE_CLIENT_ID` to be configured when Google OAuth is enabled.
6. Sanitize database credentials in `.env` and document all required variables in `.env.example`.

### Phase 4: Full Automated Regression Verification
1. Run `pytest tests/` across all 34 test files.
2. Confirm 100% test pass rate across all functional, security, and load suites.
3. Validate end-to-end user journeys for Student, Faculty, Guest, Vendor, and Admin.

---

> [!NOTE]
> **Audit status:** Ready for user review. Awaiting approval before applying file modifications.
