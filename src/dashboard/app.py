import sqlite3
from pathlib import Path

from nicegui import ui


DATABASE_PATH = Path("data/processed/merchant_tuned.db")
REFRESH_INTERVAL = 3


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_metrics():

    connection = get_connection()

    try:
        total_payments = connection.execute(
            """
            SELECT COUNT(*)
            FROM payments
            """
        ).fetchone()[0]

        failed_payments = connection.execute(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status = 'failed'
            """
        ).fetchone()[0]

        captured_payments = connection.execute(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status = 'captured'
            """
        ).fetchone()[0]

        revenue_at_risk = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE status = 'failed'
            """
        ).fetchone()[0]

        recovered_payments = connection.execute(
            """
            SELECT COUNT(DISTINCT p.payment_id)
            FROM payments p
            JOIN recovery_actions r
                ON r.entity_id = p.payment_id
            WHERE r.entity_type = 'payment'
              AND p.status = 'captured'
            """
        ).fetchone()[0]

        revenue_recovered = connection.execute(
            """
            SELECT COALESCE(SUM(p.amount), 0)
            FROM payments p
            WHERE p.status = 'captured'
              AND EXISTS (
                  SELECT 1
                  FROM recovery_actions r
                  WHERE r.entity_type = 'payment'
                    AND r.entity_id = p.payment_id
            )
            """
        ).fetchone()[0]

        escalated = connection.execute(
            """
            SELECT COUNT(*)
            FROM recovery_actions
            WHERE entity_type = 'payment'
              AND LOWER(action_type) = 'escalate'
            """
        ).fetchone()[0]

        recovery_rate = (
            recovered_payments / (
                recovered_payments + failed_payments
            ) * 100
            if recovered_payments + failed_payments > 0
            else 0
        )

        return {
            "total_payments": total_payments,
            "failed_payments": failed_payments,
            "captured_payments": captured_payments,
            "revenue_at_risk": revenue_at_risk,
            "revenue_recovered": revenue_recovered,
            "recovered_payments": recovered_payments,
            "escalated": escalated,
            "recovery_rate": recovery_rate,
        }

    finally:
        connection.close()


def get_audit_metrics():
    connection = get_connection()

    try:
        audited = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_events
            """
        ).fetchone()[0]

        compliant = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_events
            WHERE compliance_status = 'COMPLIANT'
            """
        ).fetchone()[0]

        violations = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_events
            WHERE compliance_status = 'NON_COMPLIANT'
            """
        ).fetchone()[0]

        compliance_rate = (
            compliant / audited * 100
            if audited > 0
            else 0
        )

        return {
            "audited": audited,
            "compliant": compliant,
            "violations": violations,
            "compliance_rate": compliance_rate,
        }

    finally:
        connection.close()


def get_recent_payments(limit=15):

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                p.payment_id,
                p.customer_id,
                COALESCE(c.name, p.customer_id) AS customer_name,
                p.amount,
                p.status,
                p.method,
                p.error_reason,
                p.retry_count,
                p.created_at
            FROM payments p
            LEFT JOIN customers c
                ON c.customer_id = p.customer_id
            ORDER BY p.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_recent_recovery_actions(limit=15):

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                r.action_id,
                r.entity_id AS payment_id,
                r.action_type,
                r.reason,
                r.status AS action_status,
                r.created_at,

                p.customer_id,
                COALESCE(c.name, p.customer_id) AS customer_name,
                p.amount,
                p.error_reason,
                p.status AS payment_status,
                p.retry_count,

                (
                    SELECT a.compliance_status
                    FROM audit_events a
                    WHERE a.payment_id = r.entity_id
                    ORDER BY a.audit_id DESC
                    LIMIT 1
                ) AS audit_status

            FROM recovery_actions r

            JOIN payments p
                ON p.payment_id = r.entity_id

            LEFT JOIN customers c
                ON c.customer_id = p.customer_id

            WHERE r.entity_type = 'payment'

            ORDER BY r.created_at DESC

            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()

def get_recent_audits(limit=15):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                a.audit_id,
                a.payment_id,
                a.proposed_action,
                a.policy_decision,
                a.executed_action,
                a.after_status,
                a.recovered,
                a.recovered_amount,
                a.compliance_status,
                a.audit_reason,
                a.created_at,

                p.customer_id,
                COALESCE(c.name, p.customer_id) AS customer_name,
                p.amount

            FROM audit_events a

            JOIN payments p
                ON p.payment_id = a.payment_id

            LEFT JOIN customers c
                ON c.customer_id = p.customer_id

            ORDER BY a.created_at DESC

            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()



