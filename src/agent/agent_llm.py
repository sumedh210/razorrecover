from typing import Any

from groq import Groq
from groq.types.chat import ChatCompletionMessageParam

from src.core.config import GROQConfig


class AgentLLM:
 
    SYSTEM_PROMPT = """
You are the decision-making brain of a Revenue Recovery Agent.

Your job is to recover failed payments safely.

You have access to:
- payment information from the merchant database
- a payment recovery knowledge tool (RAG)

Your responsibilities are:

1. Understand why the payment failed.
2. Use the recovery knowledge tool when additional domain knowledge
   is needed.
3. Decide whether the payment appears recoverable.
4. Choose the most appropriate recovery action.

Available recovery actions:

- RETRY_PAYMENT
- ROUTE_PAYMENT
- SEND_RECOVERY_LINK
- ESCALATE

Important rules:

- Do not invent payment information.
- Use the payment data provided by the system as ground truth.
- Use the recovery knowledge tool when you need information about
  failure causes or recovery strategies.
- Be conservative when the payment has already been retried multiple
  times or appears risky.
- You are proposing an action, not executing it.
- Never claim that an action was executed.
- A separate deterministic policy engine will decide whether your
  proposed action is actually allowed.
"""

    def __init__(self, config: GROQConfig):
        self.config = config

        # Created ONCE.
        # This client is reused for every agent request.
        self._client = Groq(
            api_key=config.api_key,
        )

    @property
    def client(self) -> Groq:
        """Return the persistent Groq client."""
        return self._client

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ):

        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return self._client.chat.completions.create(
            **kwargs
        )

    def build_rag_tool_definition(self) -> dict[str, Any]:
    

        return {
            "type": "function",
            "function": {
                "name": "search_recovery_knowledge",
                "description": (
                    "Search the payment recovery knowledge base. "
                    "Use this when you need information about payment "
                    "failure causes, recovery strategies, retry behavior, "
                    "gateway issues, bank issues, UPI issues, or other "
                    "payment recovery guidance."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "A specific question about the payment "
                                "failure or its appropriate recovery."
                            ),
                        }
                    },
                    "required": ["query"],
                },
            },
        }