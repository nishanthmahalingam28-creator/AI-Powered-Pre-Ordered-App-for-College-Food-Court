# Development Setup Guide
**Project:** AI-Powered Pre-Ordered App for College Food Court

---

## 1. Prerequisites
- **Python:** 3.11 or higher (Python 3.11, 3.12, 3.13, 3.14 supported)
- **Database (choose one):**
  - **SQLite (Default for quick local development & testing):** Zero setup required. Automatically creates `backend/food_court_local.db`.
  - **MySQL 8.0 (Recommended for production emulation):** Local MySQL server or Docker MySQL.
- **Node.js / Live Server (Optional):** Frontend is vanilla HTML5/JS and requires no build steps.

---

## 2. Quickstart Step-by-Step

### Step 1: Clone and Navigate to Directory
```bash
cd AI-Powered-Pre-Ordered-App-for-College-Food-Court
```

### Step 2: Set Up Python Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy `.env.example` to `.env` in the project root:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Key local development configuration variables:
```ini
FLASK_APP=app.py
FLASK_ENV=development
PORT=5000
SECRET_KEY=dev-local-secret-key-at-least-32-chars-long
USE_SQLITE=1
CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
COOKIE_SECURE=0
```

### Step 5: Initialize the Database & Seed Sample Data
```bash
python backend/init_db.py
```
This automatically initializes the 16 database tables and seeds sample stalls, menu items, and default test accounts.

---

## 3. Running Automated Tests

Run the full automated test suite using pytest:
```bash
python -m pytest -q
```

To run a specific test suite:
```bash
python -m pytest tests/test_phase12_remediation.py -v
python -m pytest tests/test_cart_api.py -v
```

---

## 4. Running the Application Locally

### Option A: One-Click Launchers
- **Windows Batch:** Double-click `run_app.bat`
- **Windows PowerShell:** Execute `.\run_app.ps1`

### Option B: Manual Two-Terminal Launch
**Terminal 1 — Backend REST API:**
```bash
cd backend
python app.py
```
*API is accessible at `http://127.0.0.1:5000/api/health`.*

**Terminal 2 — Frontend Static Server:**
```bash
# From workspace root:
python -m http.server 5500 --directory frontend
```
*Web application is accessible at `http://127.0.0.1:5500/index.html`.*

---

## 5. Running with Docker Compose (Production Emulation)

```bash
# Ensure required environment variables are set in .env
docker compose up --build
```
- **Nginx Ingress:** `http://localhost/`
- **Backend API:** `http://localhost/api/health`
- **Isolated MySQL 8.0:** accessible internally via Docker bridge.

---

## 6. Default Test Credentials

| Portal | URL | Username / Email | Password | Role |
| :--- | :--- | :--- | :--- | :--- |
| **Customer Portal** | `http://127.0.0.1:5500/pages/customer/dashboard.html` | `student@kpriet.ac.in` | `password123` | Student |
| **Faculty Portal** | `http://127.0.0.1:5500/pages/auth/faculty-login.html` | `faculty@kpriet.ac.in` | (Set on signup) | Faculty |
| **Guest Portal** | `http://127.0.0.1:5500/pages/auth/guest-login.html` | `guest@example.com` | (Set on signup) | Guest |
| **Vendor (YPR)** | `http://127.0.0.1:5500/pages/vendor/login.html` | `ypr@kpriet.ac.in` | `vendor123` | Stall 1 |
| **Vendor (Campus Kitchen)** | `http://127.0.0.1:5500/pages/vendor/login.html` | `campus@kpriet.ac.in` | `vendor123` | Stall 2 |
| **Vendor (German Cafe)** | `http://127.0.0.1:5500/pages/vendor/login.html` | `german@kpriet.ac.in` | `vendor123` | Stall 3 |
| **Vendor (Royal Kitchen)** | `http://127.0.0.1:5500/pages/vendor/login.html` | `royal@kpriet.ac.in` | `vendor123` | Stall 4 |
| **Vendor (Mario)** | `http://127.0.0.1:5500/pages/vendor/login.html` | `mario@kpriet.ac.in` | `vendor123` | Stall 5 |
| **Vendor (Saaral)** | `http://127.0.0.1:5500/pages/vendor/login.html` | `saaral@kpriet.ac.in` | `vendor123` | Stall 6 |
| **Admin Control Hub** | `http://127.0.0.1:5500/pages/admin/login.html` | `admin@kpriet.ac.in` *(or `admin`)* | `admin123` | Admin |
