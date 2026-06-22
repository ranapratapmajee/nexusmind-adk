# PLANNING.md: Project NexusMind (Chatbot: Nexa)

This document serves as the master engineering design blueprint, data state ledger, and architectural roadmap for the **NexusMind** multi-agent platform. Built natively on the **Google Agent Development Kit (ADK 2.0)**, this system unifies a Neo4j knowledge graph, a Chroma vector store, a local **Ollama inference engine (`qwen2.5-coder:7b`)**, and **Gemini Cloud (`gemini-2.5-flash`)** into a highly adaptive, memory-driven, and interactive Cognitive AI system.

---

## 1. Architectural Topology

NexusMind cleanly splits into two major functional pipelines managed by a central orchestration brain:

1. **Asynchronous Background PDF Ingestion Pipeline**: Extracts text layouts, generates sliding chunks, maps graph entities/relationships, validates schema types, and indexes data down into the target databases.
2. **Stateful Retrieval & Multi-Hop Reasoning Pipeline**: Evaluates inbound query safety via guardrails, determines user intentions, applies Reciprocal Rank Fusion (RRF) across multi-source contexts, runs Chain-of-Thought (CoT) tracking, and serves responsive chat text paired with interactive cross-question suggestion pills.

### 1.1 Macro-System Communication Subsystems

```
+-----------------------------------------------------------------------+
|                         Streamlit Frontend Client                     |
+-----------------------------------------------------------------------+
                                    |
                                    v [User Prompt / Binary Streams]
+-----------------------------------------------------------------------+
|                    1. GuardrailAgent (Local Model)                    |
|       - Performs real-time validation checks for text compliance     |
+-----------------------------------------------------------------------+
                                    |
                        +-----------+-----------+
                        | [Passed Validation]   | [Blocked / Violation]
                        v                       v
+---------------------------------------+   +---------------------------+
|      2. Control Engine Brain (Core)   |   | Safety Rejection Payload   |
|  - Inbound stream pattern identifier  |   +---------------------------+
+---------------------------------------+
                        |
      +-----------------+-----------------+------------------------+
      | (Intent: CASUAL_CHAT)             | (Intent: RESEARCH)     | (Intent: INGESTION_UPLOAD)
      v                                   v                        v
+---------------------------+   +--------------------------+ +--------------------------+
|  FastConversationalAgent  |   |  DeepResearchPipeline    | | Enterprise PDF Ingest  |
|                           |   | (SequentialWorkflow V2)  | | Pipeline (Sequential)  |
| - Generates lightweight   |   +--------------------------+ +--------------------------+
|   conversational turn     |                 |                           |
|   using history buffer    |                 v                           v
+---------------------------+       A. PlannerAgent             1. PDFLayoutParserAgent
                                              |                           |
                                              v                           v
                                    B. RetrievalAgent           2. SlidingWindowChunker
                                              |                           |
                                              v                           v
                                    C. KnowledgeFusion (RRF)    3. EntityExtractorAgent
                                              |                           |
                                              v                           v
                                    D. ReasonerAgent (CoT)      4. RelationExtractorAgent
                                              |                           |
                                              v                           v
                                    E. ResponseAgent (Pills)    5. KgValidatorAgent
                                              |                           |
                                              v                           v
                                        [Gemini / Ollama]       6. IndexerAgent (Commits)
                                              |                           |
                                              +-------------+-------------+
                                                            |
                                               +------------+------------+
                                               |                         |
                                               v                         v
                                    +--------------------+    +--------------------+
                                    |  ChromaDB Vector   |    |     Neo4j Graph    |
                                    |   (Dense Store)    |    |  (Knowledge Base)  |
                                    +--------------------+    +--------------------+

```

---

## 2. Granular Agent & Workflow Responsibilities

### 2.1 The Core Orchestration and Safety Layer

* **`GuardrailAgent`**: The front-line validation firewall. It scans incoming text sequences for prompt injections, system access tokens, or sensitive leaks. If a threat is detected, it returns a `SECURITY_REFUSAL` payload.
* **`ControlEngine` / `RouterAgent**`: The semantic router. It identifies structural header blocks (like `DOCUMENT_INJECT_STREAM:`) or conversational patterns to route traffic into the appropriate sub-graphs.
* **`FastConversationalAgent`**: A lightweight local handler that responds to chitchat, greetings, or basic system requests instantly.

### 2.2 The 6-Stage Background Ingestion Workflow (`ingest_pipeline.py`)

