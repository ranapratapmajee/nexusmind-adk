# filepath: app/ingest_pipeline.py
import logging
from typing import Dict, Any

# --- NATIVE ADK 2.0.0 ACCORDANT GRAPH PRIMITIVES ---
from google.adk import Agent, Workflow
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm
from config.settings import settings
from app.states import PDF_PARSER_PROMPT, CHUNKER_PROMPT
from app.tools import chroma_write_tool, neo4j_merge_tool # For ingestion

logger = logging.getLogger(__name__)

# Initialize both runner configurations
local_llm = LiteLlm(model=settings.OLLAMA_MODEL)
cloud_llm = LiteLlm(model=settings.GEMINI_MODEL)

# Dynamic allocation switch matrix
if settings.EXECUTION_MODE.upper() == "CLOUD":
    logger.info("☁️ System Engine utilizing CLOUD topology matrix (Gemini)")
    llm = cloud_llm
else:
    logger.info("💻 System Engine utilizing LOCAL topology matrix (Ollama)")
    llm = local_llm

# =========================================================
# 1. SPECIALIZED INGESTION AGENT NODES
# =========================================================

parser_agent = Agent(
    name="PDFLayoutParserAgent",
    model=llm,
    description="Extracts clean structural text from a PDF file stream dump.",
    instruction=PDF_PARSER_PROMPT,
    mode="single_turn"
)

chunker_agent = Agent(
    name="SlidingWindowChunkerAgent",
    model=llm,
    description="Processes raw text into sliding window fragments.",
    instruction=CHUNKER_PROMPT + "\nRead and process the text passed as input from the preceding node.",
    mode="single_turn"
)

entity_extractor_agent = Agent(
    name="EntityExtractorAgent",
    model=llm,
    description="Mines explicit entities and node categories from chunk arrays.",
    instruction="""Analyze the chunked fragments passed as input. Identify key operational entities 
    (e.g., Systems, Technologies, People, Projects). Return them as a clean JSON-formatted list of nodes.""",
    mode="single_turn"
)

relation_extractor_agent = Agent(
    name="RelationExtractorAgent",
    model=llm,
    description="Identifies semantic directional connections between discovered nodes.",
    instruction="""Analyze the extracted nodes passed as input. Identify and map clear directional 
    relationships between these entities. Format connection edges using SCREAMING_SNAKE_CASE.""",
    mode="single_turn"
)

kg_validator_agent = Agent(
    name="KgValidatorAgent",
    model=llm,
    description="Enforces strict schema compliance checks across node lists and edge maps.",
    instruction="""
    Validate the graph data passed as input. Ensure every single structural edge connects 
    a valid source and target ID present in the entities array. Drop any dangling or unmapped linkages.
    
    CRITICAL MANDATE: You must perform this sanitation entirely inline within your own context memory. 
    Do NOT attempt to generate, call, or invoke any tools, functions, or external code blocks (such as 'validate_graph'). 
    Output your final validated node and edge structure directly as a standard text/JSON data block payload.
    """,
    mode="single_turn"
)

indexer_agent = Agent(
    name="IndexerAgent",
    model=llm,
    description="Database commit broker deploying text fragments to Chroma and graph entities to Neo4j.",
    instruction="""
    You are the final database indexing node. You receive a structured JSON object containing verified 'entities' and 'edges' arrays from the preceding validator.
    
    CRITICAL INSTRUCTION: You MUST call 'neo4j_merge_tool' passing the 'entities' list as the 'nodes' argument, and the 'edges' list as the 'edges' argument. 
    Do not skip this step. Do not write a conversational response until your tool calls have been generated and executed.
    """,
    tools=[chroma_write_tool, neo4j_merge_tool],
    mode="single_turn"
)

# =========================================================
# 2. DECLARATIVE WORKFLOW GRAPH MATRIX
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
