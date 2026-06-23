# 🏛️ Production Architecture Specification: NexusMind GraphRAG
**Version:** 2.5 (Core Production Baseline)  
**Execution Environment:** Hybrid Local Edge Core (`nomic-embed-text` + Local 7B LLM Engine)  
**Framework Topology:** Google ADK 2.3 Async Event-Driven Execution Engine

---

## 1. Architectural Design Theory & Strategic Advantage

Standard GraphRAG pipelines struggle with **Unstructured Context Overload** when deployed on local hardware. Forcing a local Large Language Model (LLM) to parse massive text blocks, compute token coordinates, split text, and output valid JSON maps simultaneously causes severe processing overhead, leading to **Hard Read Timeouts (`httpx.ReadTimeout`)**.

NexusMind solves this issue using a **Decoupled Asymmetric Execution** pattern:
1. **Structural Text Splitting** is offloaded from the AI layer to native Python string slicing loops running on the **CPU**, where it executes instantly.
2. The **Local Model** is used exclusively for domain entity mining, schema-constrained parsing, and multi-hop reasoning over tiny, pre-cut text blocks.


```

```
                  ┌──────────────────────────────────────────┐
                  │          Source Document (PDF)           │
                  └────────────────────┬─────────────────────┘
                                       │  [PyPDF Byte Read]
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │       Programmatic Python Extractor      │
                  │   (Natively handles text extraction)     │
                  └────────────────────┬─────────────────────┘
                                       │  [Pure Text Stream String]
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │       Programmatic CPU Chunker           │
                  │  (Deterministic Window Partitioning)     │
                  └────────────┬───────────────────────┬─────┘
                               │                       │
                               ▼ [Parent Windows]      ▼ [Child Windows]
                  ┌────────────────────────┐  ┌────────────────────────┐
                  │  Parent Chunks (~2000c)│  │   Child Chunks (~400c) │
                  │  [Passed to Graph LLM] │  │  [Passed to Embedder]  │
                  └────────────┬───────────┘  └────────────┬───────────┘
                               │                           │
                               ▼ [Iterative Payload]       ▼ [Matrix Generation]
                  ┌────────────────────────┐  ┌────────────────────────┐
                  │   Google ADK Pipeline  │  │   Ollama Local Nodes   │
                  │  (Entity/Edge Mining)  │  │  (nomic-embed-text)    │
                  └────────────┬───────────┘  └────────────┬───────────┘
                               │                           │
                               ▼ [Cypher MERGE Txs]        ▼ [HTTP Payload Add]
                  ┌────────────────────────┐  ┌────────────────────────┐
                  │   Neo4j Graph Cluster  │  │  ChromaDB Vector Pool  │
                  │  (Reified Claims/Nodes)│  │  (768-Dim Coordinates) │
                  └────────────────────────┘  └────────────────────────┘

```

```

---

## 2. Ingestion Domain Specification (Data Ingestion Pipeline)

The data ingestion engine transforms unstructured document strings into synchronized database representations with clear provenance trails.

### 2.1 Native Programmatic Layout Chunking (CPU-Bound Heuristics)
Instead of relying on prompt-driven AI splitting, `PDFExtractor.slice_hierarchical_chunks()` applies strict programmatic text windowing:
* **Parent Context Windows:** The raw document string is parsed sequentially into large, non-overlapping **Parent context chunks** capped at **2,000 characters**.
* **Child Overlap Sub-Slicing:** Each parent chunk is subdivided into smaller **Child sub-chunks** capped at **400 characters**, enforcing a **100-character overlap** with adjacent fragments to preserve semantic edge boundaries.

### 2.2 Vector Alignment Mechanics
* **Target Model Allocation:** Local vectorizations are generated exclusively by the local **`nomic-embed-text`** model running via Ollama's `/api/embeddings` endpoint.
* **Spatial Geometry Array:** Text contents are converted into mathematical coordinates with a structural dimensionality of **768 parameters**, then committed to a persistent local **ChromaDB Collection** using an `HttpClient` transport layer.

