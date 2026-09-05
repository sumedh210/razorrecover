import random
import sqlite3
import time
import uuid
import random
from pathlib import Path


DATABASE_PATH = Path("data/processed/merchant_tuned.db")

PAYMENT_INTERVAL_SECONDS = random.randint(5, 15)
FAILURE_PROBABILITY = 0.351216

FAILURE_TYPES = [
    {
        "error_source": "customer",
        "error_reason": "incorrect_otp",
    },
    {
        "error_source": "customer",
        "error_reason": "authentication_failed",
    },
    {
        "error_source": "gateway",
        "error_reason": "gateway_technical_error",
    },
    {
        "error_source": "gateway",
        "error_reason": "payment_timed_out",
    },
    {
        "error_source": "bank",
        "error_reason": "payment_failed",
    },
    {
        "error_source": "gateway",
        "error_reason": "payment_risk_check_failed",
    },
]

PAYMENT_METHODS = [
    "card",
    "upi",
    "netbanking",
    "wallet",
]

BANKS = [
    "HDFC",
    "ICIC",
    "SBIN",
    "UTIB",
    "KKBK",
]


def get_random_customer():
    """
    Pick an existing customer from the customers table.
    """

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            """
            SELECT
                customer_id,
                name,
                email,
                contact
            FROM customers
            ORDER BY RANDOM()
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            raise RuntimeError("No customers found in customers table")

        return dict(row)

    finally:
        connection.close()


def generate_payment():
    """
    Generate a simulated payment for an existing customer.
    """

    customer = get_random_customer()

    payment_id = f"pay_sim_{uuid.uuid4().hex[:12]}"
    order_id = f"order_sim_{uuid.uuid4().hex[:12]}"

    created_at = int(time.time())

    amount = random.randint(100, 500000)
    method = random.choice(PAYMENT_METHODS)
    bank = random.choice(BANKS)

    payment = {
        "payment_id": payment_id,
        "order_id": order_id,

        # Real customer from customers table
        "customer_id": customer["customer_id"],

        "entity": "payment",
        "amount": amount,
        "currency": "INR",

        # Successful by default
        "status": "captured",
        "method": method,
        "captured": 1,
        "international": 0,

        "description": "Simulated payment",

        # Real customer information
        "email": customer["email"],
        "contact": customer["contact"],

        "invoice_id": None,
        "amount_refunded": 0,
        "refund_status": None,
        "fee": 0,
        "tax": 0,

        "error_code": None,
        "error_description": None,
        "error_source": None,
        "error_step": None,
        "error_reason": None,

        "bank": bank,
        "vpa": None,
        "wallet": None,

        "acquirer_transaction_id": (
            f"txn_{uuid.uuid4().hex[:12]}"
        ),

        "retry_count": 0,
        "created_at": created_at,
        "updated_at": created_at,
    }

    # Randomly create a failed payment
    if random.random() < FAILURE_PROBABILITY:

        failure = random.choice(FAILURE_TYPES)

        payment["status"] = "failed"
        payment["captured"] = 0

        payment["error_source"] = failure["error_source"]
        payment["error_reason"] = failure["error_reason"]

        payment["error_description"] = (
            f"Simulated {failure['error_reason']}"
        )

        # Give the agent different retry-limit scenarios
        payment["retry_count"] = random.choice([0, 0, 0, 1])

    return payment


def insert_payment(payment):
    """
    Insert the simulated payment into the payments table.
    """

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute(
            """
            INSERT INTO payments (
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
                :payment_id,
                :order_id,
                :customer_id,
                :entity,
                :amount,
                :currency,
                :status,
                :method,
                :captured,
                :international,
                :description,
                :email,
                :contact,
                :invoice_id,
                :amount_refunded,
                :refund_status,
                :fee,
                :tax,
                :error_code,
                :error_description,
                :error_source,
                :error_step,
                :error_reason,
                :bank,
                :vpa,
                :wallet,
                :acquirer_transaction_id,
                :retry_count,
                :created_at,
                :updated_at
            )
            """,
            payment,
        )

        connection.commit()

    finally:
        connection.close()


def run_simulator():
    print("Starting payment simulator...")
    print(
        f"Generating one payment in "
        f"{random.randint(5, 15)} seconds."
    )

    while True:
        try:
            payment = generate_payment()
            insert_payment(payment)

            if payment["status"] == "failed":

                print(
                    f"[FAILED] "
                    f"{payment['payment_id']} | "
                    f"customer={payment['customer_id']} | "
                    f"₹{payment['amount']:,} | "
                    f"{payment['error_reason']} | "
                    f"retry_count={payment['retry_count']}"
                )

            else:

                print(
                    f"[CAPTURED] "
                    f"{payment['payment_id']} | "
                    f"customer={payment['customer_id']} | "
                    f"₹{payment['amount']:,} | "
                    f"{payment['method']}"
                )

        except Exception as exc:

            print(
                f"[ERROR] Could not create payment: {exc}"
            )

        time.sleep(random.randint(5, 15))


if __name__ == "__main__":
    run_simulator()