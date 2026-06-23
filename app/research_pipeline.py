# filepath: app/research_pipeline.py
import logging
from typing import Any
from google.adk import Agent, Workflow, Event
from google.adk.models.lite_llm import LiteLlm
from config.settings import settings

# 🌟 UPDATED: Import the simplified high-reliability tools from tools.py
from app.tools import graph_rag_retrieval, web_search

logger = logging.getLogger(__name__)

# 🚀 KEEP LOCAL: Route the complex multi-hop research pipeline through your local engine
research_llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. COGNITIVE RESEARCH AGENT NODES
# =========================================================

planner_agent = Agent(
    name="PlannerAgent",
    model=research_llm,
    description="Deconstructs inquiries into targeted vector and semantic graph entry parameters.",
    instruction="""
    ROLE: Search Parameters Architect & Intent Deconstructor.
    
    TASK: Convert the user's primary question into a precise, clean search term key optimized for concurrent vector, graph, and web tool execution.
    
    STRICT OUTPUT RULES:
    1. Output EXACTLY a valid RFC-compliant JSON object containing the 'seed_query' key mapping to the distilled semantic question.
    2. Do NOT wrap the JSON block inside any markdown formatting tags (e.g., do not use ```json).
    3. Do NOT include any conversational introduction, trailing confirmation commentary, or system feedback text.
    
    TARGET SCHEMATIC:
    {
        "seed_query": "extracted clean query string"
    }
    """,
    mode="single_turn"
)

retrieval_agent = Agent(
    name="RetrievalAgent",
    model=research_llm,
    description="Autonomous engine running parallel database and web extractions.",
    instruction="""
    ROLE: Unified Context Collector.
    
    TASK: Gather internal database knowledge and external web insights simultaneously using your tools.
    
    CRITICAL STEP EXECUTION:
    1. Call `graph_rag_retrieval` using the 'seed_query' parameter to execute the local database data harvest.
    2. Call `web_search` using the 'seed_query' parameter to pull live web text anchors.
    
    FALLBACK & COMPILATION RULE:
    - Combine the text output from BOTH tools into one single context block.
    - CRITICAL DETECTOR: If the `graph_rag_retrieval` tool indicates that no local chunks were found or failed, do NOT abort the turn. Rely entirely on the output from `web_search` to feed the downstream reasoning pipeline.
    - Pass the raw aggregated text block downstream without altering or dropping any facts.
    """,
    tools=[
        graph_rag_retrieval,
        web_search
    ],
    mode="single_turn"
)

analytical_synthesis_agent = Agent(
    name="AnalyticalSynthesisAgent",
    model=research_llm,
    description="Consolidates multi-source payloads and runs deep Chain-of-Thought relationship deduction.",
    instruction="""
    ROLE: Cross-Source Knowledge Fusion Processor & Chain-of-Thought Reasoner.
    
    TASK: Receive the raw multi-source retrieval stream, eliminate structural noise, and execute a multi-hop deductive logical audit trail.
    
    PHASE 1 - KNOWLEDGE FUSION & DEDUPLICATION:
    - Group overlapping concepts, entities, and data points logically.
    - Clean away noisy structural text artifacts and repetitive metadata logs.
    - Ensure every distinct fact group keeps its source tracking markers (e.g., source chunk IDs or web domains) fully intact.
    
    PHASE 2 - CHAIN-OF-THOUGHT REASONING:
    - Conduct an explicit, step-by-step logical analysis using only the fused facts.
    - Map out an analytical trail (Step 1, Step 2, etc.) tracing out how live internet insights align with or support your local database vector facts and graph structures.
    
    STRICT OPERATIONAL CONTROLS:
    - GROUNDING ONLY: Do not guess, extrapolate, or introduce external assumptions. If a fact is not explicitly mentioned in the context payload, treat it as entirely non-existent.
    - NO STATUS NOISE: Do not print internal agent task tracking logs, status checkmarks, or pipeline procedural comments.
    """,
    mode="single_turn"
)

# 2026 temporal configuration anchored via settings
response_agent = Agent(
    name="ResponseAgent",
    model=research_llm, 
    description="Transforms analytical trails into clean markdown summaries.",
    instruction="""
    ROLE: Nexa Premium Assistant Synthesizer.
    
    TASK: Transform the incoming analytical reasoning trail and fused fact maps into a premium, comprehensive, user-facing final answer.
    
    CRITICAL STRUCTURE & LAYOUT RULES:
    1. TYPOGRAPHY: Organize information cleanly using clear Markdown layout structures (explicit semantic headings, organized bulleted lists, and clear comparative matrices where applicable).
    2. INLINE CITATIONS: Every factual claim must be explicitly anchored using inline citations pointing back to the original database chunk IDs or web domain origins (e.g., "...as verified in [chunk_4]").
    3. ZERO INTRODUCTION FILLER: Start directly with the substantive answer text. Do NOT use introductory pleasantries or meta-commentary (e.g., "Based on the provided reasoning trail...").
    4. NO AGENT LISTINGS: Do not name or reference internal agent node workflow names in the output.
    """,
    mode="single_turn"
)

# =========================================================
# 2. EXPORTED WORKFLOW TOPOLOGY
# =========================================================

deep_research_workflow = Workflow(
    name="DeepResearchWorkflow",
    edges=[
        # Blueprint and Gathering Phase
        ("START", planner_agent),
        (planner_agent, retrieval_agent),
        
        # High-Density Synthesis and Writing Phase
        (retrieval_agent, analytical_synthesis_agent),
        (analytical_synthesis_agent, response_agent)
    ]
)