### 2.3 Dual-Layer Knowledge Graph Topology (Neo4j Schema Design)
Inside Neo4j, data is organized into a hybrid schema containing two independent layers that map real-world conceptual flows back to physical document positions.


```

[ Layer A: Domain Knowledge Layer ]
(:Component) ────[:DEPENDS_ON]────► (:Architecture)
│                                   │
[:SUBJECT]                          [:OBJECT]
▼                                   ▼
(i:Interaction {id: "claim_slug", interaction_type: "DEPENDS_ON"})
│
[:PROVENANCE_OF]
▼
[ Layer B: Provenance & Structural Tracking Layer ]
(:Entity {id: "parent_chunk_id"}) ◄───[:MENTIONED_IN]─── (:Entity {id: "chroma_id", label: "ChildChunk"})

```

#### Layer A: Domain Knowledge & Reified Claims
* **Concept Nodes:** `(:Component)`, `(:Architecture)`, `(:Constraint)`, `(:Metric)`. Nodes contain definitions, parameters, and known failure conditions.
* **Reified Claims (`:Interaction` Nodes):** Relationships are treated as distinct structural nodes holding precise operational metadata and conditional properties rather than empty lines.

#### Layer B: Provenance Tracking
* **Child Tracking Tokens:** Marked explicitly as `(c:Entity {id: $chunk_id, label: 'ChildChunk'})`.
* **Grounded Provenance Cypher Queries:**
  ```cypher
  // Merging a Concept Node & Binding Provenance Anchor
  MERGE (c:Entity {id: $chunk_id}) SET c.label = 'ChildChunk'
  WITH c MATCH (e {id: $name}) MERGE (e)-[:MENTIONED_IN]->(c)

```

```cypher
// Merging a Reified Interaction Claim & Building Structural Links
MATCH (s {id: $source}) MATCH (t {id: $target}) MATCH (i {id: $claim_id})
MERGE (c:Entity {id: $chunk_id}) SET c.label = 'ChildChunk'
MERGE (s)-[:SUBJECT]->(i) MERGE (i)-[:OBJECT]->(t) MERGE (i)-[:PROVENANCE_OF]->(c)

```

---

## 3. Ingestion Multi-Agent Orchestration Blueprint

The ingestion process runs through an automated pipeline managed by the Google ADK runner. Rather than sending the entire document into the pipeline as a single block, the engine loops through each pre-cut parent context window one frame at a time.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      NexusIngestionFlowEngine                          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                [Iterates over each Parent/Child chunk block]
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Payload Package JSON                           │
│  { "parent_context_stream": "...", "child_fragments_to_index": [...] } │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
                       =========================
                       Google ADK Pipeline Steps
                       =========================
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        EntityExtractorAgent                            │
│           Outputs: {"entities": [{"name": "X", "type": "Y"}]}          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       RelationExtractorAgent                           │
│           Outputs: {"edges": [{"source": "A", "target": "B"}]}          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          KgValidatorAgent                              │
│       Cross-references arrays, resolves syntax, builds schema          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                            IndexerAgent                                │
│          Executes tools: chroma_write, neo4j_merge_node/claim          │
└────────────────────────────────────────────────────────────────────────┘