* **Stage 1 (`PDFLayoutParserAgent`)**: Uses `pypdf` extraction to clean running headers and convert binary payloads into raw structural strings.
* **Stage 2 (`SlidingWindowChunkerAgent`)**: Splits text blocks into sliding windows (500 characters, 100 overlap) to preserve sentence contexts.
* **Stage 3 (`EntityExtractorAgent`)**: Identifies domain nodes (e.g., `SYSTEM`, `TECHNOLOGY`, `PERSON`).
* **Stage 4 (`RelationExtractorAgent`)**: Maps structural links between elements using `SCREAMING_SNAKE_CASE` connection predicates.
* **Stage 5 (`KgValidatorAgent`)**: Enforces validation constraints, checks connections, and drops orphaned properties.
* **Stage 6 (`IndexerAgent`)**: Executes `chroma_write_tool` and `neo4j_merge_tool` to write data to both database clusters concurrently.

### 2.3 The 5-Stage Multi-Hop Reasoning Workflow (`master_pipeline.py`)

* **Stage 1 (`PlannerAgent`)**: Deconstructs query requests into structured lookup criteria.
* **Stage 2 (`RetrievalAgent`)**: Calls active database search tools (`chroma_tool`, `neo4j_tool`, `web_tool`) concurrently.
* **Stage 3 (`KnowledgeFusionAgent`)**: Merges overlapping outputs mathematically using the **Reciprocal Rank Fusion (RRF)** scoring matrix:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$


* **Stage 4 (`ReasonerAgent`)**: Executes multi-hop Chain-of-Thought (CoT) tracking to resolve distant connections.
* **Stage 5 (`ResponseAgent`)**: Combines the output into a markdown report with citations, and generates 3 context-aware clickable cross-question pills.

---

## 3. Database Sync & Storage Strategy

### 3.1 ChromaDB Indexing

* **Embeddings**: Generated using local Ollama model hooks (`nomic-embed-text`) via an HTTP endpoint.
* **Storage**: Persistent storage mounted inside the container filesystem to maintain indexing integrity over reboots.

### 3.2 Neo4j Graph Topology

* **Domain Primitives**: Enforces explicit uniqueness constraints across `:Entity(id)` profiles to prevent duplicate records.
* **Data Mutation**: Uses transactional Cypher `MERGE` statements inside the service driver layer to insert nodes and links safely.

---

## 4. Finalized Directory Layout Blueprint

```text
nexusmind-adk/                             # Root workspace directory
├── .env                                   # Credentials, provider endpoints, and infrastructure ports
├── docker-compose.yaml                    # Multi-container orchestration (Chroma, Neo4j, Redis, Postgres)
├── pyproject.toml                         # Hatchling workspace dependencies (UV-compatible)
├── uv.lock                                # Locked dependency manifest
├── main.py                                # Pre-flight diagnostic network tester
├── streamlit_app.py                       # Client chat presentation interface & binary uploader
│
├── config/                                # Configuration Validation Layer
│   └── settings.py                        # Pydantic environment verification manager
│
├── app/                                   # Core Application Package Engine
│   ├── __init__.py                        # Core application module exporter
│   │
│   ├── core/                              # Orchestration System Brain
│   │   ├── control_engine.py              # Rule-based intent analyzer
│   │   └── llm_router.py                  # Dynamic model tier calculator
│   │
│   ├── models/                            # Pydantic Structured Outputs Contracts
│   │   ├── chat_state.py                  # RAG reasoning state schemas
│   │   └── ingest_state.py                # Structural entity triplet schemas
│   │
│   ├── infrastructure/                    # Low-Level Concrete Database Drivers
│   │   ├── chroma_service.py              # ChromaDB vector client wrapper & Ollama encoder
│   │   └── neo4j_service.py               # Bolt-protocol session connection pool manager
│   │
│   ├── tools/                             # Functional MCP System Registries
│   │   ├── indexer_tools.py               # Low-level write and data-mutation operations
│   │   └── mcp_registry.py                # Low-level read and context-gathering tools
│   │
│   ├── prompts/                           # Instruction Template Vault
│   │   └── system_prompts.py              # Central prompt library
│   │
│   ├── workflows/                         # Graph Execution Workflow Controllers
│   │   ├── ingest_pipeline.py             # 6-stage background document indexing manager
│   │   └── master_pipeline.py             # Global brain dynamic routing manager
│   │
│   └── agents/                            # Declarative ADK Framework Agent Primitives
│       ├── fast_agent.py                  # Lightweight conversational turn engine
│       ├── guardrail_agent.py             # Safety security barrier proxy
│       ├── ingest_nodes.py                # 6 document ingestion indexing agents
│       ├── research_nodes.py              # 5 research multi-hop retrieval agents
│       └── router_agent.py                # Semantic intent analysis agent
│
└── tests/                                 # Automated Validation Layer
    └── integration/                       # End-to-End Test Modules
        └── test_pipeline.py               # Async multi-agent transaction test suite

```