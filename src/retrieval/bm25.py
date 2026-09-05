
import re
from typing import Any
from loguru import logger
from rank_bm25 import BM25Plus 

class BM25Retriever:

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            raise ValueError("BM25 corpus cannot be empty")

        self._chunks = chunks

        tokenized_corpus =[self._tokenize(chunk["content"]) for chunk in chunks]

        self._bm25 = BM25Plus(tokenized_corpus)

        logger.info("BM25+ index initialized | documents = {}", len(chunks),)

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:

        if not query.strip():
            raise ValueError("Qurey cannot be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        tokens = self._tokenize(query)

        if not tokens:
            logger.warning("Query prouced no tokens | query ={}", query)

            return []

        scores = self._bm25.get_scores(tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        results = [{
            "id": self._chunks[index]["chunk_id"],
            "score": float(scores[index]),
            "metadata": self._build_metadata(self._chunks[index]),
        }for index in ranked_indices]

        logger.info("BM25+ query completed | results={} | top_k={}", len(results), top_k,)

        return results

    @staticmethod
    def _tokenize(text: str,) -> list[str]:
        text = text.lower()

        tokens = re.findall(r"[a-z0-9]+(?:[_-][a-z0-9]+)*",
            text,)
        return tokens

    @staticmethod
    def _build_metadata(chunk: dict[str, Any],)->dict[str,Any]:

        return {
            "source_doc": chunk["source_doc"],
            "title": chunk["title"],
            "section_title": chunk["section_title"],
            "content_type": chunk["content_type"],
            "topic": chunk.get("topic"),
        }