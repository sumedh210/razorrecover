import sqlite3
from pathlib import Path
from typing import Any, cast

from src.agent.bootstrap import build_agent


DATABASE_PATH = Path("data/processed/merchant_tuned.db")


def get_payment(payment_id: str) -> dict:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM payments
            WHERE payment_id = ?
            """,
            (payment_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError(f"Payment not found: {payment_id}")

    return dict(row)


def print_payment(payment: dict) -> None:
    print("\n" + "=" * 60)
    print("PAYMENT")
    print("=" * 60)

    print(f"Payment ID : {payment['payment_id']}")
    print(f"Amount     : ₹{payment['amount']:,.2f}")
    print(f"Status     : {payment['status']}")
    print(f"Method     : {payment['method']}")
    print(f"Failure    : {payment['error_reason']}")
    print(f"Retries    : {payment['retry_count']}")


def print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("RAZORRECOVER DECISION")
    print("=" * 60)

    print("\n[AI AGENT]")
    print(f"Diagnosis  : {result.get('diagnosis')}")
    print(
        f"Confidence : "
        f"{result.get('diagnosis_confidence', 0):.2f}"
    )
    print(f"Proposed   : {result.get('proposed_action')}")

    print("\n[POLICY ENGINE]")
    print(f"Decision   : {result.get('policy_decision')}")
    print(f"Allowed    : {result.get('policy_allowed')}")
    print(f"Reason     : {result.get('policy_reason')}")

    action_result = result.get("action_result") or {}

    print("\n[MCP EXECUTION]")
    print(f"Action     : {action_result.get('action', 'NONE')}")
    print(f"Status     : {action_result.get('status', 'NONE')}")

    final_payment = result.get("final_payment") or {}

    print("\n[OUTCOME]")
    print(f"Payment    : {final_payment.get('status')}")
    print(f"Recovered  : {result.get('recovered')}")
    print(
        f"Amount     : "
        f"₹{result.get('recovered_amount', 0):,.2f}"
    )

    audit_events = result.get("audit_events") or []

    if audit_events:
        audit = audit_events[-1]

        print("\n[AUDITOR]")
        print(
            f"Compliance : "
            f"{audit.get('compliance_status')}"
        )
        print(f"Audit      : {audit.get('audit_reason')}")

    print("\n" + "=" * 60)


def choose_payment() -> str:
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  RAZORRECOVER DEMO                       ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  1. Transient Failure  → Retry                           ║")
    print("║  2. Authentication     → Recovery Link                   ║")
    print("║  3. High-Value         → Escalate                        ║")
    print("║  4. Exit                                                 ║")
    print("╚══════════════════════════════════════════════════════════╝")

    choice = input("\nSelect scenario: ").strip()

    if choice == "4":
        raise SystemExit

    if choice not in {"1", "2", "3"}:
        print("Invalid choice.")
        return choose_payment()

    payment_ids = {
        "1": "DEMO_TRANSIENT_*",
        "2": "DEMO_AUTH_*",
        "3": "DEMO_HIGH_VALUE_*",
    }

    return payment_ids[choice]


def main() -> None:
    print("\nInitializing RazorRecover...")
    print("Loading RAG, classifier, reranker, agent and policy engine...\n")

    agent = build_agent()

    print("\nRazorRecover ready.")

    while True:
        try:
            payment_id = choose_payment()

            payment = get_payment(payment_id)

            print_payment(payment)

            print("\nRunning recovery agent...")

            result = agent.invoke(
                cast(Any, {
                    "payment_id": payment_id,
                })
            )

            print_result(result)

            input("\nPress ENTER to return to the demo menu...")

        except KeyboardInterrupt:
            print("\n\nDemo stopped.")
            break

        except Exception as exc:
            print("\nERROR")
            print("-" * 60)
            print(exc)
            print("-" * 60)


if __name__ == "__main__":
    main()