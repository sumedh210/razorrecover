# RazorRecover

### AI-Powered Revenue Recovery Agent

RazorRecover is an AI-driven payment recovery system designed to recover failed payments while keeping financial actions deterministic, policy-controlled, auditable, and measurable.

The core design principle is:

> **LLM proposes → Policy decides → Tool executes → Auditor verifies → Metrics measure**

The system combines an LLM reasoning agent, retrieval-augmented generation (RAG), deterministic recovery policies, MCP-based payment tools, a payment simulator, and a real-time observability dashboard.

---

## Why RazorRecover?

Failed payments represent immediate revenue at risk, but blindly retrying payments is unsafe and inefficient.

Different failures require different recovery strategies:

- transient gateway failures may be retried
- bank failures may be routed through another path
- customer authentication failures may require a recovery link
- risky or high-value payments may require escalation
- payments that have exceeded retry limits must stop

RazorRecover separates **reasoning** from **authorization and execution** so that the LLM never directly controls financial actions.

---

## Architecture

```text
                         ┌──────────────────────┐
                         │   Failed Payments    │
                         │      SQLite DB       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Recovery Agent     │
                         │      (LLM)           │
                         └──────────┬───────────┘
                                    │
                           diagnose + propose
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     RAG System       │
                         │                      │
                         │ Query Classifier     │
                         │ BM25 / Dense         │
                         │ RRF                  │
                         │ Cross-Encoder        │
                         │ (reranker)           │
                         │ Knowledge Base       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Policy Engine      │
                         │   Deterministic      │
                         └──────────┬───────────┘
                                    │
                              allowed action
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     MCP Tools        │
                         │                      │
                         │ Retry                │
                         │ Route                │
                         │ Recovery Link        │
                         │ Escalate             │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Payment Database   │
                         │     + Outcome        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      Auditor         │
                         │ Compliance + Revenue │
                         │      Verification    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     Dashboard        │
                         │ Revenue Recovered    │
                         │ Recovery Rate        │
                         │ Escalations          │
                         │ Compliance            │
                         └──────────────────────┘
```

---

## Key Design Principle

### LLM proposes

The LLM analyzes the payment failure and proposes an action:

```text
RETRY_PAYMENT
ROUTE_PAYMENT
SEND_RECOVERY_LINK
ESCALATE
```

It can use the RAG system to retrieve payment failure and recovery guidance.

### Policy decides

A deterministic policy engine evaluates the proposed action against merchant safety rules.

Examples:

- maximum retry limit
- high-value payment override
- payment status validation
- risk escalation
- failure-specific recovery rules

The LLM cannot bypass these rules.

### MCP executes

Only an authorized action reaches the MCP execution layer.

Available tools:

```text
get_payment
retry_payment
route_payment
send_recovery_link
escalate_payment
```

The tools update the simulated payment system and record recovery actions.

### Auditor verifies

Every processed payment is audited after the action.

The auditor checks:

- policy compliance
- executed action vs authorized action
- recovery outcome
- revenue accounting
- stopping/escalation behavior

Audit results are persisted in the database.

---

# RAG Pipeline

RazorRecover uses a multi-stage retrieval pipeline for payment failure diagnosis.

```text
User / Agent Query
        │
        ▼
Query Classifier
        │
        ├── Lexical ──────► BM25
        │
        ├── Semantic ─────► Dense Retrieval
        │
        └── Mixed ────────► BM25 + Dense
                              │
                              ▼
                     Reciprocal Rank Fusion
                              │
                              ▼
                       Cross-Encoder
                         Reranking
                              │
                              ▼
                       Top Documents
                              │
                              ▼
                         RAG LLM
```

The classifier selects the retrieval strategy based on the query.

Low-confidence classification falls back to mixed retrieval.

The knowledge base contains payment API documentation, payment failure information, error codes, retry guidance, webhooks, subscriptions, refunds, and related Razorpay documentation.

---

# Query Classifier

The retrieval router uses a trained classifier exported to ONNX for CPU inference.

Measured on the development evaluation set:

| Metric | Score |
|---|---:|
| Intent Accuracy | 84.76% |
| Intent Macro-F1 | 84.68% |
| Retrieval Mode Accuracy | 70.48% |
| Retrieval Mode Macro-F1 | 70.57% |
| Average Inference | ~68 ms |

The ONNX model is included in the repository through Git LFS.

---

# Recovery Policy

The policy engine is deterministic and independent of the LLM.

Examples of policy behavior:

| Failure | Proposed Action | Policy Behavior |
|---|---|---|
| Gateway technical error | Retry | Allow retry |
| Payment timeout | Retry | Allow retry |
| Incorrect OTP | Retry | Replace with recovery link |
| Authentication failure | Retry | Replace with recovery link |
| Bank payment failure | Retry | Route/retry |
| Risk check failure | Any | Escalate |
| Retry limit exceeded | Retry | Escalate |
| High-value payment | Any | Escalate |
| Terminal payment | Any | Stop |

