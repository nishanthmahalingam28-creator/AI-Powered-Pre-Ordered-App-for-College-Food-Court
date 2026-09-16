# College Food Court Platform — Incident Response Plan (IRP)

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Document**: Standard Operating Procedure — Incident Response  
**Target Environment**: Campus Staging & Institutional Production Deployment  
**Classification**: `IMPLEMENTED / OPERATIONAL`  

---

## 1. Incident Management Lifecycle & Severity Matrix

Every platform anomaly, outage, or security event must be managed through the 6-stage lifecycle:
```
[1. Detection] ──▶ [2. Containment] ──▶ [3. Investigation] ──▶ [4. Recovery] ──▶ [5. Verification] ──▶ [6. Post-Mortem]
```

### 1.1 Incident Severity Levels

| Severity Level | Definition | Response SLA | Resolution SLA | Notification Scope |
| :--- | :--- | :--- | :--- | :--- |
| **P1 — Critical** | Total platform outage, payment gateway failure, database corruption, or confirmed security breach. | $< 15\text{ min}$ | $< 2\text{ hours}$ | Campus IT Director, Food Court Admin, Lead Developer |
| **P2 — Major** | Partial outage affecting orders, vendor kitchen queue down, or webhook failure causing order delays. | $< 30\text{ min}$ | $< 4\text{ hours}$ | Food Court Supervisors, Affected Stall Vendors |
| **P3 — Moderate** | Individual vendor terminal glitch, notification delivery delay, or intermittent non-fatal API errors. | $< 2\text{ hours}$ | $< 8\text{ hours}$ | Assigned Support Engineer, Affected Vendor |
| **P4 — Low** | Minor cosmetic UI defects, non-critical analytics delay, or routine customer inquiry. | $< 24\text{ hours}$ | Next Sprint | Support Desk Queue |

---

## 2. Standard Operating Procedures by Incident Type

### 2.1 Scenario A: Total Application Outage (HTTP 5xx Spikes)
1. **Detection**:
   - Automated monitoring alerts on 5xx error rate $> 2\%$ or liveness probe (`GET /api/health`) failure.
2. **Containment**:
   - Nginx returns 502/503. Check Gunicorn process status: `sudo systemctl status foodcourt` or `docker ps`.
   - If container has crashed or memory leaked, restart service: `sudo systemctl restart foodcourt`.
3. **Investigation**:
   - Inspect recent application logs: `tail -n 100 /var/log/foodcourt/error.log`.
   - Check system resources: `free -m`, `df -h`, `uptime`.
4. **Recovery**:
   - If corrupted release was deployed, trigger rollback procedure (revert to previous verified Docker tag or Git commit).
5. **Verification**:
   - Run `curl -fsS http://127.0.0.1:5000/api/health` and verify HTTP 200 response with `"status": "ok"`.
6. **Documentation**:
   - Document root cause in `docs/incidents/INCIDENT_LOG.md`.

---

### 2.2 Scenario B: Database Outage or Connection Pool Exhaustion
1. **Detection**:
   - Readiness probe (`GET /api/ready`) returns HTTP 503 with `"database": "disconnected"`.
2. **Containment**:
   - Frontend automatically displays "System Maintenance: Database Reconnecting" modal to prevent new orders.
3. **Investigation**:
   - Check MySQL service: `sudo systemctl status mysql`.
   - Inspect active threads and locks: `SHOW PROCESSLIST;` and `SHOW ENGINE INNODB STATUS;`.
   - Check connection threshold: `SHOW VARIABLES LIKE 'max_connections';`.
4. **Recovery**:
   - Kill blocking or orphaned locks if necessary.
   - If MySQL daemon stopped, restart: `sudo systemctl restart mysql`.
5. **Verification**:
   - Query `/api/ready` until response returns HTTP 200 with `"database": "connected"`.
   - Verify zero uncommitted orphaned transactions in `orders` and `payments` tables.
6. **Documentation**:
   - Log incident duration and tune `max_connections` or connection pool recycle timeouts if needed.

