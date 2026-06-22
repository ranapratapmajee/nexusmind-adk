# 🧠 NexusMind Enterprise Architecture — Powered by Nexa

NexusMind is an enterprise-grade GraphRAG (Knowledge Graph + Vector Retrieval-Augmented Generation) platform engineered using the native **Google Agent Development Kit (ADK)** framework. The architecture completely decouples background knowledge graph synthesis from real-time user query traversal threads.

By unifying local inference engines (**Ollama: `qwen2.5-coder:7b`** for privacy, local embedding workflows, and edge-speed calculations) with high-context cloud endpoints (**Gemini Cloud** for deep analytical orchestration and dynamic tool-routing), NexusMind provides a stateful, interactive experience. The system's central concierge, **Nexa**, supports multi-hop reasoning, unified document indexing, and user-driven exploratory follow-ups.

---

## 1. System Topology & Architectural Flows

### 1.1 Macro-System Communication Subsystems

The diagram below details the end-to-end transaction paths for raw document ingestion streams and runtime multi-agent retrieval loops.

```mermaid
graph TD
    %% Component Style Classes
    classDef client fill:#2d3436,stroke:#dfe6e9,stroke-width:2px,color:#fff;
    classDef orchestrator fill:#0984e3,stroke:#74b9ff,stroke-width:2px,color:#fff;
    classDef control fill:#6c5ce7,stroke:#a29bfe,stroke-width:2px,color:#fff;
    classDef workflow fill:#00b894,stroke:#55efc4,stroke-width:2px,color:#fff;
    classDef guardrail fill:#d35400,stroke:#e67e22,stroke-width:3px,color:#fff;
    classDef agent fill:#e17055,stroke:#fab1a0,stroke-width:2px,color:#fff;
    classDef tool fill:#fdcb6e,stroke:#ffeaa7,stroke-width:2px,color:#2d3436;
    classDef storage fill:#b2bec3,stroke:#dfe6e9,stroke-width:2px,color:#2d3436;
    classDef compute fill:#d63031,stroke:#ff7675,stroke-width:2px,color:#fff;

    %% Presentation Layer
    UI[Streamlit UI & Interactive Chat]:::client <--> |Prompts & Cross-Questions| Gateway[SystemRootGateway Workflow]:::orchestrator
    
    %% Intent Splitting & Control
    Gateway --> |Executes Scan| GuardrailNode[safety_guardrail_node]:::guardrail
    GuardrailNode -.-> |Unsafe: BLOCKED_PATH| Refusal[handling_refusal_node]:::control
    Refusal -.-> UI

    GuardrailNode --> |Safe: SECURE_PATH| Concierge[CentralOrchestrator Agent]:::orchestrator

    %% Central Orchestrator Tool Routing Decision Matrix
    Concierge --> |Tool: FastConversationalAgent| FastAgent[Fast Agent]:::agent
    Concierge --> |Tool: Ingestion-Pipeline| IngestFlow[Ingestion-Pipeline Workflow]:::workflow
    Concierge --> |Tool: DeepResearchPipeline| DeepResearch[DeepResearchPipeline Workflow]:::workflow

    %% Ingestion Pipeline 
    subgraph Ingestion_Pipeline ["Background PDF Ingestion Pipeline (app/ingest_pipeline.py)"]
        IngestFlow --> Parser[PDFLayoutParserAgent]:::agent
        Parser --> Chunker[SlidingWindowChunkerAgent]:::agent
        Chunker --> EntityExt[EntityExtractorAgent]:::agent
        EntityExt --> RelExt[RelationExtractorAgent]:::agent
        RelExt --> KGVal[KgValidatorAgent]:::agent
        KGVal --> Indexer[IndexerAgent]:::agent
    end

    %% Adaptive Runtime Multi-Agent Pipeline
    subgraph Reasoning_Pipeline ["Deep Research Pipeline (app/research_pipeline.py)"]
        DeepResearch --> Planner[PlannerAgent]:::agent
        Planner --> |Builds Search Plan| Retrieval[RetrievalAgent]:::agent
        
        %% Tool Registry
        subgraph ADK_Tool_Registry ["Data Tools Registry (app/tools.py)"]
            Retrieval --> CTool[chroma_tool]:::tool
            Retrieval --> NTool[neo4j_tool]:::tool
            Retrieval --> WTool[web_tool]:::tool
        end
        
        CTool --> Fusion[KnowledgeFusionAgent]:::agent
        NTool --> Fusion
        WTool --> Fusion
        
        Fusion --> |Applies Reciprocal Rank Fusion| Reasoner[ReasonerAgent]:::agent
        Reasoner --> |Multi-Hop Chain-of-Thought| Responder[ResponseAgent]:::agent
    end

    %% Storage Topology
    Indexer --> |chroma_write_tool| Chroma[(ChromaDB Vector Store)]:::storage
    Indexer --> |neo4j_merge_tool| Neo4j[(Neo4j Graph Database)]:::storage
    
    Neo4j -.-> NTool
    Chroma -.-> CTool

    %% Hybrid Compute Targets (Ollama + Gemini)
    FastAgent & Parser & Chunker & EntityExt & RelExt & KGVal & Indexer & Planner & Retrieval & Fusion & Reasoner --> LocalOllama[Local Ollama: qwen2.5-coder:7b]:::compute
    Concierge & Responder --> GeminiCloud[Gemini Cloud Engine]:::compute

    LocalOllama & GeminiCloud --> |Final Response Matrix| UI

```

