# filepath: app/ingest_pipeline.py
import logging
from typing import Dict, Any

# --- NATIVE ADK 2.0.0 ACCORDANT GRAPH PRIMITIVES ---
from google.adk import Agent, Workflow
from google.adk.runners import InMemoryRunner
from config.settings import settings
from app.states import PDF_PARSER_PROMPT, CHUNKER_PROMPT
from app.tools import chroma_write_tool, neo4j_merge_tool # For ingestion

logger = logging.getLogger(__name__)

# =========================================================
# 1. SPECIALIZED INGESTION AGENT NODES
# =========================================================

parser_agent = Agent(
    name="PDFLayoutParserAgent",
    model=settings.OLLAMA_MODEL,
    description="Extracts clean structural text from a PDF file stream dump.",
    instruction=PDF_PARSER_PROMPT,
    output_schema=str,
    mode="single_turn"
)

chunker_agent = Agent(
    name="SlidingWindowChunkerAgent",
    model=settings.OLLAMA_MODEL,
    description="Processes raw text into sliding window fragments.",
    instruction=CHUNKER_PROMPT + "\nRead and process the text passed as input from the preceding node.",
    output_schema=str,
    mode="single_turn"
)

entity_extractor_agent = Agent(
    name="EntityExtractorAgent",
    model=settings.OLLAMA_MODEL,
    description="Mines explicit entities and node categories from chunk arrays.",
    instruction="""Analyze the chunked fragments passed as input. Identify key operational entities 
    (e.g., Systems, Technologies, People, Projects). Return them as a clean JSON-formatted list of nodes.""",
    output_schema=str,
    mode="single_turn"
)

relation_extractor_agent = Agent(
    name="RelationExtractorAgent",
    model=settings.OLLAMA_MODEL,
    description="Identifies semantic directional connections between discovered nodes.",
    instruction="""Analyze the extracted nodes passed as input. Identify and map clear directional 
    relationships between these entities. Format connection edges using SCREAMING_SNAKE_CASE.""",
    output_schema=str,
    mode="single_turn"
)

kg_validator_agent = Agent(
    name="KgValidatorAgent",
    model=settings.OLLAMA_MODEL,
    description="Enforces strict schema compliance checks across node lists and edge maps.",
    instruction="""Validate the graph data passed as input. Ensure every single structural edge connects 
    a valid source and target ID present in the entities array. Drop any dangling or unmapped linkages.""",
    output_schema=str,
    mode="single_turn"
)

indexer_agent = Agent(
    name="IndexerAgent",
    model=settings.OLLAMA_MODEL,
    description="Database commit broker deploying text fragments to Chroma and graph entities to Neo4j.",
    instruction="""Commit the raw text chunks into Chroma DB using chroma_write_tool. 
    Then, write the verified graph structure into Neo4j using neo4j_merge_tool.
    Output a clear narrative summary detailing the number of vectors and graph nodes successfully committed.""",
    tools=[chroma_write_tool, neo4j_merge_tool],
    output_schema=str,
    mode="single_turn"
)

# =========================================================
# 2. DECLARATIVE WORKFLOW GRAPH MATRIX
# =========================================================
ingest_workflow_pipeline = Workflow(
    name="Ingestion-Pipeline",
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

# =========================================================
# 3. BACKGROUND OPERATIONAL EXECUTION ENGINE
# =========================================================
class NexusIngestionFlowEngine:
    """Operational manager running file indexing tasks using native ADK 2.0.0 Workflows."""

    @staticmethod
    async def ingest_pdf_document(file_content_stream: str, filename: str) -> Dict[str, Any]:
        logger.info(f"📁 [PDF Pipeline] Launching 6-stage ingestion for target file: '{filename}'")
        
        inbound_context = f"Target PDF Filename: {filename}\nRaw Document Stream Source:\n{file_content_stream}"
        
        try:
            pipeline_runner = InMemoryRunner(agent=ingest_workflow_pipeline)
            pipeline_outcome = await pipeline_runner.run(input_text=inbound_context)
            logger.info(f"✅ [PDF Pipeline] Indexing complete for: '{filename}'")
            
            return {
                "status": "SUCCESS",
                "markdown_answer": f"### 📁 Processing Report: PDF Ingestion Success\n\n{pipeline_outcome.text}",
                "dynamic_followups": ["Check database structural logs", "Query the uploaded content metrics"]
            }
            
        except Exception as e:
            logger.error(f"❌ [PDF Pipeline] Execution crashed: {str(e)}")
            return {
                "status": "CRASHED",
                "markdown_answer": f"❌ **Framework operational error tracker dump:** {str(e)}",
                "dynamic_followups": []
            }

ingest_flow_engine = NexusIngestionFlowEngine()
