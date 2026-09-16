# College Food Court Pilot Runbook & Operational Guide

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Phase**: Phase 10 — Real Cloud Deployment & Live College Pilot  
**Target Environment**: Campus Staging / Controlled Campus Pilot  
**Pilot Status**: `STAGING DEPLOYMENT VERIFIED / CLOUD PILOT READY (PENDING INSTITUTIONAL INFRASTRUCTURE)`  

---

## 1. Pilot Scope & Governance

The goal of the pilot program is to validate real-world operational flows, pickup efficiency, concurrency handling, and student/faculty satisfaction in a controlled campus environment prior to full campus-wide rollout.

### 1.1 Controlled Pilot Cohort
To prevent vendor counter congestion during peak hours, access is strictly scoped:
- **Undergraduate Cohort**: 50 Students (selected from Dept. of Computer Science & Engineering and Information Technology).
- **Faculty & Staff Cohort**: 10 Faculty Members (Engineering & Management departments).
- **Guest / Administration Accounts**: 5 Managed accounts for Food Court Supervisors and Quality Auditors.
- **Total Initial Pilot Size**: Maximum 65 active users.

### 1.2 Participating Food Court Stalls
The initial pilot runs across two high-volume food court vendors:
1. **YPR Stalls (Stall ID 1)**: Specializes in breakfast, South Indian meals, and quick lunch items (Dosa, Meals, Fried Rice).
2. **German Cafe (Stall ID 2)**: Specializes in beverages, short snacks, and fast food (Coffee, Sandwiches, Cold Drinks).

Other stalls (Royal Kitchen, Mario, Saaral) remain hidden or marked offline in this phase until pilot metrics satisfy key performance indicators (KPIs).

---

## 2. End-to-End Operational Lifecycle

```
[Customer] 
    │  1. Authenticates (Student/Faculty Roll Number & Email)
    │  2. Browses menu with AI meal-slot recommendations
    │  3. Places order & pays via Razorpay Gateway (Paise-level validation)
    ▼
[Database / Orders Engine]
    │  4. Deducts item stock atomically (ACID transaction)
    │  5. Generates authoritative Order ID & secure 4-digit Pickup OTP
    │  6. Dispatches real-time WebSocket / DB notification
    ▼
[Vendor Dashboard]
    │  7. Vendor sees new order in "PLACED" state
    │  8. Updates status to "PREPARING" -> "READY"
    ▼
[Customer Counter Pickup]
    │  9. Customer receives "Order Ready for Pickup" alert
    │ 10. Customer arrives at designated stall counter and displays OTP
    │ 11. Vendor inputs OTP into Vendor Dashboard
    │ 12. System verifies OTP via POST /api/vendor/orders/<id>/verify-otp
    ▼
[Order Completed]
    │ 13. Order status transitions to "COMPLETED"
    │ 14. Stock consumption finalized; audit record created
```

---

## 3. Counter Verification & OTP Workflow

1. **OTP Generation**:
   - The pickup OTP is a cryptographically random 4-digit number generated at order placement and stored in `orders.pickup_otp`.
   - Accessible only to the authenticated customer who owns the order and the vendor of that stall once the order reaches `READY` status.

2. **Counter Verification Steps**:
   - Customer arrives at the counter and presents their Order ID and 4-digit OTP.
   - Vendor clicks **Verify OTP** on their dashboard (`POST /api/vendor/orders/<id>/verify-otp`).
   - If the OTP matches, the system updates `orders.status = 'COMPLETED'` and records the fulfillment timestamp.
   - If the OTP fails, an error is returned and the order remains `READY`. After 3 failed attempts, the vendor must inspect student college ID.

3. **Fallback Procedure**:
   - If customer's phone battery expires or network disconnects at the counter, vendor verifies the student's physical College ID Card matching the name/roll number on the order record and manually approves with supervisor override.

---

## 4. Financial Reconciliation & Razorpay Settlement

### 4.1 Daily Reconciliation Schedule (Cutoff: 18:00 IST)
At 18:00 IST daily, the Food Court Administrative Supervisor runs the reconciliation sequence:
1. Export completed order report from Admin Portal:
   - Query: `SELECT * FROM orders WHERE created_at BETWEEN @start AND @end AND status = 'COMPLETED'`
   - Total Gross Revenue = Sum of `orders.total_amount`
2. Export Razorpay Merchant Dashboard Settlement & Payment Batch:
   - Match Razorpay Payment IDs (`pay_...`) against `payments.razorpay_payment_id`.
   - Verify that all `CAPTURED` payments match the exact amount in paise (`amount_cents / 100`).
3. Identify Discrepancies:
   - **Captured in Razorpay, Failed in DB**: Initiate manual order sync via webhook replay or supervisor tool.
   - **Abandoned Checkout**: Verify order is marked `FAILED` and reserved stock was properly released back to inventory.

### 4.2 Vendor Payout Distribution
- **Commission / Platform Fee**: 2.5% deducted automatically for campus payment gateway processing.
- **Net Payout**: Transferred to vendor accounts on a T+1 business day schedule via automated bank NEFT/IMPS.

---

## 5. Dispute Resolution & Incident Response Protocols

### 5.1 Common Failure Scenarios & Standard Operating Procedures (SOP)

| Incident | Root Cause | Operator Action | System Impact |
| :--- | :--- | :--- | :--- |
| **Payment Deducted, Order Not Placed** | Network timeout during customer redirect | Customer provides Razorpay Payment ID. Admin queries Razorpay API; if captured, triggers `POST /api/payments/webhook` replay or issues refund. | Zero duplicate stock deduction. |
| **Stall Runs Out of Ingredient** | Unexpected rush on item | Vendor toggles item to `OUT OF STOCK` on dashboard. Existing unfulfilled orders are marked `CANCELLED` with automatic refund. | Stock set to 0; removed from AI recommendations. |
| **Customer No-Show (> 45 min after READY)** | Student missed pickup | After 45 minutes, stall marks order as `EXPIRED`. Food is discarded according to food safety guidelines. No automatic refund for perishable food. | Order marked `EXPIRED` in audit logs. |
| **Database Unavailability Alert** | Host reboot or network split | Liveness probe passes, readiness probe fails (HTTP 503). Frontend shows "System Maintenance" modal. | Orders blocked safely; zero orphaned payments. |

---

## 6. Pilot KPI Success Metrics

The pilot will run for an evaluation period of **10 operational days**. Progression to full campus-wide launch requires meeting all of the following criteria:

- [ ] **Order Success Rate**: $\ge 98.5\%$ of initiated orders successfully reach `COMPLETED` without manual intervention.
- [ ] **Average Queue / Wait Time Reduction**: Counter turnaround time reduced by $\ge 40\%$ compared to physical cash queues.
- [ ] **Payment Verification Accuracy**: $100\%$ reconciliation accuracy between Razorpay daily settlement and database payment records.
- [ ] **Stock Integrity**: $0$ instances of negative stock or double-booking during peak meal hours.
- [ ] **Customer Feedback Score**: Average rating $\ge 4.2 / 5.0$ collected from pilot participants.
- [ ] **Zero Security Incidents**: Zero unauthorized API access, IDOR vulnerabilities, or plaintext secret exposure.
