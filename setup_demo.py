import sqlite3
import time
from pathlib import Path


DATABASE_PATH = Path("data/processed/merchant_tuned.db")


DEMO_PAYMENTS = [
    {
        "payment_id": "DEMO_TRANSIENT_*",
        "order_id": "order_demo_transient",
        "customer_id": "cust_demo_001",
        "amount": 5500.0,
        "error_reason": "payment_timed_out",
        "error_description": "Payment timed out while communicating with the gateway",
        "error_source": "gateway",
        "error_step": "payment_processing",
        "method": "card",
        "bank": "HDFC",
    },
    {
        "payment_id": "DEMO_AUTH_*",
        "order_id": "order_demo_auth",
        "customer_id": "cust_demo_002",
        "amount": 6500.0,
        "error_reason": "incorrect_otp",
        "error_description": "Customer entered an incorrect OTP",
        "error_source": "customer",
        "error_step": "authentication",
        "method": "card",
        "bank": "ICICI",
    },
    {
        "payment_id": "DEMO_HIGH_VALUE_*",
        "order_id": "order_demo_high_value",
        "customer_id": "cust_demo_003",
        "amount": 2500000.0,
        "error_reason": "payment_failed",
        "error_description": "High-value payment failed during processing",
        "error_source": "bank",
        "error_step": "payment_processing",
        "method": "card",
        "bank": "SBI",
    },
]


def setup_demo_payments() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:

        now = int(time.time())

        for payment in DEMO_PAYMENTS:

            connection.execute(
                """
                INSERT OR REPLACE INTO payments (
                    payment_id,
                    order_id,
                    customer_id,
                    entity,
                    amount,
                    currency,
                    status,
                    method,
                    captured,
                    international,
                    description,
                    email,
                    contact,
                    invoice_id,
                    amount_refunded,
                    refund_status,
                    fee,
                    tax,
                    error_code,
                    error_description,
                    error_source,
                    error_step,
                    error_reason,
                    bank,
                    vpa,
                    wallet,
                    acquirer_transaction_id,
                    retry_count,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, 'payment', ?, 'INR', 'failed', ?,
                    0, 0, ?, '', '', '', 0, '', 0, 0, '',
                    ?, ?, ?, ?, ?, '', '',
                    ?, 0, ?, ?
                )
                """,
                (
                    payment["payment_id"],
                    payment["order_id"],
                    payment["customer_id"],
                    payment["amount"],
                    payment["method"],
                    payment["error_description"],
                    payment["error_description"],
                    payment["error_source"],
                    payment["error_step"],
                    payment["error_reason"],
                    payment["bank"],
                    "",
                    now,
                    now,
                ),
            )

            # Remove any previous recovery/audit records for these
            # demo payments so every run starts clean.
            connection.execute(
                """
                DELETE FROM recovery_actions
                WHERE entity_type = 'payment'
                  AND entity_id = ?
                """,
                (payment["payment_id"],),
            )

            connection.execute(
                """
                DELETE FROM audit_events
                WHERE payment_id = ?
                """,
                (payment["payment_id"],),
            )

            connection.execute(
                """
                DELETE FROM payment_attempts
                WHERE payment_id = ?
                """,
                (payment["payment_id"],),
            )

        connection.commit()

    print("\nDemo payments created successfully.\n")

    for payment in DEMO_PAYMENTS:
        print(
            f"{payment['payment_id']:20} "
            f"₹{payment['amount']:>10,.2f}   "
            f"{payment['error_reason']}"
        )


if __name__ == "__main__":
    setup_demo_payments()