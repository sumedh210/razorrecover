import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("data/processed/merchant_tuned.db")


def evaluate_simulation(payment_ids: list[str]) -> dict[str, Any]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        placeholders = ",".join("?" for _ in payment_ids)

        rows = connection.execute(
            f"""
            SELECT
                payment_id,
                amount,
                status,
                captured,
                error_source,
                error_reason,
                retry_count
            FROM payments
            WHERE payment_id IN ({placeholders})
            """,
            payment_ids,
        ).fetchall()

        payments = [dict(row) for row in rows]

        total_payments = len(payments)

        recovered_payments = [
            payment
            for payment in payments
            if payment["status"].lower()
            in {"captured", "paid", "success", "successful"}
        ]

        failed_payments = [
            payment
            for payment in payments
            if payment["payment_id"]
            not in {
                p["payment_id"]
                for p in recovered_payments
            }
        ]

        total_amount = sum(
            float(payment["amount"])
            for payment in payments
        )

        recovered_amount = sum(
            float(payment["amount"])
            for payment in recovered_payments
        )

        recovery_rate = (
            len(recovered_payments) / total_payments
            if total_payments
            else 0
        )

        revenue_recovery_rate = (
            recovered_amount / total_amount
            if total_amount
            else 0
        )

        action_rows = connection.execute(
            f"""
            SELECT
                action_type,
                status,
                COUNT(*) AS count
            FROM recovery_actions
            WHERE entity_type = 'payment'
              AND entity_id IN ({placeholders})
            GROUP BY action_type, status
            ORDER BY action_type, status
            """,
            payment_ids,
        ).fetchall()

        actions = [
            dict(row)
            for row in action_rows
        ]

        rule_rows = connection.execute(
            f"""
            SELECT
                rule_id,
                COUNT(*) AS count
            FROM recovery_actions
            WHERE entity_type = 'payment'
              AND entity_id IN ({placeholders})
              AND rule_id IS NOT NULL
            GROUP BY rule_id
            ORDER BY count DESC
            """,
            payment_ids,
        ).fetchall()

        policy_rules = [
            dict(row)
            for row in rule_rows
        ]

        return {
            "total_payments": total_payments,
            "recovered_payments": len(recovered_payments),
            "not_recovered": len(failed_payments),
            "total_amount": total_amount,
            "recovered_amount": recovered_amount,
            "recovery_rate": recovery_rate,
            "revenue_recovery_rate": revenue_recovery_rate,
            "actions": actions,
            "policy_rules": policy_rules,
        }

    finally:
        connection.close()


def print_report(metrics: dict[str, Any]) -> None:

    print("\n")
    print("=" * 70)
    print("REVENUE RECOVERY SIMULATION")
    print("=" * 70)

    print(f"Payments processed:    {metrics['total_payments']}")
    print(f"Payments recovered:    {metrics['recovered_payments']}")
    print(f"Payments not recovered:{metrics['not_recovered']}")

    print()

    print(
        f"Total failed amount:   "
        f"{metrics['total_amount']:,.2f}"
    )

    print(
        f"Amount recovered:      "
        f"{metrics['recovered_amount']:,.2f}"
    )

    print(
        f"Recovery rate:         "
        f"{metrics['recovery_rate'] * 100:.2f}%"
    )

    print(
        f"Revenue recovery rate: "
        f"{metrics['revenue_recovery_rate'] * 100:.2f}%"
    )

    print("\n" + "-" * 70)
    print("ACTIONS")
    print("-" * 70)

    for action in metrics["actions"]:
        print(
            f"{action['action_type']:25}"
            f"{action['status']:15}"
            f"{action['count']}"
        )

    print("\n" + "-" * 70)
    print("POLICY RULES")
    print("-" * 70)

    for rule in metrics["policy_rules"]:
        print(
            f"{rule['rule_id']:30}"
            f"{rule['count']}"
        )

    print("=" * 70)