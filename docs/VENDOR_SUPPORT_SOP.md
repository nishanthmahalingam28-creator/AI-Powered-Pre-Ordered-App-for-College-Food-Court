# College Food Court — Vendor Operations Standard Operating Procedure (SOP)

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Document**: Stall Vendor Operational Guide & SOP  
**Target Audience**: Food Court Stall Operators, Kitchen Staff, Counter Attendants  
**Classification**: `IMPLEMENTED / OPERATIONAL`  

---

## 1. Daily Stall Opening & Closing Routine

### 1.1 Morning Opening Sequence (07:00 IST)
1. **Power On Hardware**: Boot kitchen tablet / POS terminal and verify Wi-Fi connection to campus staff network (`KPR-Staff-5G`).
2. **Log in to Vendor Portal**:
   - URL: `https://foodcourt.kpriet.ac.in/pages/auth/vendor-login.html` (or staging address).
   - Enter vendor credentials (e.g. `ypr@kpriet.ac.in` / password).
3. **Set Operational Status to OPEN**:
   - Toggle stall status switch to **`OPEN`**.
   - Your stall and menu are immediately visible to students and faculty on the customer app.
4. **Daily Stock Audit**:
   - Navigate to **Menu & Inventory**.
   - Input daily prepared batches (e.g. Dosa Batter: 40 servings, Meals: 35 plates).
   - Click **Update Stock**.

### 1.2 Evening Closing Sequence (19:00 IST)
1. **Fulfill Active Queue**: Ensure all in-flight orders are processed to `COMPLETED` or `CANCELLED`.
2. **Toggle Status to CLOSED**:
   - Flip stall operational status to **`CLOSED`**.
   - Prevents customers from placing new orders while allowing vendors to complete pending pickups.
3. **Review Daily Sales Summary**:
   - Click **Daily Batch Report** on the vendor dashboard.
   - Record total fulfilled orders and gross turnover for evening settlement.

---

## 2. Kitchen Order Queue Workflow

```
[Order Notification Arrives]
         │
         ▼
[1. Status: PENDING / PAID]
   • Audible chime sounds on tablet
   • Kitchen ticket displayed with Item Name & Quantity
         │
         ▼ (Vendor taps "Start Preparing")
[2. Status: PREPARING]
   • Customer receives alert: "Your meal is now being prepared"
   • Chef cooks food fresh
         │
         ▼ (Vendor taps "Mark as Ready")
[3. Status: READY]
   • Customer receives alert: "Order Ready! Present OTP at Counter"
   • Food placed in heated holding shelf / counter pick tray
         │
         ▼ (Customer displays 4-digit OTP)
[4. Counter Verification]
   • Vendor types 4-digit OTP into Vendor Dashboard
   • System validates OTP via POST /api/orders/verify-otp
         │
         ▼ (OTP Matches)
[5. Status: COMPLETED]
   • Green confirmation banner: "OTP Verified — Hand over food"
   • Order finalized; stock consumption closed
```

---

## 3. Rapid Stock & Inventory Governance

### 3.1 Emergency Out-of-Stock Action (< 10 Seconds)
If an ingredient runs out unexpectedly during lunch rush:
1. Open **Menu Catalog** on the vendor dashboard.
2. Find the exhausted dish (e.g. *Special South Indian Meals*).
3. Click the **Toggle Availability** button to turn it **`OUT OF STOCK`**.
4. Result:
   - Item is instantly removed from customer menus and AI recommendation engines.
   - Zero orders can be placed for that dish.

### 3.2 Restocking Finished Batches
1. When fresh food arrives from the main commissary:
2. Click **Edit Item** $\rightarrow$ Enter new quantity (e.g. `+25`) $\rightarrow$ Click **Save & Activate**.
3. Item automatically returns to customer menus.

---

## 4. Counter Handshake & Dispute Handling

### 4.1 Counter OTP Verification
* Always ask customer for the **4-digit Pickup OTP** displayed on their screen.
* Enter the OTP into the vendor screen and tap **Verify OTP**.
* **Do NOT hand over food until the screen displays "OTP Verified Successfully" in green.**

### 4.2 Handling Customer Device Failures
* If customer's phone is out of battery:
  1. Ask for student's physical **College ID Card**.
  2. Verify student's name against the ticket name displayed under `customer_name` on the kitchen queue.
  3. Call the food court supervisor to execute authorized supervisor OTP verification.

---

## 5. Daily Financial Settlement & Payout Schedule

1. **Daily Settlement Cutoff**: 18:00 IST every operational day.
2. **Reconciliation Sequence**:
   - Admin generates daily payout ledger deducting 2.5% campus gateway processing fee.
   - Net funds are transferred to the vendor's registered institutional bank account on a **T+1 business day** schedule.
3. **Discrepancy Reporting**:
   - If fulfilled tickets do not match payment records, vendor submits discrepancy note to `foodcourt-admin@kpriet.ac.in` before 19:30 IST on the same day.
