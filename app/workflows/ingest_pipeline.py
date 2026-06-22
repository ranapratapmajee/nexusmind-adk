# filepath: app/workflows/ingest_pipeline.py
import logging
from typing import Dict, Any
from google.adk.agents import SequentialWorkflow
from app.agents.ingest_nodes import (
    parser_agent, chunker_agent, entity_extractor_agent,
    relation_extractor_agent, kg_validator_agent, indexer_agent
)

logger = logging.getLogger(__name__)

# Declaratively construct the 6-stage continuous pipeline graph topology
ingest_workflow_pipeline = SequentialWorkflow(
    name="Enterprise-PDF-Ingestion-Pipeline",
    description="Processes PDF documents through 6 granular stages to extract text embeddings and graph metadata.",
    steps=[
        parser_agent,              # PDF Input stream -> ParserOutput
        chunker_agent,             # ParserOutput -> ChunkedOutput
        entity_extractor_agent,    # ChunkedOutput -> ExtractedEntities
        relation_extractor_agent,  # ExtractedEntities -> ExtractedGraphTriplets
        kg_validator_agent,        # ExtractedGraphTriplets -> Validated Graph
        indexer_agent              # Validated Graph -> IngestionSummary (DB Commit)
    ]
)

class NexusIngestionFlowEngine:
    """Operational workflow manager running document indexing outside runtime user loops."""

    @staticmethod
    async def ingest_pdf_document(file_content_stream: str, filename: str) -> Dict[str, Any]:
        logger.info(f"📁 [PDF Pipeline] Launching 6-stage ingestion for target file: '{filename}'")
        
        inbound_context = f"Target PDF Filename: {filename}\nRaw Document Stream Source:\n{file_content_stream}"
        
        try:
            pipeline_outcome = await ingest_workflow_pipeline.run(input=inbound_context)
            logger.info(f"✅ [PDF Pipeline] Indexing complete for: '{filename}'")
            
            return {
                "status": "COMPLETED",
                "metrics": {
                    "vector_chunks": pipeline_outcome.get("vector_chunks_indexed", 0),
                    "graph_mutations": pipeline_outcome.get("graph_entities_merged", 0)
                },
                "summary": pipeline_outcome.get("narrative_audit_trail", "Audit execution log processed successfully.")
            }
            
        except Exception as e:
            logger.error(f"❌ [PDF Pipeline] Execution crashed: {str(e)}")
            return {
                "status": "CRASHED",
                "metrics": {"vector_chunks": 0, "graph_mutations": 0},
                "summary": f"Framework operational error tracker dump: {str(e)}"
            }

ingest_flow_engine = NexusIngestionFlowEngine()