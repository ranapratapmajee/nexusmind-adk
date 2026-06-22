# filepath: app/research_pipeline.py
import logging
from google.adk import Agent, Workflow
from google.adk.models.lite_llm import LiteLlm
from config.settings import settings
from app.tools import chroma_tool, neo4j_tool, web_tool # For research

logger = logging.getLogger(__name__)

local_model = LiteLlm(model="ollama_chat/qwen2.5-coder:7b")
llm = local_model

# =========================================================
# 1. SPECIALIZED RESEARCH AGENT NODES
# =========================================================

planner_agent = Agent(
    name="PlannerAgent",
    model=llm,
    description="Deconstructs unstructured inquiries into search paths.",
    instruction="""Analyze the incoming user prompt. Generate clear search terms for vector lookups 
    and explicit entity tokens for graph traversal queries.""",
    mode="single_turn"
)

retrieval_agent = Agent(
    name="RetrievalAgent",
    model=llm,
    description="Autonomous database retrieval worker calling specialized MCP data tools.",
    instruction="""Review the generated plan passed from the planner node. 
    Execute the chroma_tool, neo4j_tool, and web_tool to extract raw context snippets matching the requested vectors and graph entities.""",
    tools=[chroma_tool, neo4j_tool, web_tool],
    mode="single_turn"
)

fusion_agent = Agent(
    name="KnowledgeFusionAgent",
    model=llm,
    description="Applies Reciprocal Rank Fusion principles to rank database overlaps.",
    instruction="""Analyze the raw multi-source retrieval outputs passed from the retrieval node. 
    Mathematically cross-reference strings matching identical entity keywords using the Reciprocal Rank Fusion formula: 1 / (60 + rank).
    Compile a single, compressed, high-density unified context text block.""",
    mode="single_turn"
)

reasoner_agent = Agent(
    name="ReasonerAgent",
    model=llm, 
    description="Multi-hop Chain-of-Thought analytical core exploring linked data nodes.",
    instruction="""Perform a rigorous Chain-of-Thought analysis over the fused context block passed from the fusion node.
    Do not jump to immediate structural conclusions. Outline explicit chronological deduction steps.
    Resolve multi-hop connections (e.g., if Node A links to Node B, and Node B links to Node C).""",
    mode="single_turn"
)

response_agent = Agent(
    name="ResponseAgent",
    model=settings.GEMINI_MODEL, 
    description="Final output formatter generating clean markdown, source citations, and interactive cross-questions.",
    instruction="""Read the raw reasoning path and dense context compilation passed from the reasoner node.
    1. Draft a polished production-grade markdown answer complete with bracketed citation tracking.
    2. Proactively generate exactly 3 highly conversational, context-aware interactive follow-up cross-questions.""",
    mode="single_turn"
)

# =========================================================
# 2. DECLARATIVE WORKFLOW TOPOLOGY
# =========================================================
deep_research_subgraph = Workflow(
    name="DeepResearchPipeline",
    edges=[
        (
            "START",
            planner_agent,
            retrieval_agent,
            fusion_agent,
            reasoner_agent,
            response_agent
        )
    ]
)
