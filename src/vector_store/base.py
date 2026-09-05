from abc import ABC, abstractmethod
from typing import Any


class VectorStore(ABC):

    @abstractmethod
    def create_index(self) ->None:
        raise NotImplementedError

    @abstractmethod
    def index_exists(self)-> None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, vectors: list[dict[str, Any]],) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, vector: list[float], top_k: int, namespace: str | None= None) -> list[dict[str, Any]]:
        raise NotImplementedError