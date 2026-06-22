# filepath: app/agents/research_nodes.py
from google.adk.agents import LlmAgent
from config.settings import settings
from app.models.chat_state import ResearchPlan, FusedContext, CoTSynthesis, SynthesisResponse
from app.tools.mcp_registry import chroma_tool, neo4j_tool, web_tool

planner_agent = LlmAgent(
    name="PlannerAgent",
    model=settings.OLLAMA_MODEL,
    description="Deconstructs unstructured inquiries into search paths.",
    output_schema=ResearchPlan
)

retrieval_agent = LlmAgent(
    name="RetrievalAgent",
    model=settings.OLLAMA_MODEL,
    description="Autonomous database retrieval worker calling specialized MCP data tools.",
    tools=[chroma_tool, neo4j_tool, web_tool]
)

# --- NEW EXTENSION: UPGRADED MATHEMATICAL FUSION AGENT ---
fusion_agent = LlmAgent(
    name="KnowledgeFusionAgent",
    model=settings.OLLAMA_MODEL,
    description="Applies Reciprocal Rank Fusion principles to rank database overlaps.",
    instruction="""
    Analyze the raw multi-source retrieval outputs. 
    Mathematically cross-reference strings matching identical entity keywords using the Reciprocal Rank Fusion formula: 1 / (60 + rank).
    Compile a single, compressed, high-density unified context text block.
    """,
    output_schema=FusedContext
)

# --- NEW EXTENSION: MULTI-HOP REASONER NODE ---
reasoner_agent = LlmAgent(
    name="ReasonerAgent",
    model=settings.OLLAMA_MODEL, # Can be scaled via master pipeline router
    description="Multi-hop Chain-of-Thought analytical core exploring linked data nodes.",
    instruction="""
    Perform a rigorous Chain-of-Thought analysis over the fused context block.
    Do not jump to immediate structural conclusions. Outline explicit chronological deduction steps.
    Resolve multi-hop connections (e.g., if Node A links to Node B, and Node B links to Node C).
    """,
    output_schema=CoTSynthesis
)

# --- NEW EXTENSION: RESPONSE GENERATOR ---
response_agent = LlmAgent(
    name="ResponseAgent",
    model=settings.GEMINI_MODEL, # Uses premium Gemini to handle final synthesis
    description="Final output formatter generating clean markdown, source citations, and interactive cross-questions.",
    instruction="""
    Read the raw reasoning path and dense context compilation.
    Draft a polished production-grade markdown answer complete with bracketed citation tracking.
    Proactively generate exactly 3 highly conversational, context-aware interactive follow-up cross-questions.
    """,
    output_schema=SynthesisResponse
)