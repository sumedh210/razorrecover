import json
import time
import random
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable

DATABASE_PATH = Path("data/processed/merchant_tuned.db")

def _get_connection() ->sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def _generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

def _timestamp() -> int:
    return int(time.time())

def _record_event( connection: sqlite3.Connection, payment_id: str, event_type: str, payload: dict[str, Any],) -> None:
    connection.execute(
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
            _generate_id("event"),
            payment_id,
            event_type,
            _timestamp(),
            json.dumps(payload)
        )
    )

def _record_recovery_action(
        connection: sqlite3.Connection, payment_id: str, action_type: str, reason: str, status: str
)-> None:
    connection.execute(
        """
        INSERT INTO recovery_actions (
            action_id,
            entity_type,
            entity_id,
            action_type,
            reason,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
         _generate_id("action"),
            "payment",
            payment_id,
            action_type,
            reason,
            status,
            _timestamp(),   
        )
    )

def _get_payment_row(
        connection: sqlite3.Connection,
        payment_id: str
):
    return connection.execute(
        """
        SELECT*
        FROM payments
        WHERE payment_id = ?
        """,
        (payment_id,)
    ).fetchone()

def get_payment(payment_id: str) -> dict[str, Any]:
    connection = _get_connection()

    try:
        row = connection.execute("""
            SELECT *
            FROM payments
            WHERE payment_id = ?
            """,
            (payment_id,),
        ).fetchone()

        if row is None:
            return {
                "success": False,
                "error": f"Payment {payment_id} not found.",
            }
        return {
            "success": True,
            "payment": dict(row),
        }
    finally:
        connection.close()

def retry_payment(payment_id: str) -> dict[str, Any]:
    connection = _get_connection()
    try:
        row = _get_payment_row(connection, payment_id)

        if row is None:
            return {
                "success":False,
                "error": f"Payment {payment_id} not found"
            }

        payment = dict(row)

        if payment["status"] != "failed":
            return {
                "success": False,
                "error": (
                    f"Payment is not retryable. "
                    f"Current status: {payment['status']}"
                ),
            }

        current_retry_count = payment["retry_count"] + 1

        if current_retry_count > 2:
            return {
                "success": False,
                "error": "Maximum retry limit reached"
            }
            
        attempt_number = current_retry_count + 1

        # Simulate recovery outcome



        recovery_probability = {
            "gateway_technical_error": 0.75,
            "payment_timed_out": 0.70,
            "payment_failed": 0.55,
        }.get(
            payment["error_reason"],
            0.40
        )
        recovered = random.random() < recovery_probability

        timestamp = _timestamp()

        if recovered:
            new_status = "captured"

            connection.execute(
                """
                UPDATE payments
                SET
                    status = 'captured',
                    captured = 1,
                    retry_count = ?,
                    updated_at = ?
                WHERE payment_id = ?
                """,
                (
                    attempt_number,
                    timestamp,
                    payment_id,
                ),
            )
            attempt_status = "captured"

            _record_event(connection, 
                          payment_id,
                          "payment.captured",
                          {
                              "action": "RETRY_PAYMENT",
                              "attempt_number": attempt_number,
                              "result": "recovered",
                          },
                        )
            result = "recovered"

        
        else:
            new_status = "failed"
            connection.execute(
                """
                UPDATE payments
                SET
                    retry_count = ?,
                    updated_at = ?
                WHERE payment_id = ?
                """,
                (
                    attempt_number,
                    timestamp,
                    payment_id,
                ),
            )
            attempt_status = "failed"
            _record_event(
                connection,
                payment_id,
                "payment.failed",
                {
                    "action": "RETRY_PAYMENT",
                    "attempt_number": attempt_number,
                    "result": "failed",
                },
            )

            result = "failed"

        # Record attempt

        connection.execute(
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
                _generate_id("attempt"),
                payment_id,
                attempt_number,
                attempt_status,
                payment["method"],
                int(payment["amount"]),
                None if recovered else payment["error_code"],
                None if recovered else payment["error_description"],
                None if recovered else payment["error_source"],
                None if recovered else payment["error_step"],
                None if recovered else payment["error_reason"],
                payment["bank"],
                payment["vpa"],
                timestamp,
            ),
        )
        _record_recovery_action(
            connection,
            payment_id,
            "RETRY_PAYMENT",
            payment["error_reason"],
            result,
        )

        connection.commit()

        return {
            "success": True,
            "payment_id": payment_id,
            "action": "RETRY_PAYMENT",
            "attempt_number": attempt_number,
            "result": result,
            "recovered": recovered,
            "recovered_amount": (
                payment["amount"]
                if recovered
                else 0
            ),
        }
    finally:
        connection.close()
        

def route_payment(payment_id: str)-> dict[str, Any]:

    connection = _get_connection()

    try:
        row = _get_payment_row(connection, payment_id)

        if row is None:
            return {
                "success": False,
                "error": f"Payment {payment_id} not found.",
            }
        payment = dict(row)

        if payment["status"] != "failed":
            return{
                "success": False,
                "error": "Only failed payments can be routed.",
            }
        if not payment.get("bank"):
            return {
                "success": False,
                "error": "No bank information available.",
            }

        recovered = random.random() < 0.65

        timestamp = _timestamp()

        if recovered:
            connection.execute(
                """
                UPDATE payments
                SET
                    status = 'captured',
                    captured = 1,
                    updated_at = ?
                WHERE payment_id = ?
                """,
                (
                    timestamp,
                    payment_id,
                ),
            )

            result = "recovered"

            _record_event(
                connection,
                payment_id,
                "payment.captured",
                {
                    "action": "ROUTE_PAYMENT",
                    "result": "recovered",
                },
            )
        else:

            result = "failed"

            _record_event(
                connection,
                payment_id,
                "payment.failed",
                {
                    "action": "ROUTE_PAYMENT",
                    "result": "failed",
                },
            )

        _record_recovery_action(
            connection,
            payment_id,
            "ROUTE_PAYMENT",
            payment["error_reason"],
            result,
        )

        connection.commit()

        return {
            "success": True,
            "payment_id": payment_id,
            "action": "ROUTE_PAYMENT",
            "result": result,
            "recovered": recovered,
            "recovered_amount": (
                payment["amount"]
                if recovered
                else 0
            ),
        }
    finally:
        connection.close()

# SEND RECOVERY LINK

def send_recovery_link(payment_id: str,) -> dict[str, Any]:
    connection = _get_connection()

    try:
        row = _get_payment_row(
            connection,
            payment_id,
        )
        if row is None:
            return {
                "success": False,
                "error": f"Payment {payment_id} not found.",
            }

        payment = dict(row)

        if payment["status"] != "failed":
            return {
                "success": False,
                "error": (
                    "Recovery link only applies "
                    "to failed payments."
                ),
            }

        # Sending the link itself is successful.
        # Customer conversion is simulated separately.
        recovered = random.random() < 0.60

        timestamp = _timestamp()

        if recovered:

            connection.execute(
                """
                UPDATE payments
                SET
                    status = 'captured',
                    captured = 1,
                    updated_at = ?
                WHERE payment_id = ?
                """,
                (
                    timestamp,
                    payment_id,
                ),
            )

            result = "recovered"

            event_type = "payment.captured"

        else:

            result = "pending"

            event_type = "recovery_link.sent"

        _record_event(
            connection,
            payment_id,
            event_type,
            {
                "action": "SEND_RECOVERY_LINK",
                "result": result,
            },
        )

        _record_recovery_action(
            connection,
            payment_id,
            "SEND_RECOVERY_LINK",
            payment["error_reason"],
            result,
        )

        connection.commit()

        return {
            "success": True,
            "payment_id": payment_id,
            "action": "SEND_RECOVERY_LINK",
            "result": result,
            "recovered": recovered,
            "recovered_amount": (
                payment["amount"]
                if recovered
                else 0
            ),
        }

    finally:
        connection.close()

# ESCALATE

def escalate_payment(payment_id: str, reason: str) -> dict[str, Any]:
    connection = _get_connection()

    try:
        row = _get_payment_row(
            connection,
            payment_id,
        )

        if row is None:
            return {
                "success": False,
                "error": f"Payment {payment_id} not found.",
            }

        timestamp = _timestamp()

        _record_recovery_action(
            connection,
            payment_id,
            "ESCALATE",
            reason,
            "escalated",
        )

        _record_event(
            connection,
            payment_id,
            "payment.escalated",
            {
                "reason": reason,
            },
        )

        connection.commit()

        return {
            "success": True,
            "payment_id": payment_id,
            "action": "ESCALATE",
            "result": "escalated",
            "recovered": False,
            "recovered_amount": 0,
        }

    finally:
        connection.close()

def create_rag_tool(rag_orchestrator):


    def search_recovery_knowledge(query: str) -> str:
        
        return rag_orchestrator.run(query)

    return search_recovery_knowledge