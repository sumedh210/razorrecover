from typing import Any
from loguru import logger

class RRFusion:

    def __init__(self, k: int = 60) -> None:
        if k<=0:
            raise ValueError("RRF k must be greater than zero")

        self._k = k
        logger.debug("RRF Initiated | k={}", k)

    def fuse(self, result_lists: list[list[dict[str, Any]]], top_k: int,) -> list[dict[str, Any]]:
        if not result_lists:
            return []

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        scores: dict[str, float] = {}

        results_by_id: dict[str, dict[str, Any]] = {}

        for results in result_lists:
            for rank, result in enumerate(results, start=1):
                result_id = result["id"]

                scores[result_id]=(scores.get(result_id, 0.0) + 1.0 / (self._k + rank))

                results_by_id[result_id] = result

        ranked_ids = sorted(scores, key=lambda result_id: scores[result_id], reverse = True,)[:top_k]

        fused_results = [
            {
                "id": result_id,
                "score": scores[result_id],
                "metadata": results_by_id[result_id]["metadata"],
            }
            for result_id in ranked_ids
        ]
        logger.info("RRF fusion completed | input_lists={} | results={}", len(result_lists), len(fused_results),)

        return fused_results

    
        
        