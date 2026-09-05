from functools import partial
from langgraph.graph import END, START, StateGraph
from src.agent.state import AgentState
from src.agent.nodes import( load_payment_node,
    agent_reasoning_node,
    policy_node,
    execute_action_node,
    observe_payment_node,
    auditor_node, )

def build_recovery_graph(agent_llm, rag_tool, policy_engine):

    graph=StateGraph(AgentState)

    graph.add_node(
        "load_payment",
        load_payment_node,
    )

    graph.add_node(
        "agent_reasoning",
        partial(
            agent_reasoning_node,
            agent_llm=agent_llm,
            rag_tool=rag_tool,
        ),
    )

    graph.add_node(
        "policy",
        partial(
            policy_node,
            policy_engine=policy_engine,
        ),
    )

    graph.add_node(
        "execute_action",
        execute_action_node,
    )

    graph.add_node(
        "observe_payment",
        observe_payment_node,
    )

    graph.add_node(
        "auditor",
        auditor_node,
    )

    graph.add_edge(
        START, 
        "load_payment"
    )

    graph.add_conditional_edges(
        "load_payment",
        should_reason,
        {
            "reason": "agent_reasoning",
            "stop": END,
        },
    )

    graph.add_edge(
        "agent_reasoning",
        "policy",
    )

    graph.add_conditional_edges(
        "policy",
        should_execute,
        {
            "execute": "execute_action",
            "stop": "auditor",
        },
    )

    graph.add_edge(
        "execute_action",
        "observe_payment",
    )

    graph.add_edge(
        "observe_payment",
        "auditor",
    )

    graph.add_edge(
        "auditor",
        END,
    )

    return graph.compile()

def should_reason(
    state: AgentState,
) -> str:

    if state.get("should_continue", False):
        return "reason"

    return "stop"


def should_execute(
    state: AgentState,
) -> str:

    action = state.get("policy_decision")

    if action in {
        "RETRY_PAYMENT",
        "ROUTE_PAYMENT",
        "SEND_RECOVERY_LINK",
        "ESCALATE",
    }:
        return "execute"

    return "stop"