# filepath: app/ingest_pipeline.py
import logging
import json
from typing import Dict, Any

from google.adk import Agent, Workflow
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm
from config.settings import settings

# Import our fine-grained atomic ingestion tools
from app.tools import chroma_write, neo4j_merge_node, neo4j_merge_claim

logger = logging.getLogger(__name__)
llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. SPECIALIZED INGESTION AGENT NODES
# =========================================================

parser_agent = Agent(
    name="PDFLayoutParserAgent",
    model=llm,
    description="Extracts unstructured text streams from raw binary files.",
    instruction="Extract clean text from the data stream. Output only the pure text body, removing headers, footers, or formatting noise.",
    mode="single_turn"
)

chunker_agent = Agent(
    name="SlidingWindowChunkerAgent",
    model=llm,
    description="Slices raw inputs into Parent and Child sub-chunk layout boundaries.",
    instruction="""
    ROLE: Hierarchical Document Splitter.
    TASK: Slice the incoming raw text into large Parent chunks (approx 2000 characters) following layout section boundaries.
    For each Parent chunk, split it into smaller overlapping Child sub-chunks (approx 400 characters, 100 character overlap).
    
    Output a structured JSON list grouping each child text slice under its parent context.
    """,
    mode="single_turn"
)

entity_extractor_agent = Agent(
    name="EntityExtractorAgent",
    model=llm,
    description="Extracts detailed entities and micro-context property maps.",
    instruction="""
    TASK: Mine domain concepts, systems, and constraints from the text fragments.
    For each entity, capture: 'name', 'type' (Component, Architecture, Constraint, Metric), and a short 'properties' map detailing definitions or known failure conditions.
    
    Output strictly as a valid JSON object matching: {"entities": [{"name": "X", "type": "Y", "properties": {"description": "Z"}}]}
    """,
    mode="single_turn"
)

relation_extractor_agent = Agent(
    name="RelationExtractorAgent",
    model=llm,
    description="Extracts reified relationship metrics and conditional claims.",
    instruction="""
    TASK: Map connections between the extracted entities. Find explicit system interactions (e.g., DEPENDS_ON, FEEDS_DATA_TO, HAS_CONSTRAINT).
    For each link, generate: 'source', 'target', 'type' and an intermediate 'claim_id' slug with properties explaining the exact interaction conditions or caveats.
    
    Output strictly as a valid JSON object matching: {"edges": [{"source": "A", "target": "B", "type": "DEPENDS_ON", "claim_id": "slug", "properties": {"status": "Active"}}]}
    """,
    mode="single_turn"
)

kg_validator_agent = Agent(
    name="KgValidatorAgent",
    model=llm,
    instruction="""
    TASK: Combine and validate the extracted entities and edges maps. Match edge parameters to verified node IDs, clear dangling elements, and produce a unified, clean JSON object containing both arrays.
    """,
    mode="single_turn"
)

indexer_agent = Agent(
    name="IndexerAgent",
    model=llm,
    description="Asynchronous ingestion worker allocating records concurrently to storage clusters.",
    instruction="""
    ROLE: Data Sync Coordinator.
    TASK: Look at the validated JSON data maps and write them to storage by calling the active tool definitions.
    
    EXECUTION SEQUENCE:
    1. Call `chroma_write` for each raw text fragment to securely store vectors and get a unique child chunk ID pointer.
    2. Pass that chunk ID pointer along with the 'entities' list into `neo4j_merge_node` to write concept definitions.
    3. Call `neo4j_merge_claim` using the 'edges' data to link reified relationship nodes to the matching chunk ID.
    
    Output a short markdown summary confirming successful writes. Do not ask any follow-up questions.
    """,
    tools=[
        chroma_write,
        neo4j_merge_node,
        neo4j_merge_claim
    ],
    mode="single_turn"
)

# =========================================================
# 2. WORKFLOW ENGINE TOPOLOGY
# =========================================================

ingest_workflow_pipeline = Workflow(
    name="IngestionPipeline",
    edges=[
        (
            "START", 
            parser_agent, 
            chunker_agent, 
            entity_extractor_agent, 
            relation_extractor_agent, 
            kg_validator_agent, 
            indexer_agent
        )
    ]
)

class NexusIngestionFlowEngine:
    @staticmethod
    async def ingest_pdf_document(file_content_stream: str, filename: str) -> Dict[str, Any]:
        logger.info(f"📁 [PDF Pipeline] Running ingestion graph for file: '{filename}'")
        inbound_context = f"Target PDF Filename: {filename}\nRaw Document Stream Source:\n{file_content_stream}"
        try:
            pipeline_runner = InMemoryRunner(agent=ingest_workflow_pipeline)
            pipeline_outcome = await pipeline_runner.run(input_text=inbound_context)
            return {
                "status": "SUCCESS",
                "markdown_answer": f"### 📁 Processing Report: PDF Ingestion Success\n\n{pipeline_outcome.text}"
            }
        except Exception as e:
            logger.error(f"❌ Ingestion crashed: {str(e)}")
            return {
                "status": "CRASHED",
                "markdown_answer": f"❌ **Ingestion failure tracker dump:** {str(e)}"
            }

ingest_flow_engine = NexusIngestionFlowEngine()