---

### 2.3 Scenario C: Razorpay Payment Outage or Webhook Failure
1. **Detection**:
   - Spike in customer reports: "Money deducted, order shows pending" or webhook failure logs.
2. **Containment**:
   - Verify Razorpay status dashboard (`status.razorpay.com`).
   - If gateway is down, toggle payment method to "Pay at Counter / Campus Card" via Admin settings.
3. **Investigation**:
   - Inspect webhook logs: `grep -i "webhook" /var/log/foodcourt/access.log`.
   - Check for signature mismatches, HTTP 400 responses, or network timeouts.
4. **Recovery**:
   - For orders with captured payments in Razorpay but pending in DB:
     - Execute the admin reconciliation script or trigger webhook replay from the Razorpay Merchant Dashboard.
     - System idempotency guarantees exact-once stock and payment confirmation.
5. **Verification**:
   - Verify order transitions to `paid` / `placed` and customer receives confirmation notification.
6. **Documentation**:
   - Record payment transaction IDs and settlement impact.

---

### 2.4 Scenario D: Stock Inconsistency & Negative Inventory Alert
1. **Detection**:
   - Audit alert on `menu_items.quantity < 0` or vendor report of selling out unavailable food.
2. **Containment**:
   - Vendor immediately toggles item to `is_available = 0` on the vendor dashboard.
3. **Investigation**:
   - Identify concurrent orders placed for that item: `SELECT * FROM order_items WHERE menu_item_id = %s ORDER BY id DESC LIMIT 10;`.
   - Inspect transaction logs to ensure row-level locking was active (`SELECT ... FOR UPDATE`).
4. **Recovery**:
   - Update quantity to 0: `UPDATE menu_items SET quantity = 0, is_available = 0 WHERE id = %s;`.
   - If an unfulfillable order was accepted, vendor contacts customer and offers equivalent substitute or initiates immediate cancellation/refund via supervisor override.
5. **Verification**:
   - Verify item is completely hidden from AI recommendations and customer menus.
6. **Documentation**:
   - Log inventory adjustment in vendor audit log.

---

### 2.5 Scenario E: Security Incident, OTP Brute-Force, or IDOR Attempt
1. **Detection**:
   - Multiple HTTP 429 responses on `/api/orders/verify-otp` or unauthorized customer access logs.
2. **Containment**:
   - Offending IP is automatically rate-limited by Nginx `auth_limit` zone (5 req/min).
   - If persistent, add temporary firewall drop rule: `sudo ufw insert 1 deny from <attacker-ip> to any`.
3. **Investigation**:
   - Inspect request correlation ID in `/var/log/foodcourt/access.log`.
   - Check if any unauthorized order IDs or customer IDs were accessed.
4. **Recovery**:
   - Invalidate compromised user session: `DELETE FROM sessions WHERE user_id = %s;`.
   - Require password reset upon next login.
5. **Verification**:
   - Verify audit logs confirm zero unauthorized data leakage or tampering.
6. **Documentation**:
   - Compile security incident report for Campus IT Information Security Officer.

---

## 3. Communication & Escalation Paths

```
Customer / Vendor Incident
           │
           ▼
[Food Court Helpdesk / Ground Supervisor]
           │
           ├── If resolved on-site (e.g. food replacement) ──▶ Case Closed
           │
           └── If system anomaly (Payment / App / Stock)
                     │
                     ▼
           [Lead Technical On-Call Engineer]
                     │
                     ├── P3/P4: Resolve during operational hours
                     │
                     └── P1/P2: Escalate to Campus IT & Payment Gateway Support
```

### Key Contact Contacts (Operational Pilot)
* **Food Court Admin Office**: Extension 4401 / `foodcourt-admin@kpriet.ac.in`
* **Campus Network & Server Team**: Extension 4110 / `it-support@kpriet.ac.in`
* **Emergency Technical Escalation**: Designated Lead Developer Mobile (On-Call)
