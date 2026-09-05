import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from simulator.database.schema import create_tables, get_connection

fake = Faker("en_IN")

DATABASE_PATH = Path("data/processed/merchant.db")

NUM_CUSTOMERS = 1000
NUM_ORDERS = 3000

PAYMENT_METHODS = [
    "upi",
    "card",
    "netbanking",
    "wallet",
]

BANKS = [
    "HDFC",
    "ICIC",
    "SBIN",
    "UTIB",
    "KKBK",
    "AXIS",
]

WALLETS = [
    "payzapp",
    "mobikwik",
]

UPI_VPAS = [
    "customer@upi",
    "merchant@upi",
    "demo@upi",
]

FAILURE_SCENARIOS = [
    {
        "name": "incorrect_otp",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": (
            "Payment processing failed because of incorrect OTP"
        ),
        "error_source": "customer",
        "error_step": "payment_authentication",
        "error_reason": "incorrect_otp",
        "recommended_profile": "customer_action",
    },
    {
        "name": "payment_failed_bank",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment failed",
        "error_source": "bank",
        "error_step": "payment_authorization",
        "error_reason": "payment_failed",
        "recommended_profile": "retry_candidate",
    },
    {
        "name": "gateway_technical_error",
        "error_code": "GATEWAY_ERROR",
        "error_description": "Payment failed due to a gateway error",
        "error_source": "gateway",
        "error_step": "payment_authorization",
        "error_reason": "gateway_technical_error",
        "recommended_profile": "retry_candidate",
    },
    {
        "name": "payment_timed_out",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment processing timed out",
        "error_source": "gateway",
        "error_step": "payment_authorization",
        "error_reason": "payment_timed_out",
        "recommended_profile": "retry_candidate",
    },
    {
        "name": "authentication_failed",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment authentication failed",
        "error_source": "customer",
        "error_step": "payment_authentication",
        "error_reason": "authentication_failed",
        "recommended_profile": "customer_action",
    },
    {
        "name": "risk_check_failed",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment failed risk checks",
        "error_source": "gateway",
        "error_step": "payment_authorization",
        "error_reason": "payment_risk_check_failed",
        "recommended_profile": "manual_review",
    },
]

def generate_id(prefix: str)->str:
    return f"{prefix}_demo_{uuid.uuid4().hex[:12]}"

def unix_timestamp(days_back: int = 30)->int:
    now = datetime.now()

    timestamp = now - timedelta(
        days = random.uniform(0, days_back),
        hours = random.uniform(0, 23),
        minutes = random.uniform(0, 59),
        seconds = random.uniform(0, 59),
    )

    return int(timestamp.timestamp())

def random_amount_paise() -> int:

    amount_rupees = random.choice(
        [
            random.uniform(199, 999),
            random.uniform(1000, 4999),
            random.uniform(5000, 9999),
            random.uniform(10000, 50000),
        ]
    )

    return int(round(amount_rupees * 100))

# -------------------------------------------------------------------
# Customers
# -------------------------------------------------------------------

def generate_customers(
        connection: sqlite3.Connection,
        count: int,
)-> list[str]:
    cursor = connection.cursor()
    customer_ids = []
    for _ in range(count):
        customer_id = generate_id("cust")
        created_at = unix_timestamp(180)

        cursor.execute(
            """
            INSERT INTO customers (
                    customer_id,
                    name,
                    email,
                    contact,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                fake.name(),
                fake.email(),
                fake.msisdn()[:12],
                created_at,
            ),
        )

        customer_ids.append(customer_id)

    connection.commit()

    return customer_ids

# -------------------------------------------------------------------
# Orders
# -------------------------------------------------------------------

def generate_orders(
        connection: sqlite3.Connection,
        customer_ids: list[str],
        count:int,
)->list[tuple[str, str, int]]:
    cursor = connection.cursor()
    orders = []

    for _ in range(count):
        order_id = generate_id("order")
        customer_id = random.choice(customer_ids)
        amount = random_amount_paise()
        created_at = unix_timestamp(30)

        cursor.execute(
            """
            INSERT INTO orders (
                order_id,
                customer_id,
                amount,
                currency,
                status,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                customer_id,
                amount,
                "INR",
                "created",
                "Synthetic merchant order",
                created_at,
            ),
        )
        orders.append(
            (
                order_id,
                customer_id,
                amount,
            )
        )
    connection.commit()

    return orders

# -------------------------------------------------------------------
# Payment creation helpers
# -------------------------------------------------------------------

