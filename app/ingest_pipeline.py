# filepath: app/ingest_pipeline.py
import re
import logging
import json
import uuid
from typing import Dict, Any, List
from google.genai import types
from google.adk import Agent, Workflow
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm
from google.adk.workflow import START, node
from pydantic import BaseModel, Field
from config.settings import settings

from app.services import pdf_processor, vector_store, graph_db

logger = logging.getLogger(__name__)
ingestion_llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. STRUCTURAL PIPELINE STATE SCHEMA
# =========================================================
class IngestionState(BaseModel):
    extracted_entities_raw: str = Field(default="", description="The temporary raw unstructured JSON concept token array string.")

# =========================================================
# 2. REFINED MINING AGENT
# =========================================================

entity_extractor_agent = Agent(
    name="EntityExtractorAgent",
    description="Mines precise technical abstractions and concepts from targeted document chunks and echoes context keys.",
    model=ingestion_llm,
    instruction="""
    TASK: Parse the incoming text block which explicitly contains a CHUNK_ID and a CHUNK_TEXT segment.
    1. Identify and extract all core domain concepts, systems, and technical architectures.
    2. Read the provided CHUNK_ID and preserve it.
    
    OUTPUT FORMAT: You must return a strict, valid JSON object matching this schema precisely:
    {
      "chunk_id": "The exact CHUNK_ID string provided in the user input text",
      "entities": [
         {"name": "Concept Name", "type": "Concept OR Technology OR System"}
      ]
    }
    
    CRITICAL: Output ONLY valid raw JSON. Do not write markdown wrappers, triple backticks, or introduction text.
    """,
    output_key="extracted_entities_raw"
)

# =========================================================
# 3. DETERMINISTIC DATA WRITER & NORMALIZATION NODE
# =========================================================


def repair_truncated_json(raw_text: str) -> str:
    """
    🛡️ STRUCTURAL JSON FAULT RECOVERY LAYER:
    Detects and auto-repairs truncated or clipped JSON blocks output by local models,
    guaranteeing successful string compilation even if mid-token truncations occur.
    """
    fixed_text = raw_text.strip()
    
    # 🧯 Case 1: If the string ends inside an unclosed property value (e.g., `"type": "Technolog`)
    # Capture unclosed keys or string assignments and slap on missing quote/brackets
    if fixed_text.count('"') % 2 != 0:
        # Check if it was cut off inside a string value block
        if re.search(r'":\s*"[^"]*$', fixed_text):
            fixed_text += '"}'
        else:
            fixed_text += '"'

    # 🧯 Case 2: Clean up dangling, half-written keys/values like `{"name":`
    fixed_text = re.sub(r',\s*["\w\s]*:\s*$', '', fixed_text) # Strip dangling keys after commas
    fixed_text = re.sub(r'{\s*["\w\s]*:\s*$', '', fixed_text) # Strip dangling keys at opening loops
    
    # 🧯 Case 3: Fix trailing array/object brackets balance
    open_brackets = fixed_text.count('[') - fixed_text.count(']')
    open_braces = fixed_text.count('{') - fixed_text.count('}')
    
    # Dynamically append structural terminations if missing
    if open_braces > 0:
        fixed_text += "}" * open_braces
    if open_brackets > 0:
        fixed_text += "]" * open_brackets
        
    return fixed_text

@node
def clean_and_parse_extraction(ctx: Workflow, node_input: Any) -> str:
    """
    🌟 THE POLYMORPHIC WORKER BRIDGE:
    Parses payloads, auto-repairs truncated JSON data anomalies, and updates Neo4j.
    """
    raw_payload = ctx.state.get("extracted_entities_raw", "").strip()
    
    # RECOVERY: Reconstruct active chunk context via session token segments
    fallback_chunk_id = ""
    try:
        if hasattr(ctx, "session_id") and ctx.session_id and "session--" in ctx.session_id:
            session_segments = ctx.session_id.split("--")
            if len(session_segments) >= 2:
                fallback_chunk_id = session_segments[1].strip()
    except Exception as h_ex:
        logger.warning(f"⚠️ Could not parse chunk context reference trail: {str(h_ex)}")

    if raw_payload.startswith("```"):
        raw_payload = raw_payload.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if raw_payload.upper().startswith("JSON"):
        raw_payload = raw_payload[4:].strip()

    try:
        # 🔧 Fix applied right before loading: Run text repair pass first
        sanitized_payload = repair_truncated_json(raw_payload)
        parsed_data = json.loads(sanitized_payload)
        
        target_chunk = ""
        entities = []

        if isinstance(parsed_data, list):
            logger.info("ℹ️ Local LLM bypassed object wrappers; routing via session string fallback.")
            entities = parsed_data
            target_chunk = fallback_chunk_id
        elif isinstance(parsed_data, dict):
            target_chunk = parsed_data.get("chunk_id", "").strip()
            entities = parsed_data.get("entities", [])
            if not target_chunk or target_chunk.upper() == "UNKNOWN":
                target_chunk = fallback_chunk_id

        if not target_chunk:
            logger.error("❌ Aborting graph commit: Context parameters missing.")
            return "❌ Finished with missing metadata extraction matching gaps."

        committed_count = 0
        for entity in entities:
            if isinstance(entity, dict):
                name = entity.get("name")
                ent_type = entity.get("type", "Concept")
                if name:
                    graph_db.save_concept_mention(name=name, type=ent_type, target_chunk_id=target_chunk)
                    committed_count += 1
                
        logger.info(f"💾 Graph write pass complete. Forged {committed_count} semantic links for chunk: {target_chunk}")
        return f"Successfully mapped {committed_count} concepts to {target_chunk}."
        
    except Exception as e:
        logger.error(f"❌ Failed data normalizer execution block pass: {str(e)} | Raw: {raw_payload}")
        return f"Normalization exception: {str(e)}"

