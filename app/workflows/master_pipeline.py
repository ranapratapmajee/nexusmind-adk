# filepath: app/workflows/master_pipeline.py
import logging
from typing import Dict, Any, List
from google.adk.agents import SequentialWorkflow
from config.settings import settings

# Import updated agent definitions
from app.agents.guardrail_agent import guardrail_agent
from app.agents.router_agent import router_agent
from app.agents.fast_agent import fast_agent
from app.agents.research_nodes import (
    planner_agent, retrieval_agent, fusion_agent, 
    reasoner_agent, response_agent
)

logger = logging.getLogger(__name__)

# --- UPGRADED: 5-Stage Declarative ADK Workflow Subgraph ---
deep_research_subgraph = SequentialWorkflow(
    name="DeepResearchPipeline-V2",
    steps=[
        planner_agent,      # Input query -> ResearchPlan
        retrieval_agent,    # ResearchPlan -> Unstructured Tool Snippets
        fusion_agent,       # Tool Snippets -> FusedContext (RRF)
        reasoner_agent,     # FusedContext -> CoTSynthesis (Multi-hop)
        response_agent      # CoTSynthesis -> SynthesisResponse (Markdown + Pills)
    ]
)

class NexusCognitiveEngine:
    """Master controller coordinating transactional routing paths natively via ADK."""

    @staticmethod
    async def process_transaction(user_query: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        logger.info("🎬 Initializing cognitive pipeline execution loop...")

        # 1. Guardrail Execution Block
        guardrail_res = await guardrail_agent.run(input=f"Scan Input Stream: {user_query}")
        if guardrail_res.get("status") == "BLOCKED":
            return {
                "status": "SECURITY_REFUSAL",
                "markdown_answer": f"⚠️ **Security Policy Refusal:** {guardrail_res.get('reason')}",
                "dynamic_followups": []
            }

        # 2. Control Engine Routing Matrix
        routing_res = await router_agent.run(input=f"Analyze intent profile for: {user_query}")
        intent = routing_res.get("intent", "CASUAL_CHAT")
        complexity = routing_res.get("complexity", "STANDARD")
        
        logger.info(f"🧠 Routing decision: Route = {intent} | Compute Tier = {complexity}")

        # 3. Execution Path Branching Logic
        if intent == "CASUAL_CHAT":
            chat_out = await fast_agent.run(input=f"History: {str(history)} | Query: {user_query}")
            return {
                "status": "SUCCESS",
                "markdown_answer": chat_out.get("output", str(chat_out)),
                "dynamic_followups": ["Can you explain that point?", "Tell me more!", "What are my options?"]
            }

        elif intent == "INGESTION_UPLOAD":
            from app.workflows.ingest_pipeline import ingest_flow_engine
            ingest_res = await ingest_flow_engine.ingest_pdf_document(
                file_content_stream=user_query, 
                filename="interactive_user_upload.pdf"
            )
            return {
                "status": "SUCCESS",
                "markdown_answer": f"### 📁 Processing Report: PDF Ingestion Success\n\n{ingest_res.get('summary')}\n\n* **Vector Blocks Registered:** {ingest_res['metrics']['vector_chunks']}\n* **Graph Transactions Merged:** {ingest_res['metrics']['graph_mutations']}*",
                "dynamic_followups": ["Check database structural logs", "Query the uploaded content metrics"]
            }

        elif intent == "RESEARCH":
            # Dynamic Compute Tier Scaling Matrix
            if complexity == "EXTREME" or len(user_query) > 500:
                reasoner_agent.model = settings.GEMINI_MODEL
                response_agent.model = settings.GEMINI_MODEL
                logger.info("🚀 Escalated reasoning and generation cores to Premium Gemini.")
            else:
                reasoner_agent.model = settings.OLLAMA_MODEL
                response_agent.model = settings.GEMINI_MODEL
                logger.info("⚡ Balanced configuration: Local Reasoner + Gemini Response Engine.")
                
            # Run the expanded sequential research graph 
            research_out = await deep_research_subgraph.run(input=user_query)
            
            return {
                "status": "SUCCESS",
                "markdown_answer": research_out.get("markdown_answer"),
                "dynamic_followups": research_out.get("dynamic_followups", [])
            }
            
        else:
            return {
                "status": "UNHANDLED_ROUTE",
                "markdown_answer": "Cognitive orchestration router matrix routing error.",
                "dynamic_followups": []
            }

nexus_engine = NexusCognitiveEngine()