```

---

## 4. Runtime Cognitive Routing & Retrieval Specification

The runtime user interface is powered by the **`SystemRootGateway` Orchestration Subgraph**, which dynamically routes incoming queries through an intelligent retrieval funnel.

```
                              ┌──────────────────┐
                              │  User Query (In) │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │    RootAgent     │
                              │(Context Rewriter)│
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │   RouterAgent    │
                              │(Intent Classifier│
                              └────────┬─────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
             [ CASUAL_CHAT ]                         [ RESEARCH ]
                    │                                     │
                    ▼                                     ▼
      ┌───────────────────────────┐         ┌───────────────────────────┐
      │  FastConversationalAgent  │         │   DeepResearchPipeline    │
      │  (Low-Latency Speed Run)  │         │  (Multi-Stage Retrieval)  │
      └───────────────────────────┘         └─────────────┬─────────────┘
                                                          │
                    ┌─────────────────────────────────────┴─────────────────────────────────────┐
                    ▼                                     ▼                                     ▼
         ┌─────────────────────┐               ┌─────────────────────┐               ┌─────────────────────┐
         │     Stage 1:        │               │     Stage 2:        │               │     Stage 3:        │
         │   Chroma Search     │ ────────────> │   Neo4j Traverse    │ ────────────> │    Chroma Fetch     │
         │  (Vector similarity)│               │  (Multi-hop pathing)│               │ (Target text pull)  │
         └─────────────────────┘               └─────────────────────┘               └─────────────────────┘
                                                                                                │
                                                                                                ▼
                                                                                     ┌─────────────────────┐
                                                                                     │    Final Answer     │
                                                                                     │  Generation Output  │
                                                                                     └─────────────────────┘

```

### 4.1 System Gateway Core

* **`RootAgent` (Context Rewriter):** Reviews multi-turn chat histories and condenses inputs into clear standalone questions, caching the result to `invocation_context.state["resolved_query"]`.
* **`ControlEngineRouter` (Intent Classifier):** Categorizes queries into `CASUAL_CHAT` (processed by `FastConversationalAgent`) or `RESEARCH` (forwarded to the `DeepResearchPipeline`).

### 4.2 Multi-Stage Hybrid Retrieval Funnel Heuristics

When a query moves into the **`DeepResearchPipeline`**, the system executes a coordinated search across both databases:

* **Stage 1: Vector Proximity Sweep (`chroma_search`):** Runs a semantic lookup across your text embedding index to grab the top 3 high-probability Child chunk IDs.
* **Stage 2: Graph Flow Expansion (`neo4j_traverse`):** Traces retrieved Child IDs up to their Parent nodes, expanding outward by 1–2 hops to map out connected components, attributes, and reified interactions (`origin_element`, `relationship_path`, `connected_target`).
* **Stage 3: Parent Context Extraction (`chroma_fetch`):** Pulls the full text blocks from the discovered `ParentChunk` nodes to reconstruct comprehensive background details.
* **Stage 4: Context Gatekeeper Agent Evaluation (`gatekeeper_agent`):** Evaluates if the gathered context contains enough detailed facts to comprehensively answer the user's query:
* *Verdict -> SUFFICIENT:* Routes data directly to the `KnowledgeFusionAgent`.
* *Verdict -> INSUFFICIENT:* Dynamically executes `web_search` to scrape missing context, merges it with the database records, and forwards the complete package.


* **Stage 5 & 6 (Fusion & Reasoner):** Deduplicates context streams, builds step-by-step logic trails, and passes the package to `ResponseAgent` to write a final answer with strict inline source citations.

---

## 5. System Configuration & Maintenance Standard

### 5.1 System Portals File Config (`.env`)

```bash
EXECUTION_MODE="LOCAL"
LOCAL_LLM_URL="http://localhost:11434"
OLLAMA_MODEL="qwen2.5-coder:7b"
EMBEDDING_MODEL="nomic-embed-text"

CHROMA_HOST="localhost"
CHROMA_PORT=8000

NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your_secure_password"

```

### 5.2 Database Maintenance Commands

To clear old entries and safely reset your database dimensions, run these cleanup tasks before starting a new file ingestion loop:

#### Reset Neo4j Database State:

```cypher
MATCH (n) DETACH DELETE n;

```

#### Clear ChromaDB Collection Cache (via Python CLI):

```python
from app.infrastructure import chroma_service
collection = chroma_service.get_or_create_collection()
collection.delete()

```

```
---
