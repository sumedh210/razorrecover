from pinecone import Pinecone
from loguru import logger

from src.core.config import PineconeConfig

class PineconeClientManager:

    def __init__(self, config: PineconeConfig) -> None:
        self._config = config
        self._client: Pinecone | None = None
        

    def get_client(self) -> Pinecone:

        if self._client is None:
            logger.info("Pincone Initializing Client")

            self._client = Pinecone( api_key=self._config.api_key,)

            logger.success("Pinecone client initialized")

        return self._client