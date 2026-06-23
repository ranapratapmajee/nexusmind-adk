# Project NexusMind (Chatbot: Nexa)

This document serves as the master engineering design blueprint, data state ledger, and architectural roadmap for the **NexusMind** multi-agent platform. Built natively on the **Google Agent Development Kit (ADK)** framework, this system unifies an enterprise Neo4j knowledge graph, a Chroma vector store, a local **Ollama inference engine (`qwen2.5-coder:7b`)**, and **Gemini Cloud (`gemini/gemini-2.5-flash`)** into a highly adaptive, memory-driven, and interactive Cognitive AI system.

---

## 1. Architectural Topology

NexusMind cleanly decouples the background ingestion thread completely out of the front-facing core conversational routing loop to support atomic, low-overhead operations:

1. **Decoupled File-Driven Ingestion Pipeline**: Runs strictly asynchronously on its own dedicated runtime lane (`process_file_ingestion`). It extracts PDF layout text, maps entities/relationships, validates graphs entirely inline within memory to prevent tool-hallucination crashes, and pushes records directly into storage engine blocks.
2. **Stateful Conversation & Research Graph Loop**: Evaluates inbound user queries via frontend Streamlit interfaces or backend workflows, passes prompts through deep security guardrail monitors, automatically assigns model targets based on `.env` switch rules, and routes safely between simple chit-chat turn engines and deep RRF multi-hop research networks.

### 1.1 Macro-System Communication Subsystems

```
+--------------------------------------------------------------------------------------------------+
|                                    Presentation Presentation Layers                              |
|         [Streamlit Dashboard Interface UI]             [scripts/ingest.py CLI Ingestion Tool]   |
+--------------------------------------------------------------------------------------------------+
                        |                                                       |
     (Conversational Input String Payload)                             (Target PDF File Argument)
                        |                                                       |
                        v                                                       v
+--------------------------------------------------+         +-------------------------------------+
|        app/backend_engine.py Server Module       |         |   data/ Storage Directory Landing   |
|   - Runs execute_nexus_engine() sessions         |         |   - Houses raw local physical assets|
+--------------------------------------------------+         +-------------------------------------+
                        |                                                       |
                        v                                                       v
+--------------------------------------------------+         +-------------------------------------+
|      1. SystemRootGateway Workflow Matrix        |         |    process_file_ingestion Worker    |
|   - Drives top-level core graph traffic routing  |         |   - Reads layout bytes directly     |
+--------------------------------------------------+         +-------------------------------------+
                        |                                                       |
                        v [Scans Input Stream]                                  |
+--------------------------------------------------+                                    |
|              2. GuardrailAgent Node              |                                    |
|   - Double-checks prompt injections/exploits     |                                    |
+--------------------------------------------------+                                    |
            |                            |                                              |
    [Unsafe Blocked]              [Safe Passed]                                         |
            v                            v                                              |
+-----------------------+   +----------------------------------+                        |
|  handling_refusal_node|   |     3. ControlEngineRouter       |                        |
| - Intercepts execution|   | - Diverges CHAT vs RESEARCH path |                        |
+-----------------------+   +----------------------------------+                        |
                                 |                    |                                 |
         +-----------------------+                    +--------+                        |
         | (Intent: CHAT_PATH)                                 | (Intent: RESEARCH_PATH) |
         v                                                     v                        v
+---------------------------+                        +--------------------------+ +--------------------------+
|  FastConversationalAgent  |                        |  DeepResearchPipeline    | | IngestionPipeline Workflow|
|                           |                        |  (app/research_pipeline) | |  (app/ingest_pipeline)   |
| - Generates lightweight   |                        +--------------------------+ +--------------------------+
|   conversational response |                                      |                           |
|   using inline instructions|                                     v                           v
+---------------------------+                            A. PlannerAgent             1. PDFLayoutParserAgent
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
                                                         E. ResponseAgent (Pills)    5. KgValidatorAgent (Inline)
                                                                   |                           |
                                                                   v                           v
                                                             [Model Target]          6. IndexerAgent (Commits)
                                                                   |                           |
                                                                   +-------------+-------------+
                                                                                 |
                                                                    +------------+------------+
                                                                    |                         |
                                                                    v                         v
                                                         +--------------------+    +--------------------+
                                                         |  ChromaDB Vector   |    |     Neo4j Graph    |
                                                         |  (chroma_write)    |    |   (neo4j_merge)    |
                                                         +--------------------+    +--------------------+

```

