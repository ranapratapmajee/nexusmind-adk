# filepath: app/research_pipeline.py
import logging
from typing import Any
from google.adk import Agent, Workflow, Event
from google.adk.models.lite_llm import LiteLlm
from config.settings import settings

# Import the multi-stage retrieval tools we created
from app.tools import chroma_search, neo4j_traverse, chroma_fetch, web_search

logger = logging.getLogger(__name__)

# 🚀 UPGRADE: Route the complex multi-hop research pipeline through your Gemini engine
research_llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. COGNITIVE RESEARCH AGENT NODES
# =========================================================

planner_agent = Agent(
    name="PlannerAgent",
    model=research_llm,
    description="Deconstructs inquiries into targeted vector and semantic graph entry parameters.",
    instruction="""
    ROLE: Search Parameters Architect.
    TASK: Convert the user's question into precise string keys for step-by-step vector and graph tool execution.
    
    OUTPUT FORMAT FORMATTING:
    Output a valid JSON object with 'seed_query' mapping to the core question. Avoid markdown or chatter.
    {
        "seed_query": "primary meaning string"
    }
    """,
    mode="single_turn"
)

retrieval_agent = Agent(
    name="RetrievalAgent",
    model=research_llm,
    description="Autonomous engine orchestrating multi-stage context collection tool sequences.",
    instruction="""
    ROLE: Hybrid Multi-Stage Retrieval Gatherer.
    TASK: Execute the available tools in sequence to build a complete context picture.
    
    SEQUENTIAL PLAYBOOK:
    1. Call `chroma_search` using the 'seed_query' parameter to collect initial child chunk text blocks.
    2. Read the 'chunk_id' from those vector results and pass it directly into `neo4j_traverse`.
    3. Look closely at the graph data dictionary keys: 'origin_element', 'relationship_path', and 'connected_target'. 
       - If 'connected_target' contains a string format matching a vector anchor (e.g. 'chunk_X'), pass that ID into `chroma_fetch` to execute a precision text block pull.
    
    Combine all text documents and structural paths returned by your tool calls into a single, unsummarized context block and pass it downstream.
    """,
    tools=[
        chroma_search,
        neo4j_traverse,
        chroma_fetch
    ],
    mode="single_turn"
)

gatekeeper_agent = Agent(
    name="ContextGatekeeperAgent",
    model=research_llm,
    description="Evaluates context data completeness and controls web search fallback triggers.",
    instruction="""
    ROLE: Context Completeness Gatekeeper.
    TASK: Evaluate if the gathered database context contains enough detailed facts to comprehensively answer the user's original query.
    
    STRICT VERDICT RULES:
    - If the database context is thorough, detailed, and directly answers the question -> Output exactly: SUFFICIENT
    - If the database context is empty, brief, or missing specific details -> Call `web_search` using the query, merge the internet search data with the database records, and output the consolidated text.
    """,
    tools=[web_search],
    mode="single_turn"
)

fusion_agent = Agent(
    name="KnowledgeFusionAgent",
    model=research_llm,
    description="Applies ranking and deduplication across multi-source data blocks.",
    instruction="""
    TASK: Deduplicate data streams from the gatekeeper node. Group overlapping points logically and organize them into a clean, high-density unified layout. Keep all source references intact.
    """,
    mode="single_turn"
)

reasoner_agent = Agent(
    name="ReasonerAgent",
    model=research_llm, 
    description="Multi-hop Chain-of-Thought engine.",
    instruction="""
    TASK: Perform step-by-step logic deduction using the fused data text block. Document your reasoning path (Step 1, Step 2, etc.), tracing how graph relationships explain your vector facts. Do not guess beyond the provided text.
    """,
    mode="single_turn"
)

response_agent = Agent(
    name="ResponseAgent",
    model=research_llm, 
    description="Transforms analytical trails into clean markdown summaries.",
    instruction="""
    TASK: Synthesize the reasoning trail into a final response. Use clear Markdown layout structures (headings, lists, tables). Embed explicit, inline citations pointing directly back to the database sources. Do not include introductory filler.
    """,
    mode="single_turn"
)

# =========================================================
# 2. DYNAMIC WORKFLOW ROUTING FUNCTION
# =========================================================

def process_gatekeeper_decision(node_input: Any, invocation_context: Any = None) -> str:
    """Passes the complete evaluation payload down to the fusion engine."""
    text_content = getattr(node_input, "text", str(node_input))
    logger.info("🛡️ Context Gatekeeper Evaluation Completed. Forwarding text data stream to Fusion core.")
    return text_content

# =========================================================
# 3. EXPORTED WORKFLOW TOPOLOGY
# =========================================================

deep_research_subgraph = Workflow(
    name="DeepResearchPipeline",
    edges=[
        # Blueprint and Gathering Phase
        ("START", planner_agent),
        (planner_agent, retrieval_agent),
        
        # Guard Phase: Intercepting context to check for sparse data bounds
        (retrieval_agent, gatekeeper_agent),
        (gatekeeper_agent, process_gatekeeper_decision),
        
        # Synthesis and Writing Phase
        (process_gatekeeper_decision, fusion_agent),
        (fusion_agent, reasoner_agent),
        (reasoner_agent, response_agent)
    ]
)