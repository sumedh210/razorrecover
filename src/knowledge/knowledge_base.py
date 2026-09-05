from pathlib import Path
from typing import Any
import json

from loguru import logger

class KnowledgeBase:
    def __init__(self, chunks_path: Path) -> None:
        self._chunks_path = chunks_path
        self._chunks: dict[str,dict[str,Any]] = {}

        self._load()

    def _load(self) -> None:
        logger.info("Loading knowledge base | path={}", self._chunks_path)

        if not self._chunks_path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {self._chunks_path}")

        with self._chunks_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start = 1):
                line = line.strip()

                if not line:
                    continue

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at line {line_number}") from exc

                chunk_id = chunk.get("chunk_id")
                content = chunk.get("content")

                if not chunk_id:
                    raise ValueError(
                        f"Missing chunk_id at line {line_number}"
                    )

                if not content:
                    raise ValueError(
                        f"Missing content for chunk {chunk_id}"
                    )

                self._chunks[chunk_id] = chunk

        logger.success(
            "Knowledge base loaded | chunks={}",
            len(self._chunks),
        )

    def get(self, chunk_id: str) -> dict[str, Any] | None:
        return self._chunks.get(chunk_id)

    def get_all(self)-> list[dict[str,Any]]:
        return list(self._chunks.values())

    def get_many(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        chunks = []

        for chunk_id in chunk_ids:
            chunk = self._chunks.get(chunk_id)

            if chunk is not None:
                chunks.append(chunk)

        return chunks

    def __len__(self)->int:
        return len(self._chunks)