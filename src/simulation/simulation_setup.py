import json
import random
import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("data/processed/merchant_tuned.db")
BACKUP_PATH = Path("data/processed/simulation_backup.json")

SIMULATION_SIZE = 100
RANDOM_SEED = 42


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


def select_payments(
    connection: sqlite3.Connection,
    count: int,
) -> list[dict[str, Any]]:

    rows = connection.execute(
        """
        SELECT p.*
        FROM payments p
        LEFT JOIN recovery_actions r
            ON r.entity_type = 'payment'
            AND r.entity_id = p.payment_id
        WHERE r.action_id IS NULL
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (count,),
    ).fetchall()

    return [dict(row) for row in rows]


def backup_payments(
    connection: sqlite3.Connection,
    payments: list[dict[str, Any]],
) -> None:

    payment_ids = [payment["payment_id"] for payment in payments]

    attempts = []

    for payment_id in payment_ids:
        rows = connection.execute(
            """
            SELECT *
            FROM payment_attempts
            WHERE payment_id = ?
            """,
            (payment_id,),
        ).fetchall()

        attempts.extend(dict(row) for row in rows)

    backup = {
        "payments": payments,
        "payment_attempts": attempts,
    }

    BACKUP_PATH.write_text(
        json.dumps(backup, indent=2),
        encoding="utf-8",
    )


def prepare_simulation() -> None:

    random.seed(RANDOM_SEED)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        # ---------------------------------------------------------
        # Select simulation payments
        # ---------------------------------------------------------

        payments = select_payments(
            connection,
            SIMULATION_SIZE,
        )

        if len(payments) < SIMULATION_SIZE:
            raise RuntimeError(
                f"Only found {len(payments)} suitable payments. "
                f"Need {SIMULATION_SIZE}."
            )

        payment_ids = [
            payment["payment_id"]
            for payment in payments
        ]

        print(f"Selected {len(payment_ids)} payments.")

        # ---------------------------------------------------------
        # Backup original state
        # ---------------------------------------------------------

        backup_payments(
            connection,
            payments,
        )

        print(f"Backup created at: {BACKUP_PATH}")

        # ---------------------------------------------------------
        # Prepare failures
        # ---------------------------------------------------------

        distribution = {}

        for payment_id in payment_ids:

            failure = random.choice(FAILURE_TYPES)

            retry_count = random.randint(0, 2)

            connection.execute(
                """
                UPDATE payments
                SET
                    status = 'failed',
                    captured = 0,
                    error_source = ?,
                    error_reason = ?,
                    retry_count = ?,
                    updated_at = strftime('%s', 'now')
                WHERE payment_id = ?
                """,
                (
                    failure["error_source"],
                    failure["error_reason"],
                    retry_count,
                    payment_id,
                ),
            )

            # Remove previous attempts.
            connection.execute(
                """
                DELETE FROM payment_attempts
                WHERE payment_id = ?
                """,
                (payment_id,),
            )

            # Remove previous recovery actions.
            connection.execute(
                """
                DELETE FROM recovery_actions
                WHERE entity_type = 'payment'
                  AND entity_id = ?
                """,
                (payment_id,),
            )

            key = (
                failure["error_source"],
                failure["error_reason"],
            )

            distribution[key] = distribution.get(key, 0) + 1

        connection.commit()

        # ---------------------------------------------------------
        # Print exact simulation distribution
        # ---------------------------------------------------------

        print("\nSimulation prepared successfully.")
        print("-" * 65)

        for (source, reason), count in sorted(distribution.items()):
            print(
                f"{source:10} | "
                f"{reason:30} | "
                f"{count:3}"
            )

        print("-" * 65)
        print(f"Total: {sum(distribution.values())}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    prepare_simulation()