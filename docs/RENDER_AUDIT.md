# Render Production Deployment Audit

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Audit Target**: Cloud Platform Deployment on [Render](https://render.com)  
**Date**: September 2026  
**Status**: Comprehensive Pre-Deployment Audit  

---

## 1. Executive Summary

This audit evaluates the readiness of the **AI-Powered College Food Court** application for production deployment on Render. The application comprises a high-performance Python/Flask backend (with ACID transactions, RBAC, Razorpay payments, and Gemini AI financial intelligence) and a responsive Vanilla JS/Tailwind CSS frontend.

### Primary Deployment Architectural Decision
The application can be deployed to Render via two architectural patterns:

| Architecture | Frontend | Backend | Verdict |
| :--- | :--- | :--- | :--- |
| **Pattern A: Two-Service Architecture (Recommended for Render)** | Render **Static Site** (serves `frontend/`) | Render **Web Service** (Python / Gunicorn) | **Recommended**: Zero-cost static CDN caching, global edge distribution, decoupled scalability. Requires careful CORS, cookie, and API URL alignment. |
| **Pattern B: Single Unified Web Service** | Served by Flask via static routes or Nginx Docker container | Render **Web Service** (Docker) | Eliminates cross-origin CORS and third-party cookie issues, but requires modifying Flask routes or running a custom Docker container with Nginx reverse proxy. |

---

## 2. Core Checklist & Configuration Audit Findings

### 2.1. PORT Handling
* **Render Invariant**: Render dynamically provisions a port per container and injects it into the environment variable `$PORT` (typically `10000`). Web services must bind to `0.0.0.0:$PORT`.
* **Current Code State**:
  - `gunicorn.conf.py`: Line 9 dynamically reads `bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"`. **Compliant.**
  - `backend/app.py`: Line 280 executes `app.run(host="127.0.0.1", port=port, debug=debug_mode)`.
* **Critical Risk**: If an operator starts the application using `python app.py` instead of Gunicorn, the server binds to `127.0.0.1` (localhost only). Render's port scanner will fail to reach the application, resulting in a **Deploy Failed: Port scan timeout** error after 10 minutes.
* **Remediation**: Always use Gunicorn in Render with `0.0.0.0:$PORT` binding.

---

### 2.2. Gunicorn Start Command & Entry Point
* **WSGI Callable**: Located at `backend/app.py` with application instance `app`.
* **Current Configuration**:
  - Configuration file: `gunicorn.conf.py` (located in workspace root).
  - WSGI app: `app:app` (relative to `backend/`).
* **Correct Render Web Service Commands**:
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**:
    ```bash
    gunicorn -c gunicorn.conf.py --chdir backend app:app
    ```
    *Alternative (explicit CLI flags without config file)*:
    ```bash
    gunicorn --chdir backend -w 4 -k gthread --threads 2 -b 0.0.0.0:$PORT app:app
    ```
* **Critical Risk**: Running `gunicorn app:app` without `--chdir backend` will fail with `ModuleNotFoundError: No module named 'app'` because `app.py` is inside `backend/`.

---

### 2.3. Flask Application Entry Point & Pre-Boot Enforcements
* **Strict Production Invariants**: When `FLASK_ENV=production`, `backend/app.py` and `backend/config.py` enforce strict fail-fast validation:
  1. `SECRET_KEY`: Must be defined in the environment, must be >= 16 characters, and must not start with `dev-` or contain `change-this`.
  2. `DATABASE_URL` / `DB_PASSWORD`: Strictly required; SQLite fallback is prohibited in production.
  3. `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`: Strictly required in `ProductionConfig`. Must not start with `rzp_test_` or contain placeholder strings (`YourKey`).
* **Critical Risk**: If any of these environment variables are missing on Render, the backend container will crash during boot with `RuntimeError: FATAL: ...`.

---

### 2.4. Frontend Serving
* **Current Code State**:
  - `backend/app.py` is a pure REST API. It only registers `/api/*` routes and a JSON status endpoint at `/`. It does **not** serve static HTML files.
  - `Dockerfile` copies only `backend/` and `database/`. `frontend/` is omitted from the backend Docker image.
* **Render Deployment Requirement**:
  - In a Two-Service Render setup, create a separate **Static Site** for the frontend:
    - **Root Directory**: `frontend`
    - **Build Command**: *(leave blank)*
    - **Publish Directory**: `.` (or `frontend` if Root Directory is repo root)

---

### 2.5. Backend API URL Configuration (`frontend/js/config.js`)
* **Current Code State** ([frontend/js/config.js](file:///d:/Downloads/AI-Powered-Pre-Ordered-App-for-College-Food-Court/frontend/js/config.js#L19-L21)):
  ```javascript
  if (isLocalDev) {
      window.FOOD_COURT_API_BASE = (origin.indexOf(":5000") !== -1)
          ? origin + "/api"
          : "http://127.0.0.1:5000/api";
  } else {
      window.FOOD_COURT_API_BASE = "https://college-food-court-api.onrender.com/api";
  }
  ```
* **Critical Failure Mode (High)**:
  - If the backend Render service is named anything other than `college-food-court-api`, or if the user attaches a custom domain (e.g. `https://api.foodcourt.kpriet.ac.in`), **the frontend will load, but every API call will fail with `ERR_NAME_NOT_RESOLVED` or 404**.
* **Critical Failure Mode (Missing Script Tags)**:
  An audit revealed that **8 core HTML pages do not load `config.js`** in their `<head>` or `<body>`:
  1. `frontend/pages/customer/orders.html`
  2. `frontend/pages/customer/preorder.html`
  3. `frontend/pages/customer/profile.html`
  4. `frontend/pages/vendor/login.html`
  5. `frontend/pages/vendor/dashboard.html`
  6. `frontend/pages/admin/login.html`
  7. `frontend/pages/admin/dashboard.html`
  8. `frontend/pages/auth/faculty-login.html`
  
  On these 8 pages, `window.FOOD_COURT_API_BASE` is `undefined`. Consequently, requests to `${API_BASE_URL}/orders` or `${API_BASE_URL}/cart` evaluate to `/pages/customer/undefined/orders`, returning **404 Not Found**.

---

### 2.6. CORS Origins Configuration (`CORS_ORIGINS`)
* **Current Code State** ([backend/app.py](file:///d:/Downloads/AI-Powered-Pre-Ordered-App-for-College-Food-Court/backend/app.py#L75-L88)):
  ```python
  raw_origins = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_ORIGINS")
  if raw_origins:
      allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
  elif is_development:
      allowed_origins = ["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000"]
  else:
      logger.warning("CORS_ORIGINS not specified in production. Cross-origin access restricted.")
      allowed_origins = []
  ```
* **Critical Failure Mode**:
  - In production (`FLASK_ENV=production`), if `CORS_ORIGINS` is not explicitly set in the Render Web Service environment variables, `allowed_origins` defaults to `[]`.
  - Setting `CORS_ORIGINS=*` will be rejected at runtime by line 86 because credentials (`supports_credentials=True`) cannot be paired with wildcards under the W3C CORS specification.
  - Setting `CORS_ORIGINS=https://my-frontend.onrender.com/` (with trailing slash) will fail because browsers send `Origin: https://my-frontend.onrender.com` (without slash).
  - **Symptom**: Frontend loads fine, but all API requests fail with:  
    `Access to fetch at 'https://...onrender.com/api/...' from origin 'https://...onrender.com' has been blocked by CORS policy`.

---

### 2.7. Session Cookie Security & The Render Cross-Site Cookie Trap (`SameSite` & `Secure`)
* **Current Code State** ([backend/app.py](file:///d:/Downloads/AI-Powered-Pre-Ordered-App-for-College-Food-Court/backend/app.py#L60-L72)):
  ```python
  app.config["SESSION_COOKIE_HTTPONLY"] = True
  app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
  app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "1").lower() in ("1", "true")
  ```
* **Critical Failure Mode (The Render Cross-Site Trap)**:
  - When frontend and backend are hosted on separate Render subdomains (e.g. `frontend-app.onrender.com` and `backend-api.onrender.com`):
  - Because `onrender.com` is in the **Public Suffix List**, browsers treat `frontend-app.onrender.com` and `backend-api.onrender.com` as **different sites (cross-site)**, not different subdomains of the same registrable domain.
  - Modern browsers (Chrome, Safari, Firefox, Edge) **strictly block cookies with `SameSite=Lax` on cross-site asynchronous `fetch()` requests**, even with `{ credentials: "include" }`.
  - **Symptom**: User logs in (`POST /api/auth/customer/login` succeeds with HTTP 200 and issues `Set-Cookie`), but the browser refuses to send the cookie on subsequent requests (`GET /api/customer/profile`, `GET /api/cart`, `POST /api/orders`). Every subsequent API call returns **401 Unauthorized**.
* **Remediation**:
  - When frontend and backend reside on separate `onrender.com` subdomains, the backend must set:
    ```python
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = True
    ```
  - Alternatively, host both frontend and backend under a common custom domain (e.g. `app.foodcourt.kpriet.ac.in` and `api.foodcourt.kpriet.ac.in`) with `SESSION_COOKIE_DOMAIN = ".foodcourt.kpriet.ac.in"`.

---

### 2.8. SECRET_KEY
* **Requirement**: High-entropy 32-byte or 64-character hex string.
* **Validation**:
  - Must not start with `dev-`.
  - Must not contain `change-this`.
  - Must be at least 16 characters.
* **Generation**: Run `python -c "import secrets; print(secrets.token_hex(32))"` and set as `SECRET_KEY` in Render.

---

### 2.9. DATABASE_URL / MySQL Settings
* **Current Code State** ([backend/db.py](file:///d:/Downloads/AI-Powered-Pre-Ordered-App-for-College-Food-Court/backend/db.py#L46-L65)):
  ```python
  db_url = os.getenv("DATABASE_URL")
  if db_url and db_url.startswith(("mysql://", "mysql+pymysql://")):
      # parse MySQL connection parameters
  ```
* **Critical Failure Mode (Render Managed DB Incompatibility)**:
  - Render provides native managed **PostgreSQL** databases, but **does not provide native managed MySQL**.
  - If a user creates a Render PostgreSQL database and attaches its `DATABASE_URL` (`postgres://...` or `postgresql://...`), `backend/db.py` will ignore it because the scheme is not `mysql://`.
  - The application then falls back to `DB_HOST=127.0.0.1:3306`, where no database is running on Render, causing immediate `DatabaseConnectionError`.
* **Remediation**: Use an external managed MySQL 8.0 provider (e.g. Aiven, PlanetScale, Railway, AWS RDS, DigitalOcean) and supply either a `mysql://...` URL or discrete `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` variables.

---

### 2.10. Razorpay Payment Gateway Variables
* **Current Code State**: In `ProductionConfig`, non-empty live Razorpay credentials are required.
* **Required Variables**:
  - `RAZORPAY_KEY_ID`: Live key (`rzp_live_...`).
  - `RAZORPAY_KEY_SECRET`: Live secret.
  - `RAZORPAY_WEBHOOK_SECRET`: Live webhook secret configured in Razorpay Dashboard.
* **Staging Note**: If deploying to Render for testing with sandbox credentials (`rzp_test_...`), set `FLASK_ENV=development` in Render to bypass the live-key enforcement while preserving all API functionality.

---

### 2.11. Google Identity Services (GIS) Variables
* **Required Variable**: `GOOGLE_CLIENT_ID` (set on the backend).
* **Google Cloud Console Requirement**:
  - In Google Cloud Console (`APIs & Services > Credentials > OAuth 2.0 Client IDs`), add the Render frontend URL to **Authorized JavaScript origins**:
    ```
    https://<your-frontend-service>.onrender.com
    ```
  - Failure to add this origin will cause the Google Sign-In prompt to fail with `idpiframe_initialization_failed` or `origin_mismatch`.

---

### 2.12. AI / Gemini Assistant Variables
* **Supported Variables**: `GEMINI_API_KEY` (or `AI_API_KEY`, `GOOGLE_AI_KEY`).
* **Behavior**:
  - If present and valid: Generates tailored Gemini LLM dining and financial advice.
  - If absent or invalid: Gracefully falls back to the deterministic food-court rule engine with zero hallucinations.

---

### 2.13. Static Assets & Direct URL Refresh Handling
* **SPA & Deep Linking on Render Static Sites**:
  - All navigation links in the application include `.html` (e.g. `pages/customer/dashboard.html`).
  - If a user navigates to `/pages/customer/dashboard.html` and refreshes, Render Static Site serves the file directly.
  - If Render **Clean URLs** are enabled without `.html` extensions, add a Rewrite Rule in Render Dashboard:
    - **Source**: `/*`
    - **Destination**: `/index.html`
    - **Action**: Rewrite (Fallback only)

---

## 3. Top Configurations Causing "Frontend Loads, API Fails"

The table below summarizes every failure scenario where a user sees the frontend website, but all interactions (login, ordering, viewing data) fail:

| # | Root Cause | Browser Error / Symptom | Where It Breaks | How to Prevent / Fix on Render |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Wrong or Mismatched `FOOD_COURT_API_BASE`** in `frontend/js/config.js` | `net::ERR_NAME_NOT_RESOLVED` or `404 Not Found` | `frontend/js/config.js` hardcoded to `college-food-court-api.onrender.com` | Ensure `config.js` matches your exact Render backend service name, or dynamically detect `window.location.origin` if reverse-proxied. |
| **2** | **Missing `config.js` on 8 HTML Pages** | `404 Not Found` for `.../undefined/orders`, `.../undefined/cart` | `orders.html`, `preorder.html`, `profile.html`, `admin/*.html`, `vendor/*.html`, `faculty-login.html` | Add `<script src="../../js/config.js"></script>` before the controller script on all 8 pages. |
| **3** | **CORS Block (`CORS_ORIGINS` unset or wildcard `*`)** | `Access to fetch ... blocked by CORS policy: No 'Access-Control-Allow-Origin' header` | `backend/app.py` line 75-88 | Set `CORS_ORIGINS=https://<your-frontend-service>.onrender.com` in Render Backend Web Service env vars (no trailing slash). |
| **4** | **Cross-Site Cookie Stripping (`SameSite=Lax`)** | `401 Unauthorized` on every request immediately after login | `backend/app.py` line 63 | Change `SESSION_COOKIE_SAMESITE = "None"` and `SESSION_COOKIE_SECURE = True` when frontend and backend use different `.onrender.com` domains. |
| **5** | **PostgreSQL URL used for PyMySQL** | `DatabaseConnectionError: 500/503 Database service unavailable` | `backend/db.py` line 47 | Use MySQL 8.0 connection string (`mysql://...`), not Render's default PostgreSQL (`postgres://...`). |
| **6** | **Render Free Tier Cold Starts** | Initial request times out (HTTP 504 / Network Timeout) | Render free instance spindown (idle after 15m) | Allow 60s for the free instance to spin up on first request, or upgrade to Render Starter instance ($7/mo). |
| **7** | **Fatal Boot Crash on Missing Secrets** | `502 Bad Gateway` on all `/api/*` endpoints | `backend/app.py` line 48 & `backend/config.py` line 118 | Configure valid `SECRET_KEY`, `DB_PASSWORD`, and Razorpay keys in Render environment variables. |

---

## 4. Exact Render Deployment Blueprints & Specifications

### Blueprint A: Recommended Two-Service Architecture

```
[Student / Faculty Browser]
       │
       ├─── (Static Assets: HTML, CSS, JS) ───> [Render Static Site: frontend]
       │                                        (https://foodcourt-app.onrender.com)
       │
       └─── (REST API: /api/* with CORS) ─────> [Render Web Service: backend]
                                                (https://foodcourt-api.onrender.com)
                                                            │
                                                            └───> [External MySQL 8.0]
```

#### Service 1: Render Static Site (Frontend)
* **Name**: `foodcourt-frontend`
* **Root Directory**: `frontend`
* **Build Command**: *(leave empty)*
* **Publish Directory**: `.`
* **Auto-Deploy**: Yes

#### Service 2: Render Web Service (Backend API)
* **Name**: `foodcourt-api`
* **Environment**: `Python 3`
* **Root Directory**: `.` (repo root)
* **Build Command**: `pip install -r requirements.txt`
* **Start Command**:
  ```bash
  gunicorn -c gunicorn.conf.py --chdir backend app:app
  ```
* **Health Check Path**: `/api/ready`

---

## 5. Complete Render Environment Variables Reference

Add the following environment variables in the **Render Web Service Dashboard** under **Environment**:

| Variable Name | Required? | Example Value / Instructions | Purpose |
| :--- | :---: | :--- | :--- |
| `FLASK_ENV` | **YES** | `production` *(or `development` for sandbox staging)* | Activates production security, DB fail-fast, and hardened error handlers. |
| `PORT` | Auto | Render sets this automatically (e.g. `10000`). Do not override. | Container listening port. |
| `SECRET_KEY` | **YES** | `e1b7f09a8264d1c4b7891234567890abcdef1234567890abcdef1234567890ab` | Minimum 32-byte high-entropy session signing secret. |
| `CORS_ORIGINS` | **YES** | `https://foodcourt-frontend.onrender.com` | **Exact** origin of the frontend static site (comma-separated if multiple, no trailing slash). |
| `COOKIE_SECURE` | **YES** | `1` | Enforces `Secure` flag on session cookies over HTTPS. |
| `DB_HOST` | **YES** | `mysql.external-provider.com` | Hostname of external MySQL 8.0 database. |
| `DB_PORT` | **YES** | `3306` | MySQL port. |
| `DB_USER` | **YES** | `foodcourt_admin` | MySQL username. |
| `DB_PASSWORD` | **YES** | `YourStrongRemoteDbPassword!` | MySQL password. |
| `DB_NAME` | **YES** | `food_court_db` | MySQL database name. |
| `DATABASE_URL` | Optional | `mysql://user:pass@host:3306/food_court_db` | Alternative unified MySQL connection URL (overrides separate DB_* vars). |
| `PAYMENT_PROVIDER` | **YES** | `razorpay` | Primary payment provider. |
| `PAYMENT_ENVIRONMENT` | **YES** | `production` *(or `test`)* | Payment environment mode. |
| `RAZORPAY_KEY_ID` | **YES** | `rzp_live_xxxxxxxxxxxxxx` *(or `rzp_test_...` if `FLASK_ENV=development`)* | Razorpay Public Key ID. |
| `RAZORPAY_KEY_SECRET` | **YES** | `xxxxxxxxxxxxxxxxxxxxxxxx` | Razorpay Secret Key. |
| `RAZORPAY_WEBHOOK_SECRET`| **YES** | `whsec_xxxxxxxxxxxxxxxxxxxx` | Razorpay Webhook Signature Verification Secret. |
| `GOOGLE_CLIENT_ID` | Optional | `123456789-xxxxxx.apps.googleusercontent.com` | Google Identity Services OAuth 2.0 Client ID. |
| `ADMIN_EMAIL` | Optional | `admin@kpriet.ac.in` | Administrator root account email (defaults to `admin@kpriet.ac.in`). |
| `ADMIN_PASSWORD` | **Recommended** | `YourStrongAdminPassword123!` | Automatically provisions or resets the root administrator account on startup. |
| `GEMINI_API_KEY` | Optional | `AIzaSyxxxxxxxxxxxxxxxxxxxxxx` | Google Gemini API Key for AI Financial Assistant. |
| `GUNICORN_WORKERS` | Optional | `2` | WSGI worker processes (2 is optimal for Render 512MB RAM tier). |
| `GUNICORN_THREADS` | Optional | `2` | Threads per worker process. |
| `GUNICORN_TIMEOUT` | Optional | `60` | Request timeout in seconds. |

---

## 6. Verification Checklist Prior to Live Traffic

1. **Verify Backend Readiness**:
   ```bash
   curl -i https://<your-backend>.onrender.com/api/ready
   # Must return: HTTP/2 200 {"status": "ready", "database": "connected"}
   ```
2. **Verify CORS Headers on Preflight**:
   ```bash
   curl -i -X OPTIONS https://<your-backend>.onrender.com/api/auth/login \
     -H "Origin: https://<your-frontend>.onrender.com" \
     -H "Access-Control-Request-Method: POST"
   # Must return: Access-Control-Allow-Origin: https://<your-frontend>.onrender.com
   # Must return: Access-Control-Allow-Credentials: true
   ```
3. **Verify Frontend API Discovery**:
   Open browser developer console on the deployed frontend and type:
   ```javascript
   console.log(window.FOOD_COURT_API_BASE);
   // Must output the exact HTTPS URL of the live backend API.
   ```
4. **Verify Session Persistence**:
   Log in as a customer on the deployed frontend. Navigate to **Orders** and **Profile**. Ensure you are not logged out and no 401 errors appear in the browser console.
