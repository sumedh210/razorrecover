import json
from pathlib import Path
from typing import Any

from loguru import logger

from src.embeddings.base import EmbeddingService
from src.vector_store.base import VectorStore

class KnowledgeUnitLoader:

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def load(self, limit: int | None = None) -> list[dict[str, Any]]:

        if not self._path.exists():
            raise FileNotFoundError( f"Knowledge unit file not found: {self._path}")

        units: list[dict[str, Any]] = []

        with self._path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):

                if not line.strip():
                    continue

                try:
                    unit = json.loads(line)

                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at line {line_number}") from exc
                    
                if "chunk_id" not in unit:
                    raise ValueError(f"Missing 'chunk_id' at  line {line_number}")

                if "content" not in unit:
                    raise ValueError(f"Missing 'content' st line {line_number}")

                units.append(unit)

        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be greater than zero")
                
        units = units[:limit]
        
        logger.info("Knowledge units loaded| count={}", len(units),)

        return units

class EmbeddingPipeline:

    def __init__(self, loader: KnowledgeUnitLoader, embedding_service: EmbeddingService, vector_store: VectorStore, batch_size: int = 32,) -> None:
        if batch_size <=0:
            raise ValueError("Bactch-size must be greater than zero.")
        
        self._loader = loader
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._batch_size = batch_size

    def run(self, limit: int | None = None) -> None:

        units = self._loader.load(limit=limit)

        if not units:
            logger.warning("No Knowledge units found")
            return

        total_units = len(units)

        logger.info("Starting embedding pipeline | units={} | batch_size={}", total_units, self._batch_size,)

        total_batches = (total_units + self._batch_size -1) // self._batch_size

        for start in range(0, total_units, self._batch_size):

            batch = units[start: start + self._batch_size]

            batch_number = (start // self._batch_size) + 1

            self._process_batch(batch=batch, batch_number=batch_number,total_batches=total_batches)

        logger.success("Embedding pipeline completed | units={}", total_units,)

    def _process_batch(self, batch:list[dict[str,Any]], batch_number: int, total_batches: int) -> None:
            logger.info("Processing embedding batch | batch={}/{} | size={}", batch_number, total_batches, len(batch),)

            texts =[unit["content"] for unit in batch]

            embeddings = self._embedding_service.embed(texts=texts, input_type="passage",)

            if len(embeddings) != len(batch):
                raise ValueError("Embedding count does not match" f"batch size: " f"{len(embeddings)} != {len(batch)}")

            vectors = [self._build_vector(unit = unit, embedding = embedding)
                       for unit, embedding in zip(batch, embeddings, strict=True,)]
            self._vector_store.upsert(vectors)

            logger.success("Embedding batch completed | batch={}/{} | vectors={}", batch_number, total_batches, len(vectors),)

    @staticmethod
    def _build_vector(unit: dict[str, Any], embedding: list[float],) -> dict[str, Any]:
        metadata = {
            "source_doc": unit["source_doc"],
            "title": unit["title"],
            "section_title": unit["section_title"],
            "content_type": unit["content_type"],
            "topic": unit.get("topic"),
            "section_path": unit.get("section_path", []),
            "estimated_tokens": unit.get("estimated_tokens"),
            }
        return {"id": unit["chunk_id"], "values": embedding, "metadata": metadata}
    




            
        