import json
import sqlite3
from pathlib import Path
from typing import Any
import asyncio

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from loguru import logger

from src.agent.state import AgentState
from src.agent.auditor import audit_payment

DATABASE_PATH = Path("data/processed/merchant_tuned.db")

def load_payment_node(state: AgentState) ->AgentState:
    payment_id = state.get("payment_id")

    if not payment_id:
        raise RuntimeError(
            "No payment_id provided to agent.")

    # db_path = Path("data/processed/merchant_tuned.db")
        
    logger.info(
        "Loading payment | payment_id={}",
        payment_id,
    )
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
        raise RuntimeError(
            f"Payment not found: {payment_id}"
        )

    payment = dict(row)

    status = str(
        payment.get("status", "")
    ).lower()

    if status != "failed":
        logger.info(
            "Payment is not failed | payment_id={} | status={}",
            payment_id,
            status,
        )

        state["should_continue"] = False
        state["error"] = (
            f"Payment is not eligible for recovery. "
            f"Current status: {status}"
        )

        return state

    state["payment"] = payment
    state["should_continue"] = True

    logger.success(
        "Failed payment loaded | payment_id={} | reason={} | retry_count={}",
        payment_id,
        payment.get("error_reason"),
        payment.get("retry_count"),
    )

    return state

def agent_reasoning_node(
    state: AgentState,
    agent_llm,
    rag_tool,
) -> AgentState:

    payment = state["payment"]

    logger.info(
        "Agent reasoning started | payment_id={}",
        payment["payment_id"],
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": """
You are the brain of a Revenue Recovery Agent.

Your job is to analyze a failed payment and decide the safest
recovery action.

You have access to a recovery knowledge-base search tool.

Use the knowledge-base tool when you need additional information
about the failure reason, recovery procedure, or payment behavior.

You must NOT directly execute any financial action.

You only diagnose the payment and propose an action.
A separate policy engine will decide whether the action is allowed.

Possible actions:

- RETRY_PAYMENT
- ROUTE_PAYMENT
- SEND_RECOVERY_LINK
- ESCALATE

Your reasoning should consider:
- payment failure reason
- error code
- error description
- payment method
- bank
- retry count
- payment amount
- any relevant recovery knowledge

After gathering the required information, return ONLY valid JSON:

{
  "diagnosis": "...",
  "diagnosis_confidence": 0.0,
  "proposed_action": "RETRY_PAYMENT"
}

diagnosis_confidence must be between 0 and 1.
""",
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "payment": payment
                },
                default=str,
            ),
        },
    ]

    tools = [
        agent_llm.build_rag_tool_definition()
    ]

    # --------------------------------------------------
    # Let the LLM reason and optionally call RAG
    # --------------------------------------------------

    for _ in range(3):

        response = agent_llm.generate(
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        # --------------------------------------------------
        # No tool call -> LLM has finished reasoning
        # --------------------------------------------------

        if not message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                }
            )

            break

        # --------------------------------------------------
        # Handle tool calls
        # --------------------------------------------------

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [],
        }

        for tool_call in message.tool_calls:

            assistant_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )

        messages.append(assistant_message)

        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            if tool_name != "search_recovery_knowledge":
                continue

            arguments = json.loads(
                tool_call.function.arguments
            )

            query = arguments["query"]

            logger.info(
                "Agent requesting RAG | query={}",
                query,
            )

            rag_answer = rag_tool(query)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": rag_answer,
                }
            )

    # --------------------------------------------------
    # Parse final LLM decision
    # --------------------------------------------------

    final_message = messages[-1]

    if final_message["role"] != "assistant":
        raise RuntimeError(
            "Agent LLM did not produce a final decision."
        )

    content = final_message["content"]

    try:
        decision = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.error(
            "Agent returned invalid JSON | response={}",
            content,
        )
        raise RuntimeError(
            "Agent LLM returned invalid decision JSON."
        ) from exc

    diagnosis = str(
        decision.get("diagnosis", "")
    )

    diagnosis_confidence = float(
        decision.get("diagnosis_confidence", 0.0)
    )

    proposed_action = str(
        decision.get("proposed_action", "ESCALATE")
    ).upper()

    state["diagnosis"] = diagnosis
    state["diagnosis_confidence"] = diagnosis_confidence
    state["diagnosis_source"] = "llm"
    state["proposed_action"] = proposed_action

    logger.info(
        "Agent decision | payment_id={} | action={} | confidence={}",
        payment["payment_id"],
        proposed_action,
        diagnosis_confidence,
    )

    return state

def policy_node(
    state: AgentState,
    policy_engine,
) -> AgentState:

    payment = state.get("payment")

    if payment is None:
        raise RuntimeError(
            "Payment was not loaded into agent state."
        )

    diagnosis = state.get("diagnosis", "")
    proposed_action = state.get(
        "proposed_action",
        "ESCALATE",
    )

    logger.info(
        "Evaluating proposed action | payment_id={} | action={}",
        payment["payment_id"],
        proposed_action,
    )

    decision = policy_engine.evaluate(
        payment=payment,
        diagnosis=diagnosis,
        proposed_action=proposed_action,
    )

    state["policy_allowed"] = decision.allowed
    state["policy_decision"] = decision.action
    state["policy_reason"] = decision.reason

    logger.info(
        "Policy decision | payment_id={} | allowed={} | action={} | reason={}",
        payment["payment_id"],
        decision.allowed,
        decision.action,
        decision.reason,
    )

    return state

def execute_action_node(
    state: AgentState,
) -> AgentState:

    payment = state.get("payment")

    if payment is None:
        raise RuntimeError(
            "Payment was not loaded into agent state."
        )

    action = state.get("policy_decision")

    if not action:
        raise RuntimeError(
            "No policy decision available."
        )

    payment_id = payment["payment_id"]

    # --------------------------------------------------
    # Policy denied the proposed action
    # --------------------------------------------------

    if action == "DENIED":
        logger.warning(
            "Action denied by policy | payment_id={}",
            payment_id,
        )

        state["action_result"] = {
            "status": "denied",
            "action": "NONE",
            "payment_id": payment_id,
            "reason": state.get(
                "policy_reason",
                "Action denied by policy.",
            ),
        }

        return state

    logger.info(
        "Executing approved action | payment_id={} | action={}",
        payment_id,
        action,
    )

    result = asyncio.run(
        _call_mcp_tool(
            action=action,
            payment_id=payment_id,
            reason=state.get("diagnosis", ""),
        )
    )

    state["action_result"] = result

    logger.success(
        "Action executed | payment_id={} | action={}",
        payment_id,
        action,
    )

    return state

async def _call_mcp_tool(
    action: str,
    payment_id: str,
    reason: str,
) -> dict[str, Any]:

    transport = StdioTransport(
        command="uv",
        args=[
            "run",
            "python",
            "-m",
            "src.mcp.server",
        ],
        cwd="D:/razorpay_revenue_recovery",
    )

    async with Client(transport) as client:

        if action == "RETRY_PAYMENT":
            result = await client.call_tool(
                "retry_payment_tool",
                {"payment_id": payment_id}
            )
        
        elif action == "ROUTE_PAYMENT":
            result = await client.call_tool(
                "route_payment_tool",
                {"payment_id": payment_id}
            )
        
        elif action == "SEND_RECOVERY_LINK":
            result = await client.call_tool(
                "send_recovery_link_tool",
                {"payment_id": payment_id}
            )
        
        elif action == "ESCALATE":
            result = await client.call_tool(
                "escalate_payment_tool",
                {
                    "payment_id": payment_id,
                    "reason": reason
                }
            )
        
        else:
            raise RuntimeError(f"Unsupported policy action: {action}")

    return {
        "status": "executed",
        "action": action,
        "payment_id": payment_id,
        "result": str(result),
    }

def observe_payment_node(
    state: AgentState,
) -> AgentState:

    payment = state.get("payment")

    if payment is None:
        raise RuntimeError(
            "Payment was not loaded into agent state."
        )

    payment_id = payment["payment_id"]

    logger.info(
        "Observing payment after recovery action | payment_id={}",
        payment_id,
    )

    # db_path = Path("data/processed/merchant.db")

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
        raise RuntimeError(
            f"Payment disappeared from database: {payment_id}"
        )

    final_payment = dict(row)

    status = str(
        final_payment.get("status", "")
    ).lower()

    recovered = status in {
        "captured",
        "paid",
        "success",
        "successful",
    }

    amount = float(
        final_payment.get("amount", 0)
    )

    state["final_payment"] = final_payment
    state["recovered"] = recovered
    state["recovered_amount"] = amount if recovered else 0.0

    logger.info(
        "Payment observation | payment_id={} | status={} | recovered={} | amount={}",
        payment_id,
        status,
        recovered,
        state["recovered_amount"],
    )

    return state

def auditor_node(state: AgentState) -> AgentState:

    logger.info("Auditing recovery | payment_id={}", state.get("payment_id"))

    return audit_payment(state)