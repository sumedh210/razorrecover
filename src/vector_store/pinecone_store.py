from typing import Any, cast

from loguru import logger
from pinecone import Index, Pinecone, ServerlessSpec 

from src.core.config import PineconeConfig
from src.vector_store.base import VectorStore
from src.vector_store.pinecone_client import PineconeClientManager

class PineconeVectorStore(VectorStore):

    def __init__(self, config:PineconeConfig, client_manager: PineconeClientManager,) -> None:
        self._config = config
        self._client = client_manager.get_client()
        self._index: Index | None = None

        logger.debug("PineconeVectorStore initialized | index={}", self._config.index_name)

    def create_index(self) -> None:
        if self.index_exists():
            logger.info("Pinecone index already exists | index={}", self._config.index_name,)
            return

        logger.info(
            "Creating Pinecone index | name={} | dimension={} | metric={}",
            self._config.index_name,
            self._config.dimension,
            self._config.metric,
        )

        try:
            self._client.indexes.create(
                name=self._config.index_name,
                dimension=self._config.dimension,
                metric=self._config.metric,
                spec=ServerlessSpec(
                    cloud=self._config.cloud,
                    region=self._config.region,
                ),
            )
        

            logger.success("Pinecone index created | index={}", self._config.index_name,)

        except Exception:
           logger.exception(
               "Failed to create Pinecone index | index={}",
               self._config.index_name,
           )
           raise

    def index_exists(self) -> bool:

        try:
            exists = self._client.has_index( self._config.index_name,)

            logger.debug("Pinecone index existence check | index={} | exists={}", self._config.index_name, exists,)

            return exists
        
        except Exception:
            logger.exception(
                "Failed to check Pinecone index | index={}",
                self._config.index_name,
            )
            raise

    def _get_index(self) -> Index:

        if self._index is None:
            logger.debug(
                "Connecting to Pinecone index | index={}",
                self._config.index_name,
            )

            self._index = cast(Index, self._client.index(self._config.index_name, grpc=False),)
        return self._index

    def upsert(self, vectors: list[dict[str, Any]],) -> None:
        if not vectors:
            logger.warning("Upsert requested with zero vectors",)
            return 

        index = self._get_index()
        logger.info("Upserting vectors | count={} | index={}", len(vectors), self._config.index_name,)

        try:
            response = index.upsert(vectors = vectors)

            logger.success("Vctors upserted | count={}", response.upserted_count)
        except Exception:
            logger.exception("Failed to upsert vectors | count={}", len(vectors),)
            raise

    def query(self, vector: list[float], top_k: int, namespace: str | None=None) -> list[dict[str, Any]]:

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        
        index = self._get_index()
        logger.debug("Querying Pinecone | top_k={} | namespace={}", top_k, namespace,)

        try:
            response = index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace or "",
                include_metadata=True,
                include_values=False,
            )

            results = [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata,
                }
                for match in response.matches
            ]

            logger.info("Pinecone query completed | results={}", len(results),)
            return results

        except Exception:
            logger.exception("Pinecone query failed | top_k={} | namespace={}", top_k, namespace,)

            raise