This ensures the model can reason about a payment without having authority to perform an unsafe action.

---

# MCP Execution Layer

RazorRecover uses MCP to expose payment recovery operations as tools.

The agent does not directly mutate the database.

Instead:

```text
Agent
  │
  │ proposed action
  ▼
Policy Engine
  │
  │ authorized action
  ▼
MCP Tool
  │
  ▼
Payment System
```

This creates a clean separation between reasoning and execution.

The current payment environment is a synthetic simulator intended for evaluation and demonstration.

---

# Audit & Observability

The system records an audit event for every processed recovery attempt.

The dashboard exposes:

- Payments processed
- Failed payments
- Revenue at risk
- Revenue recovered
- Recovery rate
- Successful recoveries
- Escalations
- Audited payments
- Policy violations
- Compliance rate

The recovery activity view also shows:

```text
Failure → Proposed Action → Policy Decision → Execution → Result → Audit
```

This makes individual recovery decisions explainable and traceable.

---

# Project Structure

```text
razorrecover/
│
├── config/
│   └── config.example.yaml
│
├── kb/
│   ├── chunks/
│   ├── documents/
│   └── ingestion/
│
├── ml/
│   ├── models/
│   │   └── query_classifier/
│   │       └── onnx/
│   └── notebooks/
│
├── simulator/
│   └── database/
│
├── src/
│   ├── agent/
│   │   ├── agent_llm.py
│   │   ├── auditor.py
│   │   ├── bootstrap.py
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   ├── policy.py
│   │   ├── state.py
│   │   └── worker.py
│   │
│   ├── classifier/
│   │
│   ├── dashboard/
│   │
│   ├── embeddings/
│   │
│   ├── knowledge/
│   │
│   ├── llm/
│   │
│   ├── mcp/
│   │
│   ├── rag/
│   │
│   ├── retrieval/
│   │
│   ├── simulation/
│   │
│   └── vector_store/
│
├── pyproject.toml
├── requirements.txt
├── uv.lock
└── README.md
```

---

# Tech Stack

- Python
- uv
- Groq
- NVIDIA Embeddings
- Pinecone
- ONNX Runtime
- PyTorch
- LangGraph
- FastMCP
- BM25
- Reciprocal Rank Fusion
- Cross-Encoder reranking
- SQLite
- NiceGUI

---

# Setup

## 1. Clone

```bash
git clone https://github.com/sumedh210/razorrecover.git
cd razorrecover
```

## 2. Install dependencies

Using uv:

```bash
uv sync
```

Or using pip:

```bash
pip install -r requirements.txt
```

## 3. Configure credentials

Copy the example configuration:

```bash
cp config/config.example.yaml config/config.yaml
```

On Windows PowerShell:

```powershell
Copy-Item config/config.example.yaml config/config.yaml
```

Set the required environment variables in `.env`.

Required services:

- Groq
- NVIDIA Embeddings
- Pinecone

Never commit API keys or the local `config.yaml`.

---

# Running the System

## Start the recovery worker

```bash
uv run python -m src.agent.worker
```

The worker continuously scans for failed payments and processes them through the recovery graph.

## Start the dashboard

In another terminal:

```bash
uv run python -m src.dashboard.app
```

Then open:

```text
http://localhost:8080
```

---

# Recovery Graph

The agent workflow is:

```text
START
  │
  ▼
Load Payment
  │
  ▼
Agent Reasoning
  │
  ▼
Policy Engine
  │
  ├──────────────► Auditor ──► END
  │
  ▼
Execute Authorized Action
  │
  ▼
Observe Payment
  │
  ▼
Auditor
  │
  ▼
END
```

The stop path is also audited, ensuring that policy-denied actions are visible and measurable.

---

# Important Safety Boundary

RazorRecover is intentionally designed so that the LLM is **not the authority over financial actions**.

The model can:

- diagnose
- retrieve information
- reason
- propose an action

The model cannot directly:

- retry a payment
- route a payment
- send a recovery link
- escalate a payment
- modify payment state

Those operations require deterministic policy authorization and are executed through tools.

---

# Evaluation

The system is designed around measurable revenue recovery rather than only conversational quality.

Primary metrics include:

```text
Revenue at Risk
Revenue Recovered
Recovery Rate
Successful Recoveries
Escalations
Audit Coverage
Policy Violations
Compliance Rate
```

The dashboard provides live visibility into these metrics while the recovery worker processes the synthetic payment batch.

---

# Disclaimer

This project uses a synthetic payment environment for demonstration and evaluation.

Recovery success probabilities in the simulator are artificial and are **not representative of real-world payment recovery rates**.

No real customer payments are processed by this project.

---

# License

This project is intended as a student buildathon project and demonstration of AI-assisted revenue recovery architecture.
