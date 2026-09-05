from loguru import logger
from openai import OpenAI
from typing import cast
from src.core.config import NVIDIAConfig
from src.embeddings.nvidia_client import NVIDIAClientManager
from src.embeddings.base import (EmbeddingInputType, EmbeddingService)

class NVIDIAEmbeddingService(EmbeddingService):

    def __init__(self, config: NVIDIAConfig, client_Manager: NVIDIAClientManager) -> None:

        self._config = config
        self._client: OpenAI  = client_Manager.get_client()
        logger.debug("NVIDIA embedding service initialized | model={}", config.embedding_model,)

    def embed (self, texts: list[str], input_type: EmbeddingInputType) -> list[list[float]]:
        if not texts:
            logger.warning("Embedding requested with zero texts")
            return []

        logger.info("Generating embeddings | count={} | type={}", len(texts), input_type,)

        try:
            response = self._client.embeddings.create(
                model=self._config.embedding_model,
                input=texts,
                encoding_format="float",
                extra_body={
                    "input_type": input_type,
                },
            )     

            embeddings = [
                cast(list[float], item.embedding)
                for item in response.data
            ]   

            logger.success("Embeddings generated | count = {} | dimension = {}", len(embeddings), self._config.embedding_dimensions)

            return embeddings
        except Exception:
            logger.exception("Failed to generate embeddings | count={} | type={}", len(texts), input_type,)

            raise

    def validate_dimensions(self, embeddings : list[list[float]],) -> None:

        for embedding in embeddings:
            if len(embedding) != self._config.embedding_dimensions:
                raise ValueError(
                    "Unexpected embedding dimension: "
                    f"expected {self._config.embedding_dimensions}, "
                    f"got {len(embedding)}"
                )

        

