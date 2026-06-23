# Architecture Blueprint: Cognitive GraphRAG System

## 1. Advanced Data Ingestion & Chunking Strategy

To handle large documents effectively, we avoid naive chunking (which cuts off sentences and strips background context). Instead, we use a **Hierarchical Parent-Child Splitting** model combined with **Semantic Layout Stitching**.

### The Mechanism

1. **Document-Level Processing:** Calculate an immutable SHA-256 hash of the PDF to prevent duplicate ingestion loops.
2. **Parent Chunking:** Split the raw document text into large semantic sections (e.g., $2000$ characters) matching physical layout markers like chapter or section sub-headers.
3. **Child Sub-Chunking:** Divide each parent block into smaller, highly dense child sub-chunks (e.g., $400$ characters, $100$ character overlap).
4. **Vector vs. Graph Indexing:**
* **Chroma DB:** Stores *only* the **Child Sub-Chunks** as high-dimensional vectors to optimize specific semantic similarity matching.
* **Neo4j Graph Database:** Stores the structural **Parent Chunks** as physical nodes alongside domain entities and reified interactions.
* **The Provenance Anchor:** Every child sub-chunk maintains an explicit pointer link directly upstream to its structural parent node in the graph.



---

## 2. Dual-Layer Cognitive Knowledge Graph Schema

Inside Neo4j, data is organized into a hybrid schema containing two independent layers that map real-world conceptual flow back to physical document positions.

```
[ Domain Knowledge Layer ]
  (:Component) ────[:DEPENDS_ON]────► (:Architecture)
        │                                   │
   [:SUBJECT]                          [:OBJECT]
        ▼                                   ▼
  (i:Interaction {id: "claim_102", description: "caveats"})
        │
   [:PROVENANCE_OF]
        ▼
[ Provenance & Structural Tracking Layer ]
  (:ParentChunk {id: "parent_5"}) ◄───[:CHILD_OF]─── (:ChildChunk {id: "chroma_id_9"})

```

### Layer A: Domain Knowledge & Reified Claims

* **Concept Nodes:** `(:Component)`, `(:Architecture)`, `(:Constraint)`, `(:Metric)`. Nodes hold deep internal property maps such as definitions, expected parameters, and known failure conditions.
* **Reified Claims (`:Interaction` Nodes):** Instead of simple lines, relationships themselves become independent entity nodes holding precise operational metrics and conditional assertions.

### Layer B: Provenance Tracking

* **Parent Chunk Nodes:** `(:ParentChunk {id: "hash-p_index", text: "..."})`
* **Child Tracking Tokens:** `(:ChildChunk {id: "hash-child-c_index"})`
* **Structural Pointers:** * `(:ChildChunk)-[:CHILD_OF]->(:ParentChunk)`
* `(:Concept)-[:MENTIONED_IN]->(:ParentChunk)`
* `(:Interaction)-[:PROVENANCE_OF]->(:ParentChunk)`



---

## 3. The Multi-Stage Retrieval & Expansion Funnel

When a user executes an inquiry, the retrieval tool doesn't just do a single database lookup. It runs an intelligent, interleaved **Gathering Loop**:

```
[ User Query ] ──► (Stage 1: Vector Proximity Sweep) ──► Target Child Chunk IDs
                                                                  │
                                                                  ▼
 (Stage 3: Parent Context Extraction) ◄── (Stage 2: Graph Flow Expansion)
            │
            ▼
 (Stage 4: Dynamic Context Gatekeeper Agent Evaluation)
            ├──► Context Complete ──► [ KnowledgeFusionAgent ]
            └──► Context Sparse   ──► [ web_search ] ──► Combined Data

```

* **Stage 1: Vector Proximity Sweep (`chroma_search`)**
The user query executes a similarity pass across Chroma to grab the top 3 nearest-neighbor **Child Sub-Chunks**.
* **Stage 2: Graph Flow Expansion (`neo4j_traverse`)**
The tool extracts the IDs of the retrieved child sub-chunks and moves to Neo4j. It climbs up the `[:CHILD_OF]` edge to find the structural parent nodes. It then expands outward by 1–2 hops across all connected `(:Concept)` and `(:Interaction)` claim paths to map out the functional flow of information.
* **Stage 3: Parent Context Extraction (`chroma_fetch`)**
The system pulls the full text block from the discovered `ParentChunk` nodes. This brings in background context, equations, and neighboring sentences that a regular vector search would miss.

---

## 4. The Context Gatekeeper Agent & Refactored Subgraph

To resolve instances where local databases contain gaps, we insert a specialized **Context Gatekeeper Agent** directly into the research workflow pipeline.

### Updated Graph Topology Nodes

```
("START") ──► [PlannerAgent] ──► [RetrievalAgent] ──► [ContextGatekeeperAgent]
                                                               │
                                         ┌─────────────────────┴─────────────────────┐
                                         ▼ (Sufficient)                              ▼ (Sparse Context)
                                [KnowledgeFusionAgent]                         [WebSearchTool]
                                         │                                           │
                                         └─────────────────────┬─────────────────────┘
                                                               ▼
                                                       [KnowledgeFusionAgent]
                                                               │
                                                       [ReasonerAgent]
                                                               │
                                                       [ResponseAgent]

```

### The Agent Execution Flow

1. **`PlannerAgent` (The Blueprint Architect):** Sets up explicit search boundaries optimized for our parent-child graph layout.
2. **`RetrievalAgent` (The Gatherer):** Runs the multi-stage database loop (`chroma_search` -> `neo4j_traverse` -> `chroma_fetch`), collecting the raw parent text blocks and semantic graph paths.
3. **`ContextGatekeeperAgent` (The Evaluator - *NEW*):** Inspects the raw data block gathered by the retrieval node against the user's initial question. It evaluates clarity and completeness.
* *Verdict -> SUFFICIENT:* Routes the context data directly to the fusion agent.
* *Verdict -> INSUFFICIENT:* Dynamically executes `web_search` to scrape missing real-time internet context, merges the web data with the database records, and forwards the complete package.


4. **`KnowledgeFusionAgent` (The De-duplicator):** Deduplicates, ranks, and structures the combined text block.
5. **`ReasonerAgent` (The Logic Core):** Executes step-by-step Chain-of-Thought deduction over the complete text payload to trace entity connections.
6. **`ResponseAgent` (The Final Writer):** Outputs the final answer in structured markdown with strict, inline bracketed source citations.

---

## 🛠️ Implementation Phasing

1. **`app/tools.py`:** Create the atomic tools to handle the parent-child chunk routing and the new context fallback parameters.
2. **`app/ingest_pipeline.py`:** Update your 6-stage ingestion agents to extract parent nodes, child nodes, and interaction attributes.
3. **`app/research_pipeline.py`:** Integrate the `ContextGatekeeperAgent` into the graph logic structure.
