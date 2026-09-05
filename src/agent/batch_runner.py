import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

DATABASE_PATH = Path("data/processed/merchant_tuned.db")

def get_pending_payment_ids() -> list[str]:
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        query = """
                SELECT p.payment_id
                FROM payments p
                LEFT JOIN recovery_actions r
                    ON r.entity_type = 'payment'
                    AND r.entity_id = p.payment_id
                WHERE p.status = 'failed'
                  AND r.action_id IS NULL
                ORDER BY p.created_at
                """


        rows = connection.execute(query).fetchall()

        return [row[0] for row in rows]

    finally:
        connection.close()

def run_batch(agent, limit: int | None=None) -> dict[str,Any]:
    payment_ids = get_pending_payment_ids()

    logger.info("Starting batch recovery | payments = {}", len(payment_ids),)

    results = []

    for index, payment_id in enumerate(payment_ids, start=1):
        logger.info("Processing payment | {}/{} | payment_id={}", index, len(payment_ids), payment_id)

        try:
            result = agent.invoke({
                "payment_id": payment_id
            })

            results.append(result)

        except Exception as exc:
            logger.exception(
                "Payment processing failed | payment_id={}",
                payment_id,
            )

            results.append({
                "payment_id": payment_id,
                "error": str(exc),
            })

    logger.success(
        "Batch recovery completed | processed={}",
        len(results),
    )

    return {
        "processed": len(results),
        "results": results,
    }
