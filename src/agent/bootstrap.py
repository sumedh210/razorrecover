from loguru import logger

from src.rag.bootstrap import build_rag
from src.agent.agent_llm import AgentLLM
from src.agent.policy import PolicyEngine
from src.mcp.tools import create_rag_tool


def build_agent():
    logger.info("Starting Revenue Recovery Agent initialization...")

    # --------------------------------------------------
    # 1. Build RAG once
    # --------------------------------------------------

    rag_orchestrator, config = build_rag()

    logger.success("RAG system ready")

    # --------------------------------------------------
    # 2. Build Agent LLM once
    # --------------------------------------------------

    agent_llm = AgentLLM(config.groq)

    logger.success("Agent LLM ready")

    # --------------------------------------------------
    # 3. Build Policy Engine once
    # --------------------------------------------------

    policy_engine = PolicyEngine()

    logger.success("Policy engine ready")

    # --------------------------------------------------
    # 4. Create RAG tool using the existing RAG
    # --------------------------------------------------

    rag_tool = create_rag_tool(rag_orchestrator)

    logger.success("RAG tool ready")

    # --------------------------------------------------
    # 5. Build agent graph
    # --------------------------------------------------

    from src.agent.graph import build_recovery_graph

    agent = build_recovery_graph(
        agent_llm=agent_llm,
        rag_tool=rag_tool,
        policy_engine=policy_engine,
    )

    logger.success("Revenue Recovery Agent initialized successfully")

    return agent