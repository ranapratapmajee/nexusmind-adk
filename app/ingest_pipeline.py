# filepath: app/ingest_pipeline.py
import logging
import json
from typing import Dict, Any, List

import uuid
from google.genai import types

from google.adk import Agent, Workflow
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm
from config.settings import settings

# Import our fine-grained tools and programmatic extractor hooks
from app.tools import chroma_write, neo4j_merge_node, neo4j_merge_claim
from app.infrastructure import pdf_extractor

logger = logging.getLogger(__name__)

# 🚀 CHOOSE THE EXPEDITED INGESTION BRAIN:
# Switch to GEMINI_MODEL for flawless structural graphs, or OLLAMA_MODEL for local execution
ingestion_llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. SPECIALIZED KNOWLEDGE GRAPH MINING NODES
# =========================================================

entity_extractor_agent = Agent(
    name="EntityExtractorAgent",
    model=ingestion_llm,
    description="Extracts detailed entities and micro-context property maps.",
    instruction="""
    TASK: Mine domain concepts, systems, and constraints from the provided text segments.
    For each entity, capture: 'name', 'type' (Component, Architecture, Constraint, Metric), and a short 'properties' map detailing definitions or known failure conditions.
    
    Output strictly as a valid JSON object matching: {"entities": [{"name": "X", "type": "Y", "properties": {"description": "Z"}}]}
    """,
    mode="single_turn"
)

relation_extractor_agent = Agent(
    name="RelationExtractorAgent",
    model=ingestion_llm,
    description="Extracts reified relationship metrics and conditional claims.",
    instruction="""
    TASK: Map connections between the extracted entities found within the context. Find explicit system interactions (e.g., DEPENDS_ON, FEEDS_DATA_TO, HAS_CONSTRAINT).
    For each link, generate: 'source', 'target', 'type' and an intermediate 'claim_id' slug with properties explaining the exact interaction conditions or caveats.
    
    Output strictly as a valid JSON object matching: {"edges": [{"source": "A", "target": "B", "type": "DEPENDS_ON", "claim_id": "slug", "properties": {"status": "Active"}}]}
    """,
    mode="single_turn"
)

kg_validator_agent = Agent(
    name="KgValidatorAgent",
    model=ingestion_llm,
    instruction="""
    TASK: Combine and validate the extracted entities and edges maps. Match edge parameters to verified node IDs, clear dangling elements, and produce a unified, clean JSON object containing both arrays.
    """,
    mode="single_turn"
)

indexer_agent = Agent(
    name="IndexerAgent",
    model=ingestion_llm,
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
# 2. WORKFLOW ENGINE TOPOLOGY (OPTIMIZED STRUCTURAL MAP)
# =========================================================

ingest_workflow_pipeline = Workflow(
    name="IngestionPipeline",
    edges=[
        (
            "START", 
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
        print(f"\n🚀 [ENGINE INITIALIZATION] Commencing layout parsing graph layer for target asset: '{filename}'")
        
        try:
            # ⚡ STEP 1: Process text window slicing programmatically on CPU (Instant, no LLM cost)
            hierarchical_chunks = pdf_extractor.slice_hierarchical_chunks(file_content_stream)
            
            pipeline_runner = InMemoryRunner(agent=ingest_workflow_pipeline, app_name="app")
            if hasattr(pipeline_runner, "auto_create_session"):
                pipeline_runner.auto_create_session = True
                
            report_accumulator = []
            
            # ⚡ STEP 2: Loop securely over each isolated slice package
            for block in hierarchical_chunks:
                parent_idx = block["parent_index"]
                parent_text = block["parent_chunk"]
                child_fragments = block["child_chunks"]
                
                print(f"\n📦 [PROCESSING WINDOW] Analyzing Parent Segment Block [{parent_idx}/{len(hierarchical_chunks)}]")
                
                # Format an isolated atomic prompt payload package for the runtime pipeline
                payload_package = {
                    "document_metadata": {
                        "filename": filename,
                        "parent_index": parent_idx
                    },
                    "parent_context_stream": parent_text,
                    "child_fragments_to_index": child_fragments
                }
                
                isolated_session = f"ingest_block_{parent_idx}_{uuid.uuid4().hex[:4]}"
                
                # Trigger pipeline stream run on the single package frame context
                outcome_stream = pipeline_runner.run_async(
                    user_id="ingest_cli_service",
                    session_id=isolated_session,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=json.dumps(payload_package))]
                    )
                )

                text_accumulator = ""
                async for event in outcome_stream:
                    if hasattr(event, "author") and event.author:
                        # Log active nodes processing this block frame context
                        logger.debug(f"⏳ [Node Run] Active Node: {event.author}")
                    
                    if hasattr(event, "text") and event.text:
                        text_accumulator += event.text
                    elif hasattr(event, "content") and event.content:
                        c = event.content
                        if hasattr(c, "parts"):
                            for part in c.parts:
                                if hasattr(part, "text") and part.text:
                                    text_accumulator += part.text
                                    
                report_accumulator.append(text_accumulator.strip())

            print("\n🏁 [ENGINE COMPLETION] All parent/child workflow blocks synthesized safely.")
            unified_report = "\n\n".join(report_accumulator)
            return {
                "status": "SUCCESS",
                "markdown_answer": f"### 📁 Processing Report: PDF Ingestion Success\n\n{unified_report}"
            }
            
        except Exception as e:
            print(f"\n❌ [CRITICAL PIPELINE FAILURE] Thread collapsed: {str(e)}")
            logger.error(f"❌ Ingestion crashed: {str(e)}")
            return {
                "status": "CRASHED",
                "markdown_answer": f"❌ **Ingestion failure tracker dump:** {str(e)}"
            }

ingest_flow_engine = NexusIngestionFlowEngine()