### 1.2 System Runtime Interaction Loop

The sequence diagram below displays the step-by-step transaction lifecycle of an execution turn through the system layers:

```mermaid
sequenceDiagram
    autonumber
    actor User as Streamlit Client UI
    participant GW as SystemRootGateway (Workflow)
    participant SG as safety_guardrail_node
    participant CO as CentralOrchestrator (Gemini)
    participant EX as Selected Worker (Agent/Workflow Tool)
    participant INF as Infrastructure Service (Chroma/Neo4j)

    User->>GW: Post Raw Text Input or File Payload Stream
    GW->>SG: Run Defensive Safety Scan (via GuardrailAgent)
    alt Security Refusal Triggered (BLOCKED)
        SG-->>User: Short-Circuit Return Standard Security Policy Refusal Notice
    else Input Clean (SECURE_PATH)
        SG->>CO: Hand Off Control Matrix Payload
        CO->>CO: Evaluate Intent & Select Matching Registered Tool
        
        alt Option A: Conversational Intent
            CO->>EX: Delegate to FastConversationalAgent
            EX-->>User: Return Quick Text Turn Response
        else Option B: Document Ingestion Drop ('DOCUMENT_INJECT_STREAM:')
            CO->>EX: Route to Ingestion-Pipeline Workflow
            EX->>INF: Write Split Paragraph Chunks & Cypher Node Matrix
            INF-->>EX: Database Commit Summary Acknowledgments
            EX-->>User: Render Comprehensive Processing Report Status
        else Option C: Heavy Complex Analytics
            CO->>EX: Delegate to DeepResearchPipeline Workflow
            EX->>INF: Execute Retrieval Tools (chroma_tool, neo4j_tool, web_tool)
            INF-->>EX: Return Raw Semantic Context Fragments
            EX->>EX: Perform Reciprocal Rank Fusion (RRF) & Multi-Hop Reasoning (CoT)
            EX-->>User: Post Styled Report Markdown Answer + 3 Suggestion Pills
        end
    end

```

---

## 2. Minimalist Flat Project Layout

The repository utilizes an optimized, flat file topology structure designed to keep folder levels at a minimum for simple execution overhead tracking:

```text
nexusmind-adk/                             # Root workspace repository
├── pyproject.toml                         # Project metadata and toolchain dependencies configurations
├── uv.lock                                # Fast internal locked dependency manifest
├── docker-compose.yaml                    # Local multi-container vector & graph database specs
├── main.py                                # Pre-flight hardware connectivity verification & diagnostics
├── run.sh                                 # Global environment check & runtime service execution gateway
├── streamlit_app.py                       # Client interface dashboard and stream uploader layer
├── PLANNING.md                            # Blueprint, task items, and technical notes
├── LICENSE                                # Repository permission rights
│
├── config/                                # System Settings Subsystem
│   ├── __init__.py                        # Config initiation block
│   └── settings.py                        # Pydantic Settings environment loader and validator
│
├── app/                                   # Unified Core Logic Module Workspace
│   ├── __init__.py                        # Package init exports
│   ├── root_gateway.py                    # Top-level gateway graph orchestrator, safety proxy, and central hub
│   ├── research_pipeline.py               # 5-stage deep analytical reasoning workflow layout
│   ├── ingest_pipeline.py                 # 6-stage background document parsing & graph ETL compiler
│   ├── infrastructure.py                  # PyPDF extractors, Chroma HTTP clients, and Neo4j connection poolers
│   ├── tools.py                           # Functional read/write database tool sets bridged to ADK wrappers
│   └── states.py                          # Unified prompt instruction vault and structured Pydantic schemas
│
├── storage/                               # Persistent Storage Volumes
│   ├── chroma_data/                       # ChromaDB vector cluster storage directory
│   ├── neo4j_data/                        # Neo4j Graph DBMS schema volumes
│   ├── pg_data/                           # Regional database data mapping
│   └── redis_data/                        # In-memory session tracking files
│
└── tests/                                 # Automated Quality Assurance Layer
    └── __init__.py                        # Initialization module mapping for tests

```

