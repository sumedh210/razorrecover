from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyDecision:
    allowed: bool
    action: str
    reason: str
    rule_id: str
    diagnosis: str


class PolicyEngine:
    MAX_RETRIES = 3
    HIGH_VALUE_THRESHOLD = 1_000_000

    TERMINAL_STATUSES = {
        "captured",
        "paid",
        "success",
        "successful",
        "refunded",
        "cancelled",
        "expired",
    }

    CUSTOMER_ACTION_REASONS = {
        "incorrect_otp",
        "authentication_failed",
    }

    RETRYABLE_REASONS = {
        "gateway_technical_error",
        "payment_timed_out",
    }

    BANK_FAILURE_REASONS = {
        "payment_failed",
    }

    RISK_REASONS = {
        "payment_risk_check_failed",
    }

    ALLOWED_ACTIONS = {
        "RETRY_PAYMENT",
        "ROUTE_PAYMENT",
        "SEND_RECOVERY_LINK",
        "ESCALATE",
    }

    def evaluate(
        self,
        payment: dict[str, Any],
        diagnosis: str,
        proposed_action: str,
    ) -> PolicyDecision:

        status = str(payment.get("status") or "").lower()
        error_reason = str(payment.get("error_reason") or "").lower()
        error_source = str(payment.get("error_source") or "").lower()

        retry_count = int(payment.get("retry_count") or 0)
        amount = float(payment.get("amount") or 0)

        action = str(proposed_action or "ESCALATE").upper()

        # ---------------------------------------------------------
        # Rule 1: Unsupported action
        # ---------------------------------------------------------
        if action not in self.ALLOWED_ACTIONS:
            return PolicyDecision(
                allowed=False,
                action="ESCALATE",
                reason=f"Unsupported proposed action: {action}",
                rule_id="R_UNSUPPORTED_ACTION",
                diagnosis=diagnosis,
            )

        # ---------------------------------------------------------
        # Rule 2: Terminal payment
        # ---------------------------------------------------------
        if status in self.TERMINAL_STATUSES:
            return PolicyDecision(
                allowed=False,
                action="STOP",
                reason=f"Payment is already in terminal status: {status}",
                rule_id="R_TERMINAL_PAYMENT",
                diagnosis=diagnosis,
            )

        # ---------------------------------------------------------
        # Rule 3: Only failed payments are eligible
        # ---------------------------------------------------------
        if status != "failed":
            return PolicyDecision(
                allowed=False,
                action="ESCALATE",
                reason=f"Payment is not eligible for recovery: status={status}",
                rule_id="R_INVALID_PAYMENT_STATUS",
                diagnosis=diagnosis,
            )

        # ---------------------------------------------------------
        # Rule 4: High-value payments require escalation
        # ---------------------------------------------------------
        if amount >= self.HIGH_VALUE_THRESHOLD:
            return PolicyDecision(
                allowed=False,
                action="ESCALATE",
                reason=(
                    f"High-value payment ({amount:.2f}) requires "
                    "manual intervention."
                ),
                rule_id="R_HIGH_VALUE_OVERRIDE",
                diagnosis=diagnosis,
            )

        # ---------------------------------------------------------
        # Rule 5: Retry limit applies globally
        # ---------------------------------------------------------
        if retry_count >= self.MAX_RETRIES and action == "RETRY_PAYMENT":
            return PolicyDecision(
                allowed=False,
                action="ESCALATE",
                reason=(
                    f"Maximum retry limit reached: "
                    f"{retry_count}/{self.MAX_RETRIES}"
                ),
                rule_id="R_RETRY_LIMIT",
                diagnosis=diagnosis,
            )

        # ---------------------------------------------------------
        # Rule 6: Risk failures should not be retried
        # ---------------------------------------------------------
        if error_reason in self.RISK_REASONS:
            return PolicyDecision(
                allowed=False,
                action="ESCALATE",
                reason=(
                    f"Risk-related payment failure "
                    f"({error_reason}) requires manual review."
                ),
                rule_id="R_RISK_ESCALATION",
                diagnosis=diagnosis,
            )

        # ---------------------------------------------------------
        # Rule 7: Customer-caused failures
        # ---------------------------------------------------------
        if error_reason in self.CUSTOMER_ACTION_REASONS:

            if action == "SEND_RECOVERY_LINK":
                return PolicyDecision(
                    allowed=True,
                    action="SEND_RECOVERY_LINK",
                    reason=(
                        f"Customer action required for "
                        f"{error_reason}; recovery link is appropriate."
                    ),
                    rule_id="R_CUSTOMER_RECOVERY_LINK",
                    diagnosis=diagnosis,
                )

            if action == "RETRY_PAYMENT":
                return PolicyDecision(
                    allowed=False,
                    action="SEND_RECOVERY_LINK",
                    reason=(
                        f"{error_reason} indicates a customer-side "
                        "failure; blind retry is not appropriate."
                    ),
                    rule_id="R_CUSTOMER_NO_RETRY",
                    diagnosis=diagnosis,
                )

            if action == "ROUTE_PAYMENT":
                return PolicyDecision(
                    allowed=False,
                    action="SEND_RECOVERY_LINK",
                    reason=(
                        f"{error_reason} is customer-side; "
                        "alternative routing is unnecessary."
                    ),
                    rule_id="R_CUSTOMER_NO_ROUTE",
                    diagnosis=diagnosis,
                )

            if action == "ESCALATE":
                return PolicyDecision(
                    allowed=True,
                    action="ESCALATE",
                    reason=(
                        f"Customer-side failure {error_reason} "
                        "was explicitly escalated."
                    ),
                    rule_id="R_CUSTOMER_ESCALATION",
                    diagnosis=diagnosis,
                )

        # ---------------------------------------------------------
        # Rule 8: Gateway transient failures
        # ---------------------------------------------------------
        if error_reason in self.RETRYABLE_REASONS:

            if action == "RETRY_PAYMENT":
                return PolicyDecision(
                    allowed=True,
                    action="RETRY_PAYMENT",
                    reason=(
                        f"Transient gateway failure {error_reason} "
                        "is eligible for retry."
                    ),
                    rule_id="R_TRANSIENT_RETRY",
                    diagnosis=diagnosis,
                )

            if action == "ROUTE_PAYMENT":
                return PolicyDecision(
                    allowed=True,
                    action="ROUTE_PAYMENT",
                    reason=(
                        f"Transient gateway failure {error_reason} "
                        "is eligible for alternative routing."
                    ),
                    rule_id="R_TRANSIENT_ROUTE",
                    diagnosis=diagnosis,
                )

            if action == "SEND_RECOVERY_LINK":
                return PolicyDecision(
                    allowed=False,
                    action="RETRY_PAYMENT",
                    reason=(
                        f"{error_reason} is an infrastructure failure; "
                        "customer recovery link is not the first action."
                    ),
                    rule_id="R_TRANSIENT_NO_RECOVERY_LINK",
                    diagnosis=diagnosis,
                )

            if action == "ESCALATE":
                return PolicyDecision(
                    allowed=True,
                    action="ESCALATE",
                    reason=(
                        f"Transient failure {error_reason} "
                        "was explicitly escalated."
                    ),
                    rule_id="R_TRANSIENT_ESCALATION",
                    diagnosis=diagnosis,
                )

        # ---------------------------------------------------------
        # Rule 9: Bank payment failure
        # ---------------------------------------------------------
        if error_reason in self.BANK_FAILURE_REASONS:

            if action == "ROUTE_PAYMENT":
                return PolicyDecision(
                    allowed=True,
                    action="ROUTE_PAYMENT",
                    reason=(
                        "Bank-side payment failure may be recoverable "
                        "through an alternative payment route."
                    ),
                    rule_id="R_BANK_ROUTE",
                    diagnosis=diagnosis,
                )

            if action == "RETRY_PAYMENT":
                return PolicyDecision(
                    allowed=True,
                    action="RETRY_PAYMENT",
                    reason=(
                        "Bank-side payment failure is eligible "
                        "for a bounded retry."
                    ),
                    rule_id="R_BANK_RETRY",
                    diagnosis=diagnosis,
                )

            if action == "SEND_RECOVERY_LINK":
                return PolicyDecision(
                    allowed=False,
                    action="ROUTE_PAYMENT",
                    reason=(
                        "Bank-side failure is not primarily "
                        "a customer-action problem."
                    ),
                    rule_id="R_BANK_NO_RECOVERY_LINK",
                    diagnosis=diagnosis,
                )

            if action == "ESCALATE":
                return PolicyDecision(
                    allowed=True,
                    action="ESCALATE",
                    reason="Bank-side payment failure was escalated.",
                    rule_id="R_BANK_ESCALATION",
                    diagnosis=diagnosis,
                )

        # ---------------------------------------------------------
        # Rule 10: Unknown failure reason
        # ---------------------------------------------------------
        return PolicyDecision(
            allowed=False,
            action="ESCALATE",
            reason=(
                f"Unknown or unsupported failure reason: "
                f"{error_reason or 'missing'} "
                f"(source={error_source or 'missing'})"
            ),
            rule_id="R_UNKNOWN_FAILURE",
            diagnosis=diagnosis,
        )