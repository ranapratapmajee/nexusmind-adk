# filepath: app/agents/ingest_nodes.py
from google.adk.agents import LlmAgent
from config.settings import settings
from app.models.ingest_state import ParserOutput, ChunkedOutput, ExtractedEntities, ExtractedGraphTriplets, IngestionSummary
from app.tools.indexer_tools import chroma_write_tool, neo4j_merge_tool

# --- NODE 1: PARSER AGENT ---
parser_agent = LlmAgent(
    name="PDFLayoutParserAgent",
    model=settings.OLLAMA_MODEL,
    description="Extracts raw structural text and layout metrics from a PDF file stream dump.",
    instruction="Clean the text stream from the source file. Remove page numbers and headers. Export clean raw text.",
    output_schema=ParserOutput
)

# --- NODE 2: CHUNKER AGENT ---
chunker_agent = LlmAgent(
    name="SlidingWindowChunkerAgent",
    model=settings.OLLAMA_MODEL,
    description="Processes raw text into uniform sliding windows to optimize text embedding indexing.",
    instruction="""Break the text into chunks of roughly 500 characters, using a 100-character sliding overlap. 
    Ensure sentence boundaries are preserved.""",
    output_schema=ChunkedOutput
)

# --- NODE 3: ENTITY EXTRACTOR AGENT ---
entity_extractor_agent = LlmAgent(
    name="EntityExtractorAgent",
    model=settings.OLLAMA_MODEL,
    description="Mines explicit entities and node categories from chunk arrays.",
    instruction="Identify key operational entities (e.g., Systems, Technologies, People, Projects) from the chunks.",
    output_schema=ExtractedEntities
)

# --- NODE 4: RELATION EXTRACTOR AGENT ---
relation_extractor_agent = LlmAgent(
    name="RelationExtractorAgent",
    model=settings.OLLAMA_MODEL,
    description="Identifies semantic directional connections between discovered nodes.",
    instruction="Map clear relationships between the entities. Format connection edges in SCREAMING_SNAKE_CASE.",
    output_schema=ExtractedGraphTriplets
)

# --- NODE 5: KG VALIDATOR AGENT ---
kg_validator_agent = LlmAgent(
    name="KgValidatorAgent",
    model=settings.OLLAMA_MODEL,
    description="Enforces strict schema compliance checks and repairs malformed JSON syntax blocks.",
    instruction="""Validate the nodes and edges against our standard domain model.
    Ensure every edge has a valid source and target ID present in the nodes array. Drop broken linkages.""",
    output_schema=ExtractedGraphTriplets
)

# --- NODE 6: INDEXER AGENT (TOOL EXECUTOR) ---
indexer_agent = LlmAgent(
    name="IndexerAgent",
    model=settings.OLLAMA_MODEL,
    description="Database commit broker deploying text fragments to Chroma and graph entities to Neo4j.",
    instruction="""Commit the text chunks to Chroma via chroma_write_tool and the validated graph topology to Neo4j via neo4j_merge_tool.""",
    tools=[chroma_write_tool, neo4j_merge_tool],
    output_schema=IngestionSummary
)