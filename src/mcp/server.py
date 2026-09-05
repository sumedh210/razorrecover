from fastmcp import FastMCP

from src.mcp.tools import (get_payment, retry_payment, route_payment, send_recovery_link, escalate_payment)

mcp = FastMCP(
    name="Revenue Recovery MCP"
)


@mcp.tool()
def get_payment_tool(
    payment_id: str,
) -> dict:
    """
    Get the latest state of a payment.
    """
    return get_payment(payment_id)


@mcp.tool()
def retry_payment_tool(
    payment_id: str,
) -> dict:
    """
    Retry a failed payment.
    """
    return retry_payment(payment_id)


@mcp.tool()
def route_payment_tool(
    payment_id: str,
) -> dict:
    """
    Route a failed payment through an alternative route.
    """
    return route_payment(payment_id)


@mcp.tool()
def send_recovery_link_tool(
    payment_id: str,
) -> dict:
    """
    Send a recovery link to the customer.
    """
    return send_recovery_link(payment_id)


@mcp.tool()
def escalate_payment_tool(
    payment_id: str,
    reason: str,
) -> dict:
    """
    Escalate a payment for manual intervention.
    """
    return escalate_payment(
        payment_id,
        reason,
    )


if __name__ == "__main__":
    mcp.run()