---

## 2. Granular Agent & Workflow Responsibilities

### 2.1 The Core Gateway Routing and Safety Layer (`root_gateway.py`)

* **`GuardrailAgent`**: Handled via your active `llm` model target. It performs real-time validation checks for prompt injections, system access tokens, or sensitive leaks. If a threat pattern matches, it short-circuits execution and hands off a custom error block to `handling_refusal_node`.
* **`ControlEngineRouter`**: Orchestration brain evaluating transactional intentions. It classifies queries into specialized routes (`CHAT_PATH` or `RESEARCH_PATH`) and dynamically updates framework instructions while stripping old headers to avoid token bleeding.
* **`FastConversationalAgent`** (Nexa): A lightweight handler that responds to chat openings, greetings, or basic system requests with an approachable, peer-like tone.

### 2.2 The 6-Stage Background Ingestion Workflow (`ingest_pipeline.py`)

* **Stage 1 (`PDFLayoutParserAgent`)**: Unpacks structural binary contents and streams raw text logs.
* **Stage 2 (`SlidingWindowChunkerAgent`)**: Generates 500-character windows with a continuous 100-character overlapping tail to preserve context metrics.
* **Stage 3 (`EntityExtractorAgent`)**: Mines explicit semantic entity definitions (`SYSTEM`, `TECHNOLOGY`, `PERSON`, `TOOL`).
* **Stage 4 (`RelationExtractorAgent`)**: Explores directional linkages using capitalized `SCREAMING_SNAKE_CASE` connection predicates.
* **Stage 5 (`KgValidatorAgent`)**: Enforces validation constraints. **Crucial Rule:** Cleans records entirely inline within context memory to eliminate tool-hallucination crashes (such as inventing imaginary tool functions like `validate_graph`).
* **Stage 6 (`IndexerAgent`)**: Strict structural parsing broker. It receives pristine JSON datasets and invokes data write tools (`chroma_write_tool` and `neo4j_merge_tool`).

### 2.3 The 5-Stage Multi-Hop Reasoning Workflow (`research_pipeline.py`)

* **Stage 1 (`PlannerAgent`)**: Deconstructs query requests into structured lookup criteria plans.
* **Stage 2 (`RetrievalAgent`)**: Calls active database search tools (`chroma_tool`, `neo4j_tool`, `web_tool`) concurrently.
* **Stage 3 (`KnowledgeFusionAgent`)**: Merges overlapping outputs mathematically using the **Reciprocal Rank Fusion (RRF)** scoring matrix:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$

* **Stage 4 (`ReasonerAgent`)**: Executes multi-hop Chain-of-Thought (CoT) tracking to resolve distant hidden linkages.
* **Stage 5 (`ResponseAgent`)**: Combines the output into a markdown report with bracketed citations, and generates 3 context-aware follow-up suggestion pills.

---

## 3. Database Sync & Storage Strategy

### 3.1 ChromaDB Indexing

* **Data Entry Sanitation**: `chroma_write_tool` features defensive text-block split catchers that can ingest raw strings or structured dictionary arrays without throwing format attribute errors.
* **Persistence**: Persistent storage is mounted inside the container filesystem to maintain indexing integrity over container restarts.

### 3.2 Neo4j Graph Topology & Defensive Parsing

