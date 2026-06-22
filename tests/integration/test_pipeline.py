# filepath: tests/integration/test_pipeline.py
import pytest
import asyncio
from app.workflows.master_pipeline import nexus_engine
from app.infrastructure.neo4j_service import neo4j_service
from app.infrastructure.chroma_service import chroma_service

@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default asyncio event loop for the test module."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_end_to_end_ingestion_and_research_flow():
    """Verifies that document extraction data pipes execute through the dynamic router cleanly."""
    
    # 1. Define Simulated Document Ingestion Context Payload
    simulated_pdf_text = "DOCUMENT_INJECT_STREAM:\nFilename: test_policy.pdf\nContent:\nProject NexusMind uses Python. Python utilizes UV package management infrastructure."
    
    logger_msg = "⚡ Launching E2E Ingestion Verification Stage..."
    print(logger_msg)
    
    ingest_payload = await nexus_engine.process_transaction(
        user_query=simulated_pdf_text,
        history=[]
    )
    
    # Assertions to verify ingestion outputs match expected schemas
    assert ingest_payload["status"] == "SUCCESS"
    assert "Ingestion Success" in ingest_payload["markdown_answer"]
    assert len(ingest_payload["dynamic_followups"]) > 0

    # 2. Define Simulated Multi-Hop Research Inquiry
    research_query = "What package manager infrastructure does Project NexusMind use?"
    print("⚡ Launching E2E Knowledge Graph Retrieval Phase...")
    
    research_payload = await nexus_engine.process_transaction(
        user_query=research_query,
        history=[
            {"role": "user", "content": "Hello Nexa!"},
            {"role": "assistant", "content": "Hello! How can I assist your operations today?"}
        ]
    )
    
    # Assertions to verify final research responses match expected schemas
    assert research_payload["status"] == "SUCCESS"
    assert research_payload["markdown_answer"] is not None
    assert len(research_payload["dynamic_followups"]) == 3