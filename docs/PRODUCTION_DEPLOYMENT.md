# Production Deployment Runbook

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Environment**: Production (Campus Cloud / Dedicated Linux Server)  
**Target OS**: Ubuntu 22.04 LTS / Debian 12  
**WSGI Server**: Gunicorn (HTTP + Threaded Workers)  
**Reverse Proxy**: Nginx with Let's Encrypt SSL/TLS  
**Database**: MySQL 8.0 Community Edition  

---

## 1. High-Level Architecture

```
                    INTERNET (Students, Faculty, Vendors, Admins)
                                          ↓
                              [HTTPS / Port 443]
                                          ↓
                                NGINX REVERSE PROXY
                         (TLS Termination, Rate Limits,
                         Security Headers, Static Files)
                                          ↓
                              [HTTP / Port 5000]
                                          ↓
                           GUNICORN WSGI PROCESS POOL
                          (4 Workers × 2 Threads each)
                                          ↓
                             FLASK APPLICATION LAYER
                 (RBAC, IDOR Protection, Ordering, Payments, AI)
                                          ↓
                               [Connection Pool]
                                          ↓
                                 MYSQL 8.0 ENGINE
                    (InnoDB, ACID Transactions, Row Locking)
```

---

## 2. Server Prerequisites
- **Minimum Hardware**:
  - CPU: 2 vCPUs (4 vCPUs recommended for peak lunch hours)
  - RAM: 4 GB (8 GB recommended for MySQL InnoDB buffer pool)
  - Storage: 40 GB SSD (NVMe preferred for database logs and backups)
- **Software Dependencies**:
  - Python 3.11+ with `venv`
  - MySQL Server 8.0+
  - Nginx 1.18+
  - Certbot (Let's Encrypt)
  - Git, Curl, Htop

---

## 3. Environment Variables Configuration

Create `/etc/foodcourt/production.env` with restricted permissions (`chmod 600`):

```bash
# Core Application Mode
FLASK_ENV=production
PORT=5000
SECRET_KEY=generate-a-64-character-hex-key-via-python-secrets

# Production Database (MySQL 8.0)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=foodcourt_prod
DB_PASSWORD=strong_production_database_password
DB_NAME=food_court_db
DB_TIMEOUT=5

# Cookie & Session Security (Enforces Secure flag over HTTPS)
COOKIE_SECURE=1

# CORS Allowed Origins (Campus Portal Domain)
CORS_ORIGINS=https://foodcourt.kpriet.ac.in

# Razorpay Payment Gateway (Live credentials when ready)
PAYMENT_PROVIDER=razorpay
PAYMENT_ENVIRONMENT=test
RAZORPAY_KEY_ID=rzp_live_your_actual_key
RAZORPAY_KEY_SECRET=your_actual_live_secret
RAZORPAY_WEBHOOK_SECRET=your_actual_webhook_secret

# WSGI Process Tuning
GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=30
```

---

## 4. Gunicorn Systemd Service Setup

Create `/etc/systemd/system/foodcourt.service`:

```ini
[Unit]
Description=Gunicorn WSGI server for College Food Court API
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/foodcourt
EnvironmentFile=/etc/foodcourt/production.env
ExecStart=/var/www/foodcourt/.venv/bin/gunicorn \
    -c /var/www/foodcourt/gunicorn.conf.py \
    --chdir /var/www/foodcourt/backend \
    app:app

Restart=always
RestartSec=5s
KillSignal=SIGTERM
TimeoutStopSec=30
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable foodcourt
sudo systemctl start foodcourt
sudo systemctl status foodcourt
```

---

## 5. Nginx Reverse Proxy Configuration

Create `/etc/nginx/sites-available/foodcourt`:

```nginx
# Rate limiting zone for sensitive auth & order endpoints
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;

server {
    listen 80;
    server_name foodcourt.kpriet.ac.in;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name foodcourt.kpriet.ac.in;

    ssl_certificate /etc/letsencrypt/live/foodcourt.kpriet.ac.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/foodcourt.kpriet.ac.in/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Static Assets Cache Control
    location /static/ {
        alias /var/www/foodcourt/frontend/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # Sensitive Auth Rate Limit
    location /api/auth/ {
        limit_req zone=auth_limit burst=10 nodelay;
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }

    # API Proxy
    location /api/ {
        limit_req zone=api_limit burst=50 nodelay;
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }

    # Frontend Single-Page / Static Delivery
    location / {
        root /var/www/foodcourt/frontend;
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 6. Verification Probes

### Liveness Probe
```bash
curl -I https://foodcourt.kpriet.ac.in/api/health
# Expected: HTTP 200 OK
# {"environment":"production","service":"food-court-api","status":"ok","version":"2.0.0"}
```

### Readiness Probe
```bash
curl -I https://foodcourt.kpriet.ac.in/api/ready
# Expected: HTTP 200 OK
# {"database":"connected","service":"food-court-api","status":"ready"}
```

---

## 7. Zero-Downtime Deployment & Rollback

### Zero-Downtime Reload
Gunicorn supports `HUP` reloading without terminating in-flight requests:
```bash
cd /var/www/foodcourt
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl reload foodcourt
```

### Rollback Procedure
```bash
# 1. Revert to previous Git tag
git checkout v1.9.0

# 2. Re-run Gunicorn reload
sudo systemctl reload foodcourt

# 3. Check readiness
curl -f http://127.0.0.1:5000/api/ready || sudo systemctl restart foodcourt
```
