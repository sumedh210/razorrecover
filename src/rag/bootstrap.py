from pathlib import Path

from loguru import logger

from src.core.config import AppConfig
from src.core.config import ConfigLoader

from src.classifier.onnx_classifier import QueryClassifier

from src.knowledge.knowledge_base import KnowledgeBase

from src.embeddings.nvidia_client import NVIDIAClientManager
from src.embeddings.nvidia_embeddings import NVIDIAEmbeddingService

from src.vector_store.pinecone_client import PineconeClientManager
from src.vector_store.pinecone_store import PineconeVectorStore

from src.retrieval.bm25 import BM25Retriever
from src.retrieval.dense import DenseRetriever
from src.retrieval.reciprocal_rank_fusion import RRFusion
from src.retrieval.reranker import CrossEncoderReranker

from src.rag.context_builder import ContextBuilder
from src.rag.orchestrator import RAGOrchestrator

from src.llm.groq_client import GROQClientManager
from src.llm.llm import RAGLLM


def build_rag() -> tuple[RAGOrchestrator, AppConfig]:

    logger.info("Starting RAG application initialization...")

    # --------------------------------------------------
    # 1. Configuration
    # --------------------------------------------------

    config_path = Path("config/config.yaml")

    config = ConfigLoader(config_path).load()

    logger.success("Configuration loaded")

    # --------------------------------------------------
    # 2. Knowledge Base
    # --------------------------------------------------

    knowledge_base = KnowledgeBase(
        Path("kb/chunks/chunks.jsonl")
    )

    chunks = knowledge_base.get_all()

    logger.success(
        "Knowledge base loaded | chunks={}",
        len(chunks),
    )

    # --------------------------------------------------
    # 3. Query Classifier
    # --------------------------------------------------

    classifier = QueryClassifier(
        model_path=Path("ml/models/query_classifier/onnx/model.onnx"),
        tokenizer_path=Path("ml/models/query_classifier/onnx/tokenizer"),
        labels_path=Path("ml/models/query_classifier/onnx/labels.json"),
    )

    logger.success("Query classifier ready")

    # --------------------------------------------------
    # 4. NVIDIA Embedding Service
    # --------------------------------------------------

    nvidia_client_manager = NVIDIAClientManager(
        config.nvidia
    )

    embedding_service = NVIDIAEmbeddingService(
        config=config.nvidia,
        client_Manager=nvidia_client_manager,
    )

    logger.success("Embedding service ready")

    # --------------------------------------------------
    # 5. Pinecone
    # --------------------------------------------------

    pinecone_client_manager = PineconeClientManager(
        config.pinecone
    )

    vector_store = PineconeVectorStore(
        config=config.pinecone,
        client_manager=pinecone_client_manager,
    )

    logger.success("Vector store ready")

    # --------------------------------------------------
    # 6. Retrievers
    # --------------------------------------------------

    bm25 = BM25Retriever(chunks)

    dense = DenseRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    rrf = RRFusion(k=60)

    logger.success("Retrievers ready")

    # --------------------------------------------------
    # 7. Cross Encoder
    # --------------------------------------------------

    reranker = CrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L6-v2",
        device="cpu",
        max_length=512,
    )

    logger.success("Reranker ready")

    # --------------------------------------------------
    # 8. Context Builder
    # --------------------------------------------------

    context_builder = ContextBuilder()

    # --------------------------------------------------
    # 9. Groq LLM
    # --------------------------------------------------

    groq_client_manager = GROQClientManager(
        config.groq
    )

    rag_llm = RAGLLM(
        config=config.groq,
        client=groq_client_manager,
    )

    logger.success("RAG LLM ready")

    # --------------------------------------------------
    # 10. Orchestrator
    # --------------------------------------------------

    orchestrator = RAGOrchestrator(
        classifier=classifier,
        bm25=bm25,
        dense=dense,
        rrf=rrf,
        knowledge_base=knowledge_base,
        reranker=reranker,
        context_builder=context_builder,
        rag_llm=rag_llm,
        retrieval_top_k=config.retrieval.top_k,
        rerank_top_k=5,
        retrieval_confidence_threshold=0.60,
    )

    logger.success("RAG pipeline initialized successfully")

    return orchestrator, config