def payment_method_details(method: str)-> dict:

    if method == "card":
        return {
            "bank": random.choice(BANKS),
            "vpa": None,
            "wallet": None,
        }

    if method == "netbanking":
        return {
            "bank": random.choice(BANKS),
            "vpa": None,
            "wallet": None,
        }

    if method == "upi":
        return {
            "bank": None,
            "vpa": random.choice(UPI_VPAS),
            "wallet": None,
        }

    if method == "wallet":
        return {
            "bank": None,
            "vpa": None,
            "wallet": random.choice(WALLETS),
        }

    return {
        "bank": None,
        "vpa": None,
        "wallet": None,
    }

def choose_failure() -> dict:
    return random.choice(FAILURE_SCENARIOS)

# -------------------------------------------------------------------
# Payment events
# -------------------------------------------------------------------

def create_payment_event( 
        connection: sqlite3.Connection,
        payment_id: str,
        event_type: str,
        payload: dict, 
        created_at: int, 
    )->None:

    event_id = generate_id("evt")
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO payment_events (
            event_id,
            payment_id,
            event_type,
            created_at,
            payload
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event_id,
            payment_id,
            event_type,
            created_at,
            json.dumps(payload),
        ),
    ) 


# -------------------------------------------------------------------
# Payment attempts
# -------------------------------------------------------------------

def create_payment_attempt(
    connection: sqlite3.Connection,
    payment_id: str,
    attempt_number: int,
    amount: int,
    method: str,
    status: str,
    created_at: int,
    failure: dict | None=None,
)-> None:
    attempt_id = generate_id("attempt")
    details = payment_method_details(method)

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO payment_attempts (
            attempt_id,
            payment_id,
            attempt_number,
            status,
            method,
            amount,
            error_code,
            error_description,
            error_source,
            error_step,
            error_reason,
            bank,
            vpa,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt_id,
            payment_id,
            attempt_number,
            status,
            method,
            amount,
            failure["error_code"] if failure else None,
            failure["error_description"] if failure else None,
            failure["error_source"] if failure else None,
            failure["error_step"] if failure else None,
            failure["error_reason"] if failure else None,
            details["bank"],
            details["vpa"],
            created_at,
        ),
    )

# -------------------------------------------------------------------
# Payments
# -------------------------------------------------------------------

def generate_payments(
        connection: sqlite3.Connection,
        orders: list[tuple[str, str, int]]
) -> None:

    cursor = connection.cursor()

    for order_id, customer_id, amount in orders:

        payment_id = generate_id("pay")
        method = random.choice(PAYMENT_METHODS)

        created_at = unix_timestamp(30)

        is_failed = random.random() < 0.30

        if not is_failed:

            status = "captured"

            retry_count = 0

            details = payment_method_details(method)

            cursor.execute(
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
                    bank,
                    vpa,
                    wallet,
                    retry_count,
                    created_at,
                    updated_at
                )
                 SELECT
                    ?,
                    ?,
                    ?,
                    'payment',
                    ?,
                    'INR',
                    'captured',
                    ?,
                    1,
                    ?,
                    'Synthetic merchant payment',
                    email,
                    contact,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                FROM customers
                WHERE customer_id = ?
                """,
                (
                    payment_id,
                    order_id,
                    customer_id,
                    amount,
                    method,
                    random.choice([0, 1]),
                    details["bank"],
                    details["vpa"],
                    details["wallet"],
                    retry_count,
                    created_at,
                    created_at,
                    customer_id,
                ),
            )

            create_payment_attempt(
                connection,
                payment_id,
                1,
                amount,
                method,
                "captured",
                created_at,
            )

            payload = {
                "entity": "event",
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {
                            "id": payment_id,
                            "entity": "payment",
                            "amount": amount,
                            "currency": "INR",
                            "status": "captured",
                            "order_id": order_id,
                            "method": method,
                            "captured": True,
                        }
                    }
                },
            }

            create_payment_event(
                connection,
                payment_id,
                "payment.captured",
                payload,
                created_at,
            )

            continue
        # -----------------------------------------------------------
        # Failed payment
        # -----------------------------------------------------------

        failure = choose_failure()

        details = payment_method_details(method)

        retry_count = random.randint(0, 2)

        cursor.execute(
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
                error_code,
                error_description,
                error_source,
                error_step,
                error_reason,
                bank,
                vpa,
                wallet,
                retry_count,
                created_at,
                updated_at
            )
            SELECT
                ?,
                ?,
                ?,
                'payment',
                ?,
                'INR',
                'failed',
                ?,
                0,
                ?,
                'Synthetic failed payment',
                email,
                contact,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            FROM customers
            WHERE customer_id = ?
            """,
            (
                payment_id,
                order_id,
                customer_id,
                amount,
                method,
                random.choice([0, 1]),
                failure["error_code"],
                failure["error_description"],
                failure["error_source"],
                failure["error_step"],
                failure["error_reason"],
                details["bank"],
                details["vpa"],
                details["wallet"],
                retry_count,
                created_at,
                created_at,
                customer_id,
            ), 
        )
        create_payment_attempt(
            connection,
            payment_id,
            1,
            amount,
            method,
            "failed",
            created_at,
            failure,
        )
        payload = {
            "entity": "event",
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "entity": "payment",
                        "amount": amount,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": order_id,
                        "method": method,
                        "captured": False,
                        "error_code": failure["error_code"],
                        "error_description": failure[
                            "error_description"
                        ],
                        "error_source": failure["error_source"],
                        "error_step": failure["error_step"],
                        "error_reason": failure["error_reason"],
                    }
                }
            },
        }
        create_payment_event(
            connection,
            payment_id,
            "payment.failed",
            payload,
            created_at,
        )

    connection.commit()

