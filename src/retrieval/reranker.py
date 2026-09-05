from typing import Any

from loguru import logger
from sentence_transformers import CrossEncoder

class CrossEncoderReranker:

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2", device:str="cpu", max_length:int=512) -> None:
        self._model_name = model_name
        self._device = device
        self._max_length = max_length

        logger.info("Initializing reranker | model={} | device={}",
            model_name,
            device,)

        self._model = CrossEncoder(model_name, device=device, max_length=max_length)

        logger.success(
            "Reranker initialized | model={}",
            model_name,
        )

    def rerank(self, query: str, candidates: list[dict[str,Any]], top_k:int) -> list[dict[str, Any]]:

        if not query.strip():
            raise ValueError("Query cannot be empty")

        if top_k <=0:
            raise ValueError("top k cannot be 0")

        if not candidates:
            return []

        top_k = min(top_k, len(candidates))

        pairs = []

        for candidate in candidates:
            content = candidate.get("content")

            if not content:
                raise ValueError(f"Candidate '{candidate.get('id')}' ""does not contain content")

            pairs.append((query, content))

        logger.info(
            "Reranking candidates | candidates={} | top_k={}",
            len(candidates),
            top_k,
        )

        scores = self._model.predict(pairs, batch_size=len(pairs), show_progress_bar=False)

        reranked = []

        for candidate, score in zip(candidates, scores, strict=True):
            result = dict(candidate)

            result["rerank_score"] = float(score)
            reranked.append(result)

            reranked.sort(key=lambda result: result["rerank_score"], reverse=True)

            reranked = reranked[:top_k]

        logger.info("Reranking completed | returned={}",len(reranked),)

        return reranked