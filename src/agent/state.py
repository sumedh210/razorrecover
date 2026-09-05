from typing import Any, TypedDict, NotRequired


class AgentState(TypedDict):

    payment_id: str
    payment: dict[str, Any]

    diagnosis: str
    diagnosis_confidence: float
    diagnosis_source: str

    proposed_action: str

    policy_decision: str
    policy_reason: str
    policy_allowed: NotRequired[bool]

    action_result: dict[str, Any]

    final_payment: dict[str, Any]

    recovered: bool
    recovered_amount: float

    attempts: int
    should_continue: bool

    audit_events: list[dict[str, Any]]

    error: str