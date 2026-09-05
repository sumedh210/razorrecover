import time
from typing import cast

from loguru import logger

from src.agent.bootstrap import build_agent
from src.agent.batch_runner import get_pending_payment_ids
from src.agent.state import AgentState


SCAN_INTERVAL_SECONDS = 3


def run_worker() -> None:
    logger.info("Starting Revenue Recovery Agent worker...")

    # Build the agent ONCE.
    # RAG, classifier, reranker and LLM remain alive and are reused.
    agent = build_agent()

    logger.success("Revenue Recovery Agent worker is ready")

    while True:
        try:
            payment_ids = get_pending_payment_ids()

            if not payment_ids:
                logger.info("No new failed payments found")

            else:
                logger.info(
                    "Found {} failed payment(s) to process",
                    len(payment_ids),
                )

                for payment_id in payment_ids:
                    try:
                        logger.info(
                            "Processing payment | payment_id={}",
                            payment_id,
                        )

                        result = agent.invoke(
                            cast(AgentState, {"payment_id": payment_id})
                        )

                        logger.success(
                            "Payment processed | payment_id={} | "
                            "action={} | recovered={} | amount={}",
                            payment_id,
                            result.get("policy_decision"),
                            result.get("recovered"),
                            result.get("recovered_amount", 0),
                        )

                    except Exception:
                        logger.exception(
                            "Payment processing failed | payment_id={}",
                            payment_id,
                        )

        except Exception:
            logger.exception("Worker scan failed")

        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()