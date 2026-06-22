# filepath: app/states.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# =========================================================
# SYSTEM STATIC TEXT PROMPTS
# =========================================================

PDF_PARSER_PROMPT = """
You are an expert document extraction layout specialist.
Clean the incoming raw text stream. Eliminate formatting artifacts, trailing footer elements, and running page numbers.
Provide a clean text body.
"""

CHUNKER_PROMPT = """
You are a high-performance text segmentation engine.
Analyze the cleaned text provided in the session state. Break the raw stream into logical, uniform paragraphs or sliding context windows of approximately 500 characters, maintaining an intentional 100-character overlap.
Ensure sentence structures and technical arguments remain unbroken.
"""

KNOWLEDGE_FUSION_PROMPT = """
You are a data curation engineer. Analyze the raw multi-source data snippets retrieved by the upstream nodes.
Apply Reciprocal Rank Fusion principles (1 / (60 + rank)) to deduplicate matching entity references.
Compile these fragments into a single, high-density unified reference context block.
"""

RESEARCH_SYNTHESIS_PROMPT = """
You are Nexa, a senior GraphRAG analytical research engine.
Review the reasoning path and the fused context block available in the session state.
1. Draft an enterprise-grade report formatted in clean markdown, tracking references with bracketed citations.
2. Proactively generate exactly 3 highly contextual, interactive follow-up questions to help the user explore the data further.
"""

# =========================================================
# COGNITIVE ORCHESTRATION SHIELD SCHEMAS
# =========================================================

class GuardrailResponse(BaseModel):
    status: str = Field(description="Must be exactly 'PASSED' or 'BLOCKED'")
    reason: str = Field(description="Detailed compliance analytics or safety metadata logs.")

class RouterResponse(BaseModel):
    intent: str = Field(description="Must be exactly: 'CASUAL_CHAT', 'INGESTION_UPLOAD', or 'RESEARCH'")
    complexity: str = Field(description="Compute tier mapping: 'STANDARD' or 'EXTREME'")

# =========================================================
# DEEP RESEARCH SUB-GRAPH DATA STRUCTURES
# =========================================================

class ResearchPlan(BaseModel):
    vector_queries: List[str] = Field(description="Semantic phrases targeting regional text matches in Chroma.")
    graph_queries: List[str] = Field(description="Cypher or key-property extraction conditions targeting Neo4j topology.")

class FusedContext(BaseModel):
    fused_context_block: str = Field(description="Mathematically ranked, unified contextual reference baseline.")
    telemetry_rankings: Dict[str, Any] = Field(description="RRF scoring trace logs for debugging database overlaps.")

class CoTSynthesis(BaseModel):
    chain_of_thought_steps: List[str] = Field(description="Explicit multi-hop reasoning deductions made step-by-step.")
    raw_synthesis: str = Field(description="Unformatted dense context extraction compilation.")

class SynthesisResponse(BaseModel):
    markdown_answer: str = Field(description="Deep analytical response compiled in clean, human-readable markdown.")
    dynamic_followups: List[str] = Field(description="Exactly 3 diverse, context-aware interactive follow-up cross-questions.")

# =========================================================
# CONCURRENT DOCUMENT INGESTION WORKFLOW SCHEMAS
# =========================================================

class ParserOutput(BaseModel):
    raw_text: str = Field(description="Extracted clean text content from the PDF source document.")
    metadata: Dict[str, Any] = Field(description="Document metadata including page boundaries and file properties.")

class ChunkedOutput(BaseModel):
    chunks: List[str] = Field(description="Text fragments broken into strict sliding token/character windows.")
    source_file: str = Field(description="Name of the source PDF document.")

class ExtractedEntities(BaseModel):
    class EntityNode(BaseModel):
        id: str = Field(description="Unique, normalized name token of the entity.")
        label: str = Field(description="Entity group class (e.g., TECHNOLOGY, PERSON, SYSTEM).")
        properties: Dict[str, Any] = Field(default_factory=dict, description="Extracted key-value attributes.")
        
    entities: List[EntityNode] = Field(description="Array of isolated semantic entity nodes extracted from chunks.")

class ExtractedGraphTriplets(BaseModel):
    class Edge(BaseModel):
        source: str = Field(description="ID of the source origin node element.")
        target: str = Field(description="ID of the destination node element.")
        type: str = Field(description="Relationship label predicate in SCREAMING_SNAKE_CASE (e.g., DEPENDS_ON).")
        
    nodes: List[ExtractedEntities.EntityNode] = Field(description="Forwarded collection of unique nodes.")
    edges: List[Edge] = Field(description="Array of relative entity graph edges.")

class IngestionSummary(BaseModel):
    status: str = Field(description="Final operational outcome: 'SUCCESSFUL' or 'MALFORMED'")
    vector_chunks_indexed: int = Field(description="Total split data chunk fragments pushed to Chroma.")
    graph_entities_merged: int = Field(description="Total elements and paths committed to Neo4j.")
    narrative_audit_trail: str = Field(description="Detailed summary explaining what entities and connections were cataloged.")
    