---

## 3. Granular Agent & Pipeline Engineering Details

### 3.1 Asynchronous Background Ingestion Pipeline

Processes incoming files into high-fidelity context spaces across both storage engines simultaneously through 6 sequential steps:

1. **`PDFLayoutParserAgent`**: Unpacks layout byte streams and extracts clear, structured raw text.
2. **`SlidingWindowChunkerAgent`**: Partitions raw text into 500-character windows with a continuous 100-character overlapping tail to preserve context.
3. **`EntityExtractorAgent`**: Parses isolated text fragments to extract structural categories (`SYSTEM`, `TECHNOLOGY`, `PERSON`).
4. **`RelationExtractorAgent`**: Explores intersections between items to formulate connection predicates (`SCREAMING_SNAKE_CASE`).
5. **`KgValidatorAgent`**: Sanitizes the graph matrix by purging broken nodes or dangling connection lineages.
6. **`IndexerAgent`**: Interacts with the data write tools (`chroma_write_tool` and `neo4j_merge_tool`) to save components to disk.

### 3.2 Dynamic Retrieval & Multi-Hop Reasoning Pipeline

Processes deep exploratory queries by evaluating context indices through consecutive multi-agent tasks:

* **`PlannerAgent`**: Breaks compound query instructions into targeted search strategies.
* **`RetrievalAgent`**: Executes contextual tools (`chroma_tool`, `neo4j_tool`, `web_tool`) concurrently.
* **`KnowledgeFusionAgent`**: Deduplicates and cross-references multi-source outputs using **Reciprocal Rank Fusion (RRF)**:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$$

* **`ReasonerAgent`**: Performs a multi-hop Chain-of-Thought (CoT) sequence over the fused context to resolve hidden linkages.
* **`ResponseAgent`**: Builds the final response layout in markdown with bracketed source tracking and yields 3 interactive follow-up suggestion pills.

---

## 4. Installation & Production Launch Commands

### 1. Initialize Virtual Environment and Workspace Dependencies

Ensure you have `uv` installed. Run these commands from your root terminal:

```bash
# Create local virtual python environment sandbox
uv venv

# Activate local environment
source .venv/bin/activate  # Windows command: .venv\Scripts\activate

# Install dependencies and map the local project workspace
uv sync

```

### 2. Configure Environment Secrets

Ensure a `.env` file exists in your project's root directory containing these configurations:

```bash
# Model Specific Target Assignments
LOCAL_LLM_URL="http://localhost:11434"
OLLAMA_MODEL="qwen2.5-coder:7b"
GEMINI_MODEL="gemini-2.5-flash"

# Database Connection Infrastructure
CHROMA_HOST="localhost"
CHROMA_PORT=8000

NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your_neo4j_password"

```

### 3. Spin Up Storage Containers

Launch the core multi-container environment in background detached mode:

```bash
docker compose up -d

```

### 4. Execute Complete Pre-Flight Environment Launch

Use the automated orchestration script to test database availability and launch the application interface:

```bash
# Make the run script executable
chmod +x run.sh

# Launch pre-flight diagnostics and Streamlit interface
./run.sh

```

---

## 5. 🌐 Visualizing Your Knowledge Graph in Neo4j Browser

To visually inspect the extracted graph structures and entities processed by your `Ingestion-Pipeline`, follow this quick verification guide.

### Step 1: Access the Interface

Open your web browser and navigate to the Neo4j default web management panel console:

> **URL:** `http://localhost:7474`

### Step 2: Connection Settings Configuration

When the database portal splash screen prompts you, populate the login fields with your `.env` parameters:

* **Connection URL:** `bolt://localhost:7687`
* **Authentication Type:** `Username / Password`
* **Username:** `neo4j`
* **Password:** `********`

### Step 3: Useful Cypher Investigative Queries

Once inside the running terminal interface worksheet box at the top, run these queries to monitor your database nodes:

* **View the Entire Discovered Knowledge Graph Structure (Up to 300 items):**
```cypher
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 300;

```


* **Count Total Nodes Extracted By Entity Classes:**
```cypher
MATCH (n) RETURN n.label AS Type, count(n) AS Total Elements ORDER BY Total Elements DESC;

```


* **Clear the Whole Sandbox DB to Restart Ingestion Anew:**
```cypher
MATCH (n) DETACH DELETE n;

```
