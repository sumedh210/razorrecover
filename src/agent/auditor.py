import sqlite3
import time
from pathlib import Path
from typing import Any

from loguru import logger

from src.agent.state import AgentState


DATABASE_PATH = Path("data/processed/merchant_tuned.db")


def ensure_audit_table() -> None:
    """Create the audit table if it does not already exist."""

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL,
                proposed_action TEXT,
                policy_decision TEXT,
                policy_allowed INTEGER,
                executed_action TEXT,
                before_status TEXT,
                after_status TEXT,
                amount REAL,
                recovered_amount REAL,
                recovered INTEGER,
                compliance_status TEXT NOT NULL,
                audit_reason TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )

        connection.commit()


def audit_payment(state: AgentState) -> AgentState:
    """
    Deterministically verify the recovery decision and outcome.

    The auditor does not make recovery decisions.
    It only verifies what happened against the policy decision.
    """

    ensure_audit_table()

    payment = state.get("payment") or {}
    final_payment = state.get("final_payment") or payment
    action_result = state.get("action_result") or {}

    payment_id = str(
        state.get("payment_id")
        or payment.get("payment_id")
        or ""
    )

    proposed_action = str(
        state.get("proposed_action")
        or "UNKNOWN"
    )

    policy_decision = str(
        state.get("policy_decision")
        or "UNKNOWN"
    )

    policy_allowed = bool(
        state.get("policy_allowed", False)
    )

    before_status = str(
        payment.get("status")
        or "unknown"
    ).lower()

    after_status = str(
        final_payment.get("status")
        or before_status
    ).lower()

    amount = float(
        final_payment.get("amount")
        or payment.get("amount")
        or 0
    )

    recovered = bool(
        state.get("recovered", False)
    )

    recovered_amount = float(
        state.get("recovered_amount", 0)
        or 0
    )

    # ---------------------------------------------------------
    # Determine what was actually executed
    # ---------------------------------------------------------

    executed_action = str(
        action_result.get("action")
        or "NONE"
    ).upper()

    # If policy stopped execution, nothing was executed.
    if not action_result:
        executed_action = "NONE"

    # ---------------------------------------------------------
    # Compliance checks
    # ---------------------------------------------------------

    compliance_status = "COMPLIANT"
    audit_reason = "Recovery flow followed the policy decision."

    # Policy allowed an action → that exact action should execute.
    if policy_allowed:

        if executed_action != policy_decision:
            compliance_status = "NON_COMPLIANT"

            audit_reason = (
                f"Policy allowed {policy_decision}, "
                f"but executed action was {executed_action}."
            )

    # Policy denied the proposed action and replaced it
    # with a safe alternative.
    elif policy_decision not in {"STOP", "ESCALATE"}:

        if executed_action != policy_decision:
            compliance_status = "NON_COMPLIANT"

            audit_reason = (
                f"Policy selected safe replacement {policy_decision}, "
                f"but executed action was {executed_action}."
            )
        else:
            audit_reason = (
                f"Proposed action {proposed_action} was blocked; "
                f"policy selected safe alternative {policy_decision}, "
                f"which was executed."
            )

    # ESCALATE is intentionally executable even when policy_allowed
    # is False.
    elif policy_decision == "ESCALATE":

        if executed_action != "ESCALATE":
            compliance_status = "NON_COMPLIANT"

            audit_reason = (
                "Policy required escalation, but escalation "
                f"was not executed. Executed={executed_action}."
            )
        else:
            audit_reason = (
                "Payment was correctly escalated according to policy."
            )

    # STOP means absolutely no recovery action should execute.
    elif policy_decision == "STOP":

        if executed_action != "NONE":
            compliance_status = "NON_COMPLIANT"

            audit_reason = (
                "Policy required the payment to stop, "
                f"but {executed_action} was executed."
            )
        else:
            audit_reason = (
                "Payment correctly stopped by policy."
            )

    # ---------------------------------------------------------
    # Revenue sanity check
    # ---------------------------------------------------------

    if recovered and recovered_amount <= 0:

        compliance_status = "NON_COMPLIANT"

        audit_reason = (
            "Payment is marked recovered but recovered amount "
            "is zero."
        )

    if not recovered and recovered_amount > 0:

        compliance_status = "NON_COMPLIANT"

        audit_reason = (
            "Payment is not recovered but recovered amount "
            "is greater than zero."
        )

    # Never allow recovered amount to exceed payment amount.
    if recovered_amount > amount:

        compliance_status = "NON_COMPLIANT"

        audit_reason = (
            f"Recovered amount ({recovered_amount}) exceeds "
            f"payment amount ({amount})."
        )

    # ---------------------------------------------------------
    # Store audit event
    # ---------------------------------------------------------

    created_at = int(time.time())

    with sqlite3.connect(DATABASE_PATH) as connection:

        connection.execute(
            """
            INSERT INTO audit_events (
                payment_id,
                proposed_action,
                policy_decision,
                policy_allowed,
                executed_action,
                before_status,
                after_status,
                amount,
                recovered_amount,
                recovered,
                compliance_status,
                audit_reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_id,
                proposed_action,
                policy_decision,
                int(policy_allowed),
                executed_action,
                before_status,
                after_status,
                amount,
                recovered_amount,
                int(recovered),
                compliance_status,
                audit_reason,
                created_at,
            ),
        )

        connection.commit()

    audit_event = {
        "payment_id": payment_id,
        "proposed_action": proposed_action,
        "policy_decision": policy_decision,
        "policy_allowed": policy_allowed,
        "executed_action": executed_action,
        "before_status": before_status,
        "after_status": after_status,
        "amount": amount,
        "recovered_amount": recovered_amount,
        "recovered": recovered,
        "compliance_status": compliance_status,
        "audit_reason": audit_reason,
        "created_at": created_at,
    }

    state["audit_events"] = state.get("audit_events", [])
    state["audit_events"].append(audit_event)

    logger.info(
        "Audit completed | payment_id={} | compliance={} | "
        "executed={} | recovered={}",
        payment_id,
        compliance_status,
        executed_action,
        recovered,
    )

    return state