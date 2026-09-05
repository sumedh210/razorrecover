import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/processed/merchant.db")


def check_table_counts(connection: sqlite3.Connection) -> None:
    """Check that the expected tables exist and contain data."""

    expected_tables = [
        "customers",
        "orders",
        "payments",
        "payment_attempts",
        "payment_events",
        "subscriptions",
        "invoices",
        "recovery_actions",
    ]

    cursor = connection.cursor()

    existing_tables = {
        row[0]
        for row in cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    print("\n[1] TABLE CHECK")

    for table in expected_tables:
        if table not in existing_tables:
            print(f"  ❌ Missing table: {table}")
            continue

        count = cursor.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"  ✓ {table}: {count:,} rows")


def check_foreign_keys(connection: sqlite3.Connection) -> None:
    """Check for broken foreign-key relationships."""

    print("\n[2] FOREIGN KEY CHECK")

    cursor = connection.cursor()

    violations = cursor.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if violations:
        print(f"  ❌ {len(violations)} foreign-key violations")

        for violation in violations[:10]:
            print(f"     {violation}")

    else:
        print("  ✓ No foreign-key violations")


def check_payment_status_consistency(
    connection: sqlite3.Connection,
) -> None:
    """Validate basic payment state invariants."""

    print("\n[3] PAYMENT STATE CHECK")

    cursor = connection.cursor()

    # Captured payments must have captured = 1.
    invalid_captured = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'captured'
        AND captured != 1
        """
    ).fetchone()[0]

    if invalid_captured:
        print(
            f"  ❌ {invalid_captured} captured payments "
            "have captured != 1"
        )
    else:
        print("  ✓ Captured payments are consistent")

    # Failed payments must have captured = 0.
    invalid_failed = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'failed'
        AND captured != 0
        """
    ).fetchone()[0]

    if invalid_failed:
        print(
            f"  ❌ {invalid_failed} failed payments "
            "have captured != 0"
        )
    else:
        print("  ✓ Failed payments are consistent")

    # Failed payments should contain failure information.
    missing_failure_info = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'failed'
        AND (
            error_code IS NULL
            OR error_source IS NULL
            OR error_step IS NULL
            OR error_reason IS NULL
        )
        """
    ).fetchone()[0]

    if missing_failure_info:
        print(
            f"  ❌ {missing_failure_info} failed payments "
            "are missing failure information"
        )
    else:
        print(
            "  ✓ Failed payments contain failure information"
        )


def check_payment_attempts(
    connection: sqlite3.Connection,
) -> None:
    """Check payment-to-attempt relationships."""

    print("\n[4] PAYMENT ATTEMPT CHECK")

    cursor = connection.cursor()

    orphan_attempts = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payment_attempts pa
        LEFT JOIN payments p
            ON pa.payment_id = p.payment_id
        WHERE p.payment_id IS NULL
        """
    ).fetchone()[0]

    if orphan_attempts:
        print(
            f"  ❌ {orphan_attempts} orphan payment attempts"
        )
    else:
        print("  ✓ All attempts belong to valid payments")

    # Every payment should have at least one attempt.
    payments_without_attempts = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments p
        LEFT JOIN payment_attempts pa
            ON p.payment_id = pa.payment_id
        WHERE pa.payment_id IS NULL
        """
    ).fetchone()[0]

    if payments_without_attempts:
        print(
            f"  ❌ {payments_without_attempts} payments "
            "have no attempts"
        )
    else:
        print("  ✓ Every payment has at least one attempt")


def check_payment_events(
    connection: sqlite3.Connection,
) -> None:
    """Check payment event relationships."""

    print("\n[5] PAYMENT EVENT CHECK")

    cursor = connection.cursor()

    orphan_events = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payment_events pe
        LEFT JOIN payments p
            ON pe.payment_id = p.payment_id
        WHERE p.payment_id IS NULL
        """
    ).fetchone()[0]

    if orphan_events:
        print(
            f"  ❌ {orphan_events} orphan payment events"
        )
    else:
        print("  ✓ All events belong to valid payments")


def check_customer_statistics(
    connection: sqlite3.Connection,
) -> None:
    """Verify customer payment statistics."""

    print("\n[6] CUSTOMER STATISTICS CHECK")

    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT
            c.customer_id,
            c.successful_payments,
            c.failed_payments,
            c.lifetime_value_paise,

            (
                SELECT COUNT(*)
                FROM payments p
                WHERE p.customer_id = c.customer_id
                AND p.status = 'captured'
            ) AS actual_successful,

            (
                SELECT COUNT(*)
                FROM payments p
                WHERE p.customer_id = c.customer_id
                AND p.status = 'failed'
            ) AS actual_failed,

            COALESCE(
                (
                    SELECT SUM(p.amount)
                    FROM payments p
                    WHERE p.customer_id = c.customer_id
                    AND p.status = 'captured'
                ),
                0
            ) AS actual_lifetime_value

        FROM customers c
        """
    ).fetchall()

    errors = 0

    for row in rows:

        if row["successful_payments"] != row["actual_successful"]:
            errors += 1

        if row["failed_payments"] != row["actual_failed"]:
            errors += 1

        if row["lifetime_value_paise"] != row[
            "actual_lifetime_value"
        ]:
            errors += 1

    if errors:
        print(
            f"  ❌ Found {errors} customer statistic mismatches"
        )
    else:
        print(
            "  ✓ Customer payment statistics are consistent"
        )


def check_payment_event_distribution(
    connection: sqlite3.Connection,
) -> None:
    """Check whether payment events match payment states."""

    print("\n[7] EVENT DISTRIBUTION CHECK")

    cursor = connection.cursor()

    failed_payments = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'failed'
        """
    ).fetchone()[0]

    failed_events = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payment_events
        WHERE event_type = 'payment.failed'
        """
    ).fetchone()[0]

    captured_payments = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'captured'
        """
    ).fetchone()[0]

    captured_events = cursor.execute(
        """
        SELECT COUNT(*)
        FROM payment_events
        WHERE event_type = 'payment.captured'
        """
    ).fetchone()[0]

    print(
        f"  Failed payments: {failed_payments:,}"
    )
    print(
        f"  payment.failed events: {failed_events:,}"
    )

    print(
        f"  Captured payments: {captured_payments:,}"
    )
    print(
        f"  payment.captured events: {captured_events:,}"
    )

    if failed_payments == failed_events:
        print("  ✓ Failed payment events match")

    else:
        print(
            "  ⚠ Failed payment/event counts differ"
        )

    if captured_payments == captured_events:
        print("  ✓ Captured payment events match")

    else:
        print(
            "  ⚠ Captured payment/event counts differ"
        )


def run_validation() -> None:

    print("=" * 60)
    print("SYNTHETIC MERCHANT DATABASE SANITY CHECK")
    print("=" * 60)

    if not DATABASE_PATH.exists():
        print(
            f"\n❌ Database not found: {DATABASE_PATH}"
        )
        return

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    try:

        check_table_counts(connection)

        check_foreign_keys(connection)

        check_payment_status_consistency(connection)

        check_payment_attempts(connection)

        check_payment_events(connection)

        check_customer_statistics(connection)

        check_payment_event_distribution(connection)

    finally:

        connection.close()

    print("\n" + "=" * 60)
    print("SANITY CHECK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_validation()