* **Defensive Tool Layers**: `neo4j_merge_tool` utilizes custom runtime JSON parsers (`_ensure_list_of_dicts`) that catch raw stringified LLM outputs, strip markdown decorators (````json`), and automatically rebuild valid node lists on the fly.
* **Data Mutation**: Enforces distinct labeled node creations using Cypher `MERGE` transactions, populating custom label mappings (`Technology`, `Feature`, `Component`, `Tool`, `Library`) based on dynamic model annotations.

---

## 4. Finalized Directory Layout Blueprint

The production layout maps out a flat workspace structure, intentionally minimizing subdirectory levels to ensure transparent tracing overhead:

```text
nexusmind-adk/                             # Root workspace repository directory
├── pyproject.toml                         # Project metadata and toolchain dependencies configurations
├── uv.lock                                # Fast internal locked dependency manifest
├── docker-compose.yaml                    # Local multi-container vector & graph database specs
├── main.py                                # Pre-flight hardware connectivity verification & diagnostics
├── run.sh                                 # Global environment check & runtime service execution gateway
├── streamlit_app.py                       # Client interface dashboard (Strictly UI Staging Copy Operations)
├── PLANNING.md                            # Blueprint, task items, and technical notes (This Document)
├── LICENSE                                # Repository permission rights
├── nexusmind_runtime.log                  # Rolling backend operational tracking output trace
│
├── config/                                # System Settings Subsystem
│   ├── __init__.py                        # Config initiation block
│   └── settings.py                        # Pydantic Settings environment loader, dotenv bootstrap injector
│
├── data/                                  # Ingestion Landing Strip Directory (Isolated)
│   └── rag_book.pdf                       # Target raw binary file copies prepared for parser pipelines
│
├── scripts/                               # Production Operational Shell Wrappers
│   ├── __init__.py                        # Script pack exports
│   ├── ingest.py                          # Streamlined CLI module triggering file-driven ingest workers
│   └── test_connection.py                 # Network link sanity verification scripts
│
├── app/                                   # Unified Core Backend Workspace Module
│   ├── __init__.py                        # Package init exports
│   ├── agent.py                           # Framework bridge file re-exporting root_agent for adk web UI
│   ├── backend_engine.py                  # Core Engine (Manages Chat Sessions & process_file_ingestion)
│   ├── root_gateway.py                    # Gateway orchestrator (Guardrail, Router, and Chat/Research paths)
│   ├── research_pipeline.py               # 5-stage deep analytical reasoning workflow layout
│   ├── ingest_pipeline.py                 # 6-stage background document parsing & graph ETL compiler
│   ├── infrastructure.py                  # PyPDF extractors, Chroma HTTP clients, and Neo4j connection poolers
│   ├── tools.py                           # Functional read/write database tool sets bridged to ADK wrappers
│   └── states.py                          # Unified prompt instruction vault and structured Pydantic schemas
│
└── storage/                               # Persistent Database Container Storage Volumes
    ├── chroma_data/                       # ChromaDB vector cluster data store volume files
    ├── pg_data/                           # Regional relational relational database mapping data
    ├── redis_data/                        # In-memory session tracking and cache logs
    └── neo4j_data/                        # Neo4j Graph DBMS Active Schema Files
        ├── dbms/                          # System security configurations (auth.ini)
        ├── databases/                     # Internal transactional graphs database mapping paths
        │   ├── neo4j/                     # Core default operational data store nodes
        │   └── system/                    # Database system catalog definitions
        └── transactions/                  # Uncommitted operational log structures
            ├── neo4j/                     # Runtime transactional queries logs
            └── system/                    # Framework metadata lifecycle commits

```

---

## 5. Development & Telemetry Tracking Roadmap

* **`EXECUTION_MODE` Verification**: Maintain complete verification tests ensuring that switching between `LOCAL` and `CLOUD` execution modes re-allocates all downstream workflow agent model references (`local_llm` vs `cloud_llm`) dynamically without system degradation.
* **Observability Checks**: Keep `app/agent.py` perfectly synched with `root_gateway.py` to allow the built-in developer UI tool stack (`uv run adk web`) to chart graphs, evaluate prompt lengths, and visualize token generations across multi-agent environments seamlessly.

---