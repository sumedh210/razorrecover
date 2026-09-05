from typing import Any

from src.embeddings.base import EmbeddingService
from src.vector_store.base import VectorStore

class DenseRetriever:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore)->None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    def search(self, query:str, top_k:int, namespace:str | None = None)->list[dict[str,Any]]:

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if top_k <=0:
            raise ValueError("top k needs to be greater 0")

        query_vector = self._embedding_service.embed([query], input_type="query")[0]

        return self._vector_store.query(vector=query_vector, top_k=top_k, namespace=namespace)
    

        
