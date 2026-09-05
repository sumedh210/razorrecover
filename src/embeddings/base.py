from abc import ABC, abstractmethod
from typing import Literal 

EmbeddingInputType = Literal["passage", "query"]

class EmbeddingService(ABC):

    @abstractmethod
    def embed(self, texts: list[str], input_type: EmbeddingInputType) -> list[list[float]]:
        raise NotImplementedError

    