# -------------------------------------------------------------------
# Subscriptions
# -------------------------------------------------------------------

def generate_subscriptions(
    connection: sqlite3.Connection,
    customer_ids: list[str],
) -> None:

    cursor = connection.cursor()

    sample_size = min(300, len(customer_ids))

    for customer_id in random.sample(
        customer_ids,
        k=sample_size,
    ):

        subscription_id = generate_id("sub")

        amount = int(
            round(random.uniform(499, 4999) * 100)
        )

        status = random.choices(
            [
                "active",
                "payment_failed",
            ],
            weights=[
                0.80,
                0.20,
            ],
        )[0]

        next_billing_date = (
            datetime.now()
            + timedelta(days=random.randint(1, 30))
        )

        failed_attempts = (
            random.randint(1, 3)
            if status == "payment_failed"
            else 0
        )
        cursor.execute(
            """
            INSERT INTO subscriptions (
                subscription_id,
                customer_id,
                amount,
                currency,
                status,
                next_billing_date,
                failed_attempts,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                customer_id,
                amount,
                "INR",
                status,
                int(next_billing_date.timestamp()),
                failed_attempts,
                int(datetime.now().timestamp()),
            ),
        )

    connection.commit()

# -------------------------------------------------------------------
# Invoices
# -------------------------------------------------------------------

def generate_invoices(
    connection: sqlite3.Connection,
    customer_ids: list[str],
) -> None:

    cursor = connection.cursor()

    sample_size = min(200, len(customer_ids))

    for customer_id in random.sample(
        customer_ids,
        k=sample_size,
    ):

        invoice_id = generate_id("inv")

        amount = int(
            round(random.uniform(5000, 100000) * 100)
        )
        status = random.choices(
            [
                "paid",
                "overdue",
            ],
            weights=[
                0.75,
                0.25,
            ],
        )[0]

        due_date = (
            datetime.now()
            - timedelta(days=random.randint(1, 30))
        )

        reminder_count = (
            random.randint(0, 3)
            if status == "overdue"
            else 0
        )
        cursor.execute(
            """
            INSERT INTO invoices (
                invoice_id,
                customer_id,
                amount,
                currency,
                status,
                due_date,
                reminder_count,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_id,
                customer_id,
                amount,
                "INR",
                status,
                int(due_date.timestamp()),
                reminder_count,
                int(datetime.now().timestamp()),
            ),
        )

    connection.commit()

# -------------------------------------------------------------------
# Customer statistics
# -------------------------------------------------------------------

def update_customer_statistics(
    connection: sqlite3.Connection,
) -> None:

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE customers
        SET
            successful_payments = (
                SELECT COUNT(*)
                FROM payments
                WHERE payments.customer_id = customers.customer_id
                AND payments.status = 'captured'
            ),

            failed_payments = (
                SELECT COUNT(*)
                FROM payments
                WHERE payments.customer_id = customers.customer_id
                AND payments.status = 'failed'
            ),
            lifetime_value_paise = COALESCE(
                (
                    SELECT SUM(amount)
                    FROM payments
                    WHERE payments.customer_id = customers.customer_id
                    AND payments.status = 'captured'
                ),
                0
            )
        """
    )

    connection.commit()

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def generate_dataset() -> None:

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    print("Creating database schema...")

    create_tables()

    connection = get_connection()

    print("Generating customers...")

    customer_ids = generate_customers(
        connection,
        NUM_CUSTOMERS,
    )

    print("Generating orders...")

    orders = generate_orders(
        connection,
        customer_ids,
        NUM_ORDERS,
    )

    print("Generating payments...")

    generate_payments(
        connection,
        orders,
    )

    print("Generating subscriptions...")

    generate_subscriptions(
        connection,
        customer_ids,
    )

    print("Generating invoices...")

    generate_invoices(
        connection,
        customer_ids,
    )

    print("Updating customer statistics...")

    update_customer_statistics(
        connection,
    )

    connection.close()

    print()
    print("=" * 60)
    print("Synthetic merchant environment created successfully.")
    print(f"Database: {DATABASE_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    generate_dataset()