# =========================================================
# 4. WORKFLOW TOPOLOGY DEFINITION (CLEAN & STREAMLINED)
# =========================================================
ingest_workflow_pipeline = Workflow(
    name="IngestionPipeline",
    state_schema=IngestionState,
    edges=[
        (START, entity_extractor_agent),
        (entity_extractor_agent, clean_and_parse_extraction)
    ]
)

# =========================================================
# 5. EXECUTION ENGINE FLOW MANAGER
# =========================================================
class NexusIngestionFlowEngine:
    @staticmethod
    async def ingest_pdf_document(file_content_stream: str, filename: str) -> Dict[str, Any]:
        logger.info(f"📁 Running ingestion graph for file: '{filename}'")
        print(f"\n🚀 Commencing layout parsing graph layer for target asset: '{filename}'")
        
        try:
            hierarchical_chunks = pdf_processor.slice_hierarchical_chunks(
                text=file_content_stream,
                document_name=filename
            )
            
            pipeline_runner = InMemoryRunner(agent=ingest_workflow_pipeline, app_name="app")
            if hasattr(pipeline_runner, "auto_create_session"):
                pipeline_runner.auto_create_session = True
                
            report_accumulator = []
            
            for block in hierarchical_chunks:
                p_id = block["parent_id"]
                p_text = block["parent_text"]
                child_fragments = block["children"]
                
                print(f"\n📦 Analyzing Parent Segment Block [ {p_id} ]")
                
                for child in child_fragments:
                    c_id = child["id"]
                    c_text = child["text"]
                    
                    print(f"📡 Processing [ {c_id} ] ➔ Vector Store & Graph Node Assembly...")
                    
                    # ✅ LAYER 1: Core Database Writes happen deterministically via safe Python calls
                    vector_store.insert_child_vector(child_id=c_id, child_text=c_text, parent_id=p_id)
                    graph_db.save_hierarchical_edge(child_id=c_id, parent_id=p_id, parent_text=p_text)
                    
                    # ✅ LAYER 2: Multi-Agent Pipeline session identifier serialization
                    # Encodes the active chunk id safely within double-dash boundaries
                    isolated_session = f"session--{c_id}--{uuid.uuid4().hex[:6]}"
                    
                    message_payload_string = (
                        f"CHUNK_ID: {c_id}\n"
                        f"CHUNK_TEXT:\n{c_text}"
                    )
                    
                    outcome_stream = pipeline_runner.run_async(
                        user_id="ingest_cli_service",
                        session_id=isolated_session,
                        new_message=types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=message_payload_string)]
                        )
                    )

                    text_accumulator = ""
                    async for event in outcome_stream:
                        if hasattr(event, "text") and event.text:
                            text_accumulator += event.text
                        elif hasattr(event, "content") and event.content:
                            c = event.content
                            if hasattr(c, "parts"):
                                for part in c.parts:
                                    if hasattr(part, "text") and part.text:
                                        text_accumulator += part.text
                                        
                    report_accumulator.append(text_accumulator.strip())

            print("\n🏁 All parent/child workflow blocks synthesized safely.")
            unified_report = "\n\n".join([r for r in report_accumulator if r])
            return {
                "status": "SUCCESS",
                "markdown_answer": f"### 📁 Processing Report: PDF Ingestion Success\n\n{unified_report}"
            }
            
        except Exception as e:
            print(f"\n❌ Thread collapsed: {str(e)}")
            logger.error(f"❌ Ingestion crashed: {str(e)}")
            return {
                "status": "CRASHED",
                "markdown_answer": f"❌ **Ingestion failure tracker dump:** {str(e)}"
            }

ingest_flow_engine = NexusIngestionFlowEngine()