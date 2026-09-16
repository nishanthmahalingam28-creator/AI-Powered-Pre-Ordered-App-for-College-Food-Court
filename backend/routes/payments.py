"""
Payment Routes and Webhook Handler for College Food Court Application.
Supports:
- Official Razorpay Webhook listener (POST /api/payments/webhook) with HMAC-SHA256 signature verification.
- Direct payment verification (POST /api/payments/verify).
- Status polling and payment inquiry (GET /api/payments/<int:order_id>/status).
"""

import json
import logging
from flask import Blueprint, request, jsonify, session
from db import DB
from routes.auth import role_required
from services.payment import PaymentService
from services.payment_provider import get_payment_provider

logger = logging.getLogger("food_court.payments_route")
payments_bp = Blueprint("payments", __name__)


@payments_bp.post("/webhook")
def razorpay_webhook():
    """
    Official Razorpay Webhook Endpoint.
    1. Cryptographically verifies X-Razorpay-Signature over the raw request payload.
    2. Idempotently processes payment.captured, order.paid, and payment.failed events.
    3. Guarantees stock and payment consistency under duplicate or out-of-order deliveries.
    """
    raw_body = request.get_data()
    webhook_signature = request.headers.get("X-Razorpay-Signature")

    if not webhook_signature or not raw_body:
        logger.warning("Unsigned or empty webhook received.")
        return jsonify({"success": False, "message": "Missing webhook signature or payload."}), 400

    provider = get_payment_provider()
    is_valid = provider.verify_webhook_signature(raw_body, webhook_signature)
    if not is_valid:
        logger.warning("Invalid webhook signature detected.")
        return jsonify({"success": False, "message": "Invalid webhook signature."}), 400

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse webhook JSON payload: %s", e)
        return jsonify({"success": False, "message": "Malformed JSON payload."}), 400

    event_type = payload.get("event")
    event_payload = payload.get("payload", {})
    payment_entity = event_payload.get("payment", {}).get("entity", {})
    order_entity = event_payload.get("order", {}).get("entity", {})

    logger.info("Processing webhook event: %s", event_type)

    # 1. Successful payment captured / order paid
    if event_type in ("payment.captured", "order.paid"):
        gateway_order_id = payment_entity.get("order_id") or order_entity.get("id")
        gateway_payment_id = payment_entity.get("id")
        gateway_amount_paise = payment_entity.get("amount") or order_entity.get("amount_paid")

        if not gateway_order_id:
            return jsonify({"status": "ok", "message": "Ignored: No gateway_order_id found."}), 200

        # Look up local payment record by gateway_order_id
        payment = DB.get_one(
            "SELECT id, order_id, amount, status FROM payments WHERE gateway_order_id = %s",
            (gateway_order_id,)
        )
        if not payment:
            logger.warning("Webhook received for unknown gateway_order_id: %s", gateway_order_id)
            return jsonify({"status": "ok", "message": "Payment record not found."}), 200

        local_order_id = payment["order_id"]
        expected_paise = int(round(float(payment["amount"]) * 100))

        # Amount Tampering / Gateway Mismatch Protection
        if gateway_amount_paise is not None and int(gateway_amount_paise) != expected_paise:
            logger.critical(
                "CRITICAL SECURITY ALERT: Webhook amount mismatch for order %s! Gateway: %s paise, Local DB: %s paise",
                local_order_id, gateway_amount_paise, expected_paise
            )
            with DB.transaction() as tx:
                PaymentService.handle_payment_failure(local_order_id, failure_reason="Amount mismatch detected by webhook", tx=tx)
            return jsonify({"success": False, "message": "Amount mismatch detected."}), 400

        # Idempotent status check
        if payment["status"] == "successful":
            return jsonify({"status": "ok", "message": "Already processed."}), 200

        with DB.transaction() as tx:
            # Update payment record
            tx.execute(
                """
                UPDATE payments
                SET status = 'successful', gateway_payment_id = %s, paid_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (gateway_payment_id, payment["id"]),
            )
            # Update order record
            tx.execute(
                """
                UPDATE orders
                SET payment_status = 'paid', payment_time = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (local_order_id,),
            )
        logger.info("Webhook successfully confirmed payment for order_id=%s", local_order_id)

    # 2. Payment failed
    elif event_type == "payment.failed":
        gateway_order_id = payment_entity.get("order_id")
        error_desc = payment_entity.get("error_description") or payment_entity.get("error_reason") or "Gateway payment failed"

        if gateway_order_id:
            payment = DB.get_one("SELECT order_id FROM payments WHERE gateway_order_id = %s", (gateway_order_id,))
            if payment:
                local_order_id = payment["order_id"]
                with DB.transaction() as tx:
                    PaymentService.handle_payment_failure(local_order_id, failure_reason=error_desc, tx=tx)
                logger.info("Webhook processed payment failure for order_id=%s: %s", local_order_id, error_desc)

    return jsonify({"status": "ok"}), 200


@payments_bp.post("/verify")
@role_required(["customer", "admin"])
def verify_payment():
    """
    Client Payment Verification API.
    Called by frontend after customer completes payment in Razorpay Checkout modal.
    """
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    gateway_order_id = str(data.get("razorpay_order_id") or data.get("gateway_order_id") or "").strip()
    gateway_payment_id = str(data.get("razorpay_payment_id") or data.get("gateway_payment_id") or "").strip()
    gateway_signature = str(data.get("razorpay_signature") or data.get("gateway_signature") or "").strip()

    if not order_id or not gateway_order_id or not gateway_payment_id or not gateway_signature:
        return jsonify({
            "success": False,
            "message": "Payment verification requires order_id, razorpay_order_id, razorpay_payment_id, and razorpay_signature."
        }), 400

    customer_id = session.get("user_id") if session.get("role") == "customer" else None

    try:
        with DB.transaction() as tx:
            result = PaymentService.verify_gateway_payment(
                order_id=int(order_id),
                gateway_order_id=gateway_order_id,
                gateway_payment_id=gateway_payment_id,
                gateway_signature=gateway_signature,
                customer_id=customer_id,
                tx=tx
            )
        return jsonify({
            "success": True,
            "message": result["message"],
            "status": "paid",
            "payment_status": "paid",
            "order_id": order_id,
            "transaction_ref": gateway_payment_id
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except PermissionError as pe:
        return jsonify({"success": False, "message": str(pe)}), 403
    except Exception as e:
        logger.error("Payment verification failed for order %s: %s", order_id, e)
        return jsonify({"success": False, "message": "Failed to verify payment."}), 500


@payments_bp.get("/<int:order_id>/status")
@role_required(["customer", "vendor", "admin"])
def get_payment_status(order_id):
    """Returns authoritative payment status for an order."""
    user_id = session.get("user_id")
    user_role = session.get("role")

    order = DB.get_one("SELECT id, customer_id, shop_id, payment_status, total_amount FROM orders WHERE id = %s", (order_id,))
    if not order:
        return jsonify({"success": False, "message": "Order not found."}), 404

    # IDOR check
    if user_role == "customer" and order["customer_id"] != user_id:
        return jsonify({"success": False, "message": "Access forbidden."}), 403

    payment = DB.get_one(
        "SELECT id, provider, method, amount, status, transaction_ref, gateway_order_id, gateway_payment_id, paid_at FROM payments WHERE order_id = %s ORDER BY id DESC LIMIT 1",
        (order_id,)
    )

    return jsonify({
        "success": True,
        "order_id": order_id,
        "payment_status": order["payment_status"],
        "payment": payment
    }), 200
