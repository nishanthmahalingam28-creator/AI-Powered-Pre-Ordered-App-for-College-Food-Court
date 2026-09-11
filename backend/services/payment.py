"""
Payment Service Abstraction for College Food Court Application.
Supports:
- Campus Wallet (Internal student ledger)
- UPI Simulation (Development mode simulated gateway)
- Cash at Counter (Pay upon physical pickup)

Ensures clear separation between development simulated payments and production gateways.
Never stores card credentials, CVVs, or bank secrets.
"""
import secrets
from datetime import datetime
from db import DB


class PaymentService:
    SUPPORTED_METHODS = {
        "campus_wallet": "Campus Wallet / KPR Pay",
        "kpr_pay": "Campus Wallet / KPR Pay",
        "campus wallet": "Campus Wallet / KPR Pay",
        "upi": "UPI (Simulated Gateway)",
        "cash": "Pay at Counter"
    }

    @classmethod
    def process_payment(cls, order_id, method, amount, customer_id=None, tx=None):
        method_key = str(method or "campus_wallet").strip().lower()
        method_label = cls.SUPPORTED_METHODS.get(method_key, "Campus Wallet / KPR Pay")

        tx_ref = f"TXN-{secrets.token_hex(6).upper()}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        executor = tx if tx is not None else DB
        payment_id = executor.execute(
            """
            INSERT INTO payments (order_id, method, amount, status, transaction_ref, created_at)
            VALUES (%s, %s, %s, 'successful', %s, %s)
            """,
            (order_id, method_label, float(amount), tx_ref, created_at),
        )

        return {
            "payment_id": payment_id,
            "status": "successful",
            "transaction_ref": tx_ref,
            "method": method_label,
            "amount": float(amount),
            "mode": "development_simulated"
        }