# =========================================================
# FORMATTING
# =========================================================

def format_inr(amount):

    amount = float(amount)

    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.1f} Cr"

    if amount >= 100_000:
        return f"₹{amount / 100_000:.1f} L"

    if amount >= 1_000:
        return f"₹{amount / 1_000:.1f}K"

    return f"₹{amount:,.0f}"


def format_timestamp(timestamp):

    if not timestamp:
        return "-"

    from datetime import datetime

    try:
        return datetime.fromtimestamp(
            int(timestamp)
        ).strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return "-"


def action_name(action):

    if not action:
        return "-"

    return str(action).replace("_", " ").title()


# =========================================================
# PAGE
# =========================================================

ui.colors(
    primary="#6366f1",
    secondary="#64748b",
    accent="#22c55e",
    dark="#0f172a",
)

ui.query("body").classes("bg-slate-950")


# =========================================================
# HEADER
# =========================================================

with ui.header().classes(
    "bg-slate-900 border-b border-slate-800 px-8 py-4"
):

    with ui.row().classes(
        "w-full items-center justify-between"
    ):

        with ui.column().classes("gap-0"):

            ui.label(
                "Razor Recover"
            ).classes(
                "text-xl font-bold tracking-widest text-white"
            )

            ui.label(
                "AI-powered payment recovery system"
            ).classes(
                "text-xs text-slate-400"
            )

        with ui.row().classes(
            "items-center gap-2"
        ):

            ui.icon("circle").classes(
                "text-green-400 text-xs"
            )

            ui.label("LIVE").classes(
                "text-sm font-semibold text-green-400"
            )


# =========================================================
# MAIN
# =========================================================

