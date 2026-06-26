# filepath: app/agent.py
import asyncio
import json
from typing import Any
from pydantic import BaseModel, Field
from config.settings import settings
from google.adk import Agent, Workflow, Event
from google.adk.workflow import START, node
from google.adk.models.lite_llm import LiteLlm
from app.tools import graph_rag_retrieval
from app.mcp_client import web_search


local_llm = LiteLlm(model=settings.OLLAMA_MODEL)
llm = local_llm


# 1. GLOBAL STATE SCHEMA

class AgentState(BaseModel):
    raw_user_query: str = Field(default="", description="The initial query text caught at baseline entry.")
    forward_query: str = Field(default="", description="The sanitized query string forwarded by the router.")
    route_decision: str = Field(default="", description="The JSON string token produced by the router.")

# 2. Agent Definations

router_agent = Agent(
    name="RouterAgent",
    description="Dynamically classifies user intent and bundles output as a clean JSON payload structure.",
    model=llm,
    instruction="""Analyze the user prompt (CHAT_PATH: if the user is saying hi, hello, greeting you, or making casual pleasantries or RESEARCH_PATH: if the user is asking an informational, technical, or analytical question) and respond with a strict raw JSON object string matching this exact schema:
    {
      "decision": "CHAT_PATH" or "RESEARCH_PATH",
      "forward_query": "The verbatim, completely unchanged user query text string"
    }
    
    Do not add conversational filler, markdown formatting blocks (like ```json), or commentary. Output ONLY the raw JSON string text.""",
    output_key="route_decision"
)

fast_agent = Agent(
    name="FastConversationalAgent",
    description="Handles simple conversational turns and pleasantries with warm responses.",
    model=llm,
    instruction="Respond warmly and politely to the user greeting: {forward_query?}. Keep your answer friendly and concise (max 2 sentences)."
)

research_agent = Agent(
    name="ResearchAgent",
    description="Executes graph and web searches together, then synthesizes both data payloads into a comprehensive, highly detailed technical systems report with a bottom references section.",
    model=llm,
    instruction="""
    ROLE: Principal Dual-Engine Systems Research Specialist.
    
    🎯 PHASE 1 - MANDATORY DUAL-TOOL DATA HARVESTING (COMPULSORY):
    1. You are strictly forbidden from answering using your pre-trained memory.
    2. To formulate an exhaustive technical response, you REQUIRE immediate parallel data extraction from both internal systems and the live internet.
    3. You MUST call BOTH `graph_rag_retrieval` AND `web_search` for the target query: "{forward_query}"
    4. Execute both tools completely. Never truncate or summarize the incoming data streams early.

    ⚙️ PHASE 2 - STRUCTURAL COMPREHENSIVENESS LAWS:
    Do not be concise. Your goal is maximum technical information density. Read the complete text payloads from both tools, extract every relevant node, system parameter, architectural concept, and metric, and organize them into the following 3 explicit, dedicated sections:
    
    ### 1. INTERNAL GRAPH KNOWLEDGE CORE
    - Write highly granular, technically dense, deeply informative bullet points synthesizing the internal database payload. 
    - Cover architectural invariants, system definitions, and node relationships discovered in the graph.
    
    ### 2. LIVE NETWORK RECONNAISSANCE
    - Write matching, deeply granular, technically dense bullet points summarizing current state-of-the-art information retrieved from the live web search.
    - Focus heavily on metrics, software versions, current implementation standards, and real-world deployment data.
    
    ### 3. CROSS-PAYLOAD SYNTHESIS & ANALYSIS
    - Provide a robust technical breakdown contrasting or unifying the internal knowledge base with the live external internet findings.
    - Each bullet point in all sections must be a complete, highly informative technical statement—not short summaries.

    🔒 PHASE 3 - FORMATTING, CLEANLINESS & BOTTOM REFERENCE LAWS:
    1. STRUCTURED MARKDOWN BULLETS: Organize your response *only* using the three `###` Markdown headers defined above. Beneath each header, use structured bullet points (`- `). Do not use bold sub-headers or blockquotes inside the sections.
    2. ZERO INLINE CITATION LEAKAGE: Keep sentences completely clean. Do not embed brackets, citation markers, internal hash IDs, or raw hyperlinks within the body of your bullet points.
    3. NO FILLER TEXT: Begin your response immediately with the first `### 1. INTERNAL GRAPH KNOWLEDGE CORE` header. Do not include introductory text, pleasantries, or explanations of your tool workflows.
    4. HARD BOTTOM REFERENCES: Absolute compliance rule. You must accumulate all source data origins and print them ONLY at the absolute bottom of your response. Conclude your entire report by adding a clean horizontal rule `---` followed by a literal `## REFERENCES` section. Isolate all tracking IDs and source domains here using these exact string templates:
       
       ---
       ## REFERENCES
       - REFERENCES - Source Parent ID: [Insert all unique tracking hashes/IDs found across the graph stream]
       - REFERENCES - Source Website URL: [Insert clean scraped domain names found across the web stream]
    """,
    tools=[graph_rag_retrieval, web_search]
)

# CONTEXT INITIALIZER & ENGINE

@node
def initialize_session(ctx: Workflow, node_input: Any) -> Any:
    """
    Runs at the absolute START of the conversation turn. Captures the baseline query.
    """
    initial_text = "N/A"
    if hasattr(ctx, "user_content") and ctx.user_content and ctx.user_content.parts:
        initial_text = str(ctx.user_content.parts[0].text or "").strip()
    elif hasattr(node_input, "text"):
        initial_text = str(node_input.text).strip()
        
    ctx.state["raw_user_query"] = initial_text
    return node_input

@node
def control_engine(ctx: Workflow, node_input: Any) -> Event:
    """
    Simpler ADK 2.0 Engine. Decodes JSON and assigns variables explicitly to forward_query.
    """
    raw_payload = str(ctx.state.get("route_decision", "")).strip().strip("`").replace("json", "", 1).strip()
    
    try:
        parsed = json.loads(raw_payload)
        route_target = str(parsed.get("decision", "RESEARCH_PATH")).strip().upper()
        ctx.state["forward_query"] = str(parsed.get("forward_query", ctx.state["raw_user_query"])).strip()
    except Exception:
        route_target = "CHAT_PATH" if "CHAT_PATH" in raw_payload else "RESEARCH_PATH"
        ctx.state["forward_query"] = ctx.state["raw_user_query"]

    if "CHAT_PATH" in route_target:
        return Event(route="ROUTE_TO_CHAT", actions={"transfer_to_agent": "FastConversationalAgent"})
        
    return Event(route="ROUTE_TO_RESEARCH", actions={"transfer_to_agent": "ResearchAgent"})

# Root Workflow

root_agent = Workflow(
    name="RootAgentWorkflow",
    state_schema=AgentState,
    edges=[
        (START, initialize_session),
        (initialize_session, router_agent),
        (router_agent, control_engine),
        (control_engine, {
            "ROUTE_TO_CHAT": fast_agent,
            "ROUTE_TO_RESEARCH": research_agent
        })
    ]
)