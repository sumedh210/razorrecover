from typing import Any
from loguru import logger
from src.core.logging import configure_logging

from src.classifier.onnx_classifier import QueryClassifier
from src.knowledge.knowledge_base import KnowledgeBase
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever
from src.retrieval.reciprocal_rank_fusion import RRFusion
from src.retrieval.reranker import CrossEncoderReranker
from src.rag.context_builder import ContextBuilder
from src.llm.llm import RAGLLM


class RAGOrchestrator:
    def __init__(self,
        classifier: QueryClassifier,
        bm25: BM25Retriever,
        dense: DenseRetriever,
        rrf: RRFusion,
        knowledge_base: KnowledgeBase,
        reranker: CrossEncoderReranker,
        context_builder: ContextBuilder,
        rag_llm: RAGLLM,
        retrieval_top_k: int = 10,
        rerank_top_k: int = 5,
        retrieval_confidence_threshold: float = 0.60,) -> None:

        if retrieval_top_k <=0:
            raise ValueError("retrieval_top_k must be greater than zero")

        if rerank_top_k <= 0:
            raise ValueError("rerank_top_k must be greater than zero")

        if not 0.0 <= retrieval_confidence_threshold <= 1.0:
            raise ValueError("retrieval_confidence_threshold must be between 0 and 1")

        self._classifier = classifier
        self._bm25 = bm25
        self._dense = dense
        self._rrf = rrf
        self._knowledge_base = knowledge_base
        self._reranker = reranker
        self._context_builder = context_builder
        self._rag_llm = rag_llm

        self._retrieval_top_k = retrieval_top_k
        self._rerank_top_k = rerank_top_k
        self._retrieval_confidence_threshold = (
            retrieval_confidence_threshold
        )

        logger.success("RAG orchestrator initialized")

    def run(self, query: str) -> str:
        if not query or not query.strip():
            raise ValueError("Query must not be empty")

        logger.info("RAG query started | query={}", query)

        classification = self._classifier.predict(query)

        intent = classification["intent"]
        retrieval_mode = classification["retrieval_mode"]
        retrieval_confidence = classification["retrieval_confidence"]

        logger.info("Query classified | intent={} | retrieval_mode={} | confidence={:.3f}",intent,retrieval_mode,retrieval_confidence)

        if retrieval_confidence < self._retrieval_confidence_threshold:
            logger.warning("Low retrieval confidence | confidence={:.3f} | " "threshold={:.3f} | falling back to mixed retrieval", retrieval_confidence, self._retrieval_confidence_threshold,
            )

            retrieval_mode = "mixed"

        candidates = self._retrieve(query = query, retrieval_mode = retrieval_mode)

        if not candidates: 
            logger.warning("No retrieval candidates found | query={}", query,)
            return ("I could not find enough relevant information in the knowledge base to answer this question.")

        candidates = self._resolve_content(candidates)

        if not candidates:
            logger.warning(
                "No candidate content could be resolved from the loaded KB | query={}",
                query,
            )
            return (
                "I could not find enough relevant information in "
                "the knowledge base to answer this question."
            )

        reranked =  self._reranker.rerank(query = query, candidates=candidates, top_k=self._rerank_top_k)

        if not reranked:
            logger.warning("Reranker returned no results | query={}", query)
            return (
                "I could not find enough relevant information in the knowledge base to answer this question."
            )

        context = self._context_builder.build(reranked)

        answer = self._rag_llm.generate_answer(query=query, context=context)

        logger.success(
            "RAG query completed | retrieval_mode={} | candidates={} | reranked={}", retrieval_mode, len(candidates), len(reranked),)

        return answer

    def _retrieve(self, query: str, retrieval_mode: str) -> list[dict[str, Any]]:

        if retrieval_mode == "lexical":
            logger.info("Using lexical retrieval")

            return self._bm25.search(query=query, top_k=self._retrieval_top_k)

        if retrieval_mode == "semantic":
            logger.info("Using semantic retrieval")

            return self._dense.search(query=query, top_k=self._retrieval_top_k)

        if retrieval_mode == "mixed":
            logger.info("Using mixed retrieval")

            bm25_results = self._bm25.search(
                query=query,
                top_k=self._retrieval_top_k,
            )

            dense_results = self._dense.search(
                query=query,
                top_k=self._retrieval_top_k,
            )
            return self._rrf.fuse(
                result_lists=[
                    bm25_results,
                    dense_results,
                ],
                top_k=self._retrieval_top_k,
            )

        raise ValueError(
            f"Unsupported retrieval mode: {retrieval_mode}"
        )

    def _resolve_content(self, candidates: list[dict[str, Any]])->list[dict[str, Any]]:

        chunk_ids =[candidate["id"] for candidate in candidates]

        chunks = self._knowledge_base.get_many(chunk_ids)

        chunks_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}

        resolved : list[dict[str, Any]] = []

        for candidate in candidates:
            chunk = chunks_by_id.get(candidate["id"])

            if chunk is None:
                logger.warning("Knowledge-base chunk not found | id={}",
                    candidate["id"],)
                continue

            result = dict(candidate)

            result["content"] = chunk["content"]

            if not result.get("metadata"):
                result["metadata"] = {
                    key: chunk.get(key)
                    for key in [
                        "source_doc",
                        "title",
                        "section_title",
                        "content_type",
                        "topic",
                    ]
                }

            resolved.append(result)

        return resolved

            