with ui.column().classes(
    "w-full max-w-7xl mx-auto p-8 gap-6"
):

    with ui.column().classes("gap-1"):

        ui.label(
            "Recovery Overview"
        ).classes(
            "text-3xl font-bold text-white"
        )

        ui.label(
            "Real-time view of payment failures and recovered revenue"
        ).classes(
            "text-sm text-slate-400"
        )


    # =====================================================
    # PRIMARY METRICS
    # =====================================================

    with ui.row().classes("w-full gap-4"):

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("PAYMENTS PROCESSED").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            total_label = ui.label("0").classes(
                "text-3xl font-bold text-white mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("REVENUE AT RISK").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            risk_label = ui.label("₹0").classes(
                "text-3xl font-bold text-orange-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("REVENUE RECOVERED").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            recovered_label = ui.label("₹0").classes(
                "text-3xl font-bold text-green-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("RECOVERY RATE").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            rate_label = ui.label("0%").classes(
                "text-3xl font-bold text-indigo-400 mt-2"
            )


    # =====================================================
    # SECONDARY METRICS
    # =====================================================

    with ui.row().classes("w-full gap-4"):

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("FAILED PAYMENTS").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            failed_label = ui.label("0").classes(
                "text-2xl font-bold text-red-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("SUCCESSFUL RECOVERIES").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            recovery_label = ui.label("0").classes(
                "text-2xl font-bold text-green-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("ESCALATED").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            escalated_label = ui.label("0").classes(
                "text-2xl font-bold text-yellow-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("CAPTURED PAYMENTS").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )
            captured_label = ui.label("0").classes(
                "text-2xl font-bold text-blue-400 mt-2"
            )

    # =====================================================
    # AUDIT METRICS
    # =====================================================

    with ui.row().classes("w-full gap-4"):

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("AUDITED PAYMENTS").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )

            audited_label = ui.label("0").classes(
                "text-2xl font-bold text-white mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("COMPLIANT").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )

            compliant_label = ui.label("0").classes(
                "text-2xl font-bold text-green-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("VIOLATIONS").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )

            violations_label = ui.label("0").classes(
                "text-2xl font-bold text-red-400 mt-2"
            )

        with ui.card().classes(
            "bg-slate-900 border border-slate-800 "
            "rounded-xl p-5 flex-1"
        ):
            ui.label("COMPLIANCE RATE").classes(
                "text-xs font-semibold tracking-wider text-slate-400"
            )

            compliance_label = ui.label("0%").classes(
                "text-2xl font-bold text-indigo-400 mt-2"
            )

    # =====================================================
    # LIVE PAYMENT ACTIVITY
    # =====================================================

    with ui.card().classes(
        "w-full bg-slate-900 border border-slate-800 "
        "rounded-xl p-6"
    ):

        with ui.row().classes(
            "w-full items-center justify-between mb-4"
        ):

            ui.label(
                "LIVE PAYMENT ACTIVITY"
            ).classes(
                "text-sm font-bold tracking-wider text-white"
            )

            ui.label(
                "Latest payments"
            ).classes(
                "text-xs text-slate-500"
            )

        payment_table = ui.table(
            columns=[
                {
                    "name": "time",
                    "label": "TIME",
                    "field": "time",
                },
                {
                    "name": "customer",
                    "label": "CUSTOMER",
                    "field": "customer",
                },
                {
                    "name": "amount",
                    "label": "AMOUNT",
                    "field": "amount",
                },
                {
                    "name": "status",
                    "label": "STATUS",
                    "field": "status",
                },
                {
                    "name": "failure",
                    "label": "FAILURE",
                    "field": "failure",
                },
                {
                    "name": "retry",
                    "label": "RETRIES",
                    "field": "retry",
                },
            ],
            rows=[],
            row_key="payment_id",
        ).classes("w-full")


    # =====================================================
    # RECOVERY ACTIVITY
    # =====================================================

    with ui.card().classes(
        "w-full bg-slate-900 border border-slate-800 "
        "rounded-xl p-6"
    ):

        with ui.row().classes(
            "w-full items-center justify-between mb-4"
        ):

            ui.label(
                "AGENT RECOVERY ACTIVITY"
            ).classes(
                "text-sm font-bold tracking-wider text-white"
            )

            ui.label(
                "Agent decisions and execution"
            ).classes(
                "text-xs text-slate-500"
            )

        recovery_table = ui.table(
            columns=[
                {
                    "name": "time",
                    "label": "TIME",
                    "field": "time",
                },
                {
                    "name": "customer",
                    "label": "CUSTOMER",
                    "field": "customer",
                },
                {
                    "name": "amount",
                    "label": "AMOUNT",
                    "field": "amount",
                },
                {
                    "name": "failure",
                    "label": "FAILURE",
                    "field": "failure",
                },
                {
                    "name": "action",
                    "label": "ACTION",
                    "field": "action",
                },
                {
                    "name": "reason",
                    "label": "POLICY",
                    "field": "reason",
                },
                {
                    "name": "result",
                    "label": "RESULT",
                    "field": "result",
                },
                {
                    "name": "audit",
                    "label": "AUDIT",
                    "field": "audit",
                },
            ],
            rows=[],
            row_key="action_id",
        ).classes("w-full")


    # =====================================================
    # AUDIT ACTIVITY
    # =====================================================

    with ui.card().classes(
        "w-full bg-slate-900 border border-slate-800 "
        "rounded-xl p-6"
    ):

        with ui.row().classes(
            "w-full items-center justify-between mb-4"
        ):

            ui.label(
                "AUDIT ACTIVITY"
            ).classes(
                "text-sm font-bold tracking-wider text-white"
            )

            ui.label(
                "Independent policy verification"
            ).classes(
                "text-xs text-slate-500"
            )

        audit_table = ui.table(
            columns=[
                {
                    "name": "time",
                    "label": "TIME",
                    "field": "time",
                },
                {
                    "name": "customer",
                    "label": "CUSTOMER",
                    "field": "customer",
                },
                {
                    "name": "amount",
                    "label": "AMOUNT",
                    "field": "amount",
                },
                {
                    "name": "proposed",
                    "label": "PROPOSED",
                    "field": "proposed",
                },
                {
                    "name": "policy",
                    "label": "POLICY",
                    "field": "policy",
                },
                {
                    "name": "executed",
                    "label": "EXECUTED",
                    "field": "executed",
                },
                {
                    "name": "result",
                    "label": "RESULT",
                    "field": "result",
                },
                {
                    "name": "audit",
                    "label": "AUDIT",
                    "field": "audit",
                },
            ],
            rows=[],
            row_key="audit_id",
        ).classes("w-full")


    # =====================================================
    # SYSTEM STATUS
    # =====================================================

    with ui.card().classes(
        "w-full bg-slate-900 border border-slate-800 "
        "rounded-xl p-6"
    ):

        with ui.row().classes(
            "w-full items-center justify-between"
        ):

            with ui.column().classes("gap-1"):

                ui.label(
                    "SYSTEM STATUS"
                ).classes(
                    "text-xs font-semibold tracking-wider text-slate-400"
                )

                status_label = ui.label(
                    "Monitoring payments..."
                ).classes(
                    "text-lg font-semibold text-white"
                )

            ui.label(
                "Auto-refresh: 3s"
            ).classes(
                "text-xs text-slate-500"
            )


# =========================================================
# UPDATE DASHBOARD
# =========================================================

def update_dashboard():

    metrics = get_metrics()

    audit_metrics = get_audit_metrics()

    total_label.set_text(
        f"{metrics['total_payments']:,}"
    )

    risk_label.set_text(
        format_inr(metrics["revenue_at_risk"])
    )

    recovered_label.set_text(
        format_inr(metrics["revenue_recovered"])
    )

    rate_label.set_text(
        f"{metrics['recovery_rate']:.1f}%"
    )

    failed_label.set_text(
        f"{metrics['failed_payments']:,}"
    )

    recovery_label.set_text(
        f"{metrics['recovered_payments']:,}"
    )

    escalated_label.set_text(
        f"{metrics['escalated']:,}"
    )

    captured_label.set_text(
        f"{metrics['captured_payments']:,}"
    )

    audited_label.set_text(
        f"{audit_metrics['audited']:,}"
    )

    compliant_label.set_text(
        f"{audit_metrics['compliant']:,}"
    )

    violations_label.set_text(
        f"{audit_metrics['violations']:,}"
    )

    compliance_label.set_text(
        f"{audit_metrics['compliance_rate']:.1f}%"
    )

    # -----------------------------------------------------
    # Payments
    # -----------------------------------------------------

    payments = get_recent_payments()

    payment_rows = []

    for payment in payments:

        payment_rows.append(
            {
                "payment_id": payment["payment_id"],
                "time": format_timestamp(
                    payment["created_at"]
                ),
                "customer": payment["customer_name"],
                "amount": format_inr(
                    payment["amount"]
                ),
                "status": payment["status"].upper(),
                "failure": (
                    payment["error_reason"]
                    or "-"
                ),
                "retry": payment["retry_count"],
            }
        )

    payment_table.rows = payment_rows
    payment_table.update()


    # -----------------------------------------------------
    # Recovery actions
    # -----------------------------------------------------

    actions = get_recent_recovery_actions()

    action_rows = []

    for action in actions:

        action_rows.append(
            {
                "action_id": action["action_id"],
                "time": format_timestamp(
                    action["created_at"]
                ),
                "customer": action["customer_name"],
                "amount": format_inr(
                    action["amount"]
                ),
                "failure": (
                    action["error_reason"]
                    or "-"
                ),
                "action": action_name(
                    action["action_type"]
                ),
                "reason": (
                    action["reason"]
                    or "-"
                ),
                "result": action["payment_status"].upper(),
                "audit": (
                    "✓ COMPLIANT"
                    if action["audit_status"] == "COMPLIANT"
                    else "⚠ NON_COMPLIANT"
                    if action["audit_status"] == "NON_COMPLIANT"
                    else "PENDING"
                ),
            }
        )

    recovery_table.rows = action_rows
    recovery_table.update()

    # -----------------------------------------------------
    # Audit activity
    # -----------------------------------------------------

    audits = get_recent_audits()

    audit_rows = []

    for audit in audits:

        audit_rows.append(
            {
                "audit_id": audit["audit_id"],

                "time": format_timestamp(
                    audit["created_at"]
                ),

                "customer": audit["customer_name"],

                "amount": format_inr(
                    audit["amount"]
                ),

                "proposed": action_name(
                    audit["proposed_action"]
                ),

                "policy": action_name(
                    audit["policy_decision"]
                ),

                "executed": action_name(
                    audit["executed_action"]
                ),

                "result": (
                    "RECOVERED"
                    if audit["recovered"]
                    else audit["after_status"].upper()
                ),

                "audit": audit["compliance_status"],
            }
        )

    audit_table.rows = audit_rows
    audit_table.update()

    status_label.set_text(
        f"Monitoring {metrics['failed_payments']:,} failed payment(s)"
    )


# Initial update
update_dashboard()

# Live refresh
ui.timer(
    REFRESH_INTERVAL,
    update_dashboard,
)


ui.run(
    title="Revenue Recovery",
    port=8080,
    reload=False,
)