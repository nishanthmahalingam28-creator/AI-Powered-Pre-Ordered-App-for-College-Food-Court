# College Food Court — Customer Support Standard Operating Procedure (SOP)

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Document**: Customer Support & Helpdesk SOP  
**Target Audience**: Food Court Supervisors, Helpdesk Staff, Student Support Representatives  
**Classification**: `IMPLEMENTED / OPERATIONAL`  

---

## 1. Core Principles & Privacy Governance

1. **Student & Faculty First**: Ensure fast, courteous resolution of food court inquiries during peak meal hours.
2. **Zero Sensitive Data Storage / Ingestion**:
   - Support staff must **NEVER** ask for or log a customer's UPI PIN, card CVV, bank passwords, or account passwords.
   - All lookups must be performed using **Order Reference** (e.g. `KPR-123456`) or **College Roll / Staff ID** (e.g. `22CS042`).
3. **Audit Trail**: Every supervisor intervention, refund, or status override is permanently recorded in `audit_logs`.

---

## 2. Standard Support Scenarios & Resolution Workflows

### 2.1 Scenario 1: Pickup OTP Problem at Counter
* **Symptom**: Customer arrives at the counter, but their phone battery has died, network is disconnected, or they cannot locate their OTP.
* **Verification Protocol**:
  1. Ask the customer for their **College ID Card** and **Order ID / Reference Number**.
  2. In the Admin / Supervisor Portal, navigate to **Orders Directory** and search by Order Reference.
  3. Verify that the full name and Roll Number / Staff ID on the physical College ID card match the `customer_profiles` record on the order.
* **Resolution**:
  - If identity matches, supervisor instructs vendor to verify the order using the supervisor emergency counter override, or reads the 4-digit OTP from the authorized order record directly to the vendor.
  - Order transitions to `completed`.

---

### 2.2 Scenario 2: Payment Deducted from Bank, Order Remains "Pending"
* **Symptom**: Student paid ₹130 via UPI / Google Pay / PhonePe, money was deducted from their bank account, but the app shows "Order Pending" or "Payment Processing".
* **Root Cause**: Network timeout or delayed webhook delivery between Razorpay and campus servers.
* **Resolution Protocol**:
  1. Ask student for the **Razorpay Payment ID** (`pay_...`) or Bank UTR number shown on their UPI app receipt.
  2. In the Admin Dashboard, navigate to **Payment Reconciliation**:
     - Search by `gateway_order_id` or `gateway_payment_id`.
     - Click **Query Gateway Status**.
  3. If Razorpay indicates `captured`:
     - Click **Sync Payment & Authorize Order**.
     - System updates `payments.status = 'successful'` and `orders.order_status = 'paid'`.
     - Food stall receives order in their kitchen queue immediately.
  4. If Razorpay indicates `failed` or payment was not captured:
     - Inform student: *"The transaction was declined by the issuing bank. The deducted amount will automatically reverse back to your source account within 24 to 48 hours according to RBI/NPCI settlement guidelines."*
     - If student requires food immediately, offer them to place a "Pay at Counter" order.

---

### 2.3 Scenario 3: Stall Runs Out of Ordered Item
* **Symptom**: Student placed an order for Dosa, but stall runs out of batter during peak rush.
* **Resolution Protocol**:
  1. Vendor informs the ground supervisor.
  2. Supervisor offers student two options:
     - **Option A (Item Substitution)**: Vendor substitutes an item of equal or greater value with student consent.
     - **Option B (Immediate Cancellation & Refund)**: Supervisor cancels the order in Admin Portal with reason: `Out of Stock — Mutual Cancellation`.
  3. System automatically restores remaining stock and initiates an automated refund to the student's Razorpay source account (or campus wallet).

---

### 2.4 Scenario 4: Delayed Order Preparation (> 20 Minutes Past Estimate)
* **Symptom**: Student has a lecture starting soon and their order is still in `PREPARING` status after 20 minutes.
* **Resolution Protocol**:
  1. Supervisor checks live queue depth at that specific stall.
  2. If vendor has an unexpected queue bottleneck:
     - Supervisor requests vendor to prioritize the student's ticket.
     - If student cannot wait and must attend class, supervisor issues a priority pickup voucher or initiates order cancellation with full refund.

---

### 2.5 Scenario 5: Food Quality / Incorrect Item Received
* **Symptom**: Student received Veg Sandwich instead of Grilled Chicken Sandwich.
* **Resolution Protocol**:
  1. Customer reports incorrect item to stall counter within 15 minutes of pickup.
  2. Vendor immediately replaces the item with the correct order without charging the student.
  3. If vendor cannot fulfill the correct item, supervisor processes a refund for that item's value.

---

### 2.6 Scenario 6: Notification Not Received
* **Symptom**: Student claims they never received the "Order Ready" alert.
* **Resolution Protocol**:
  1. Verify whether browser notifications were blocked by customer's device settings.
  2. Advise student to check the **Notifications Bell Icon** inside the application dashboard, which always maintains the authoritative in-app history.

---

## 3. Support Contact Information & Operational Hours

* **Pilot Support Desk**: Located at Food Court Central Counter (Ground Floor).
* **Operating Hours**:
  * Breakfast: 07:30 — 09:30 IST
  * Lunch: 12:00 — 14:30 IST
  * Evening Snacks: 16:30 — 18:30 IST
* **Email Support**: `foodcourt-support@kpriet.ac.in` (Responded to within 30 minutes during active meal hours).
