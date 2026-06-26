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
    description="Executes graph and web searches together, then synthesizes both data payloads into a single, unified technical systems report with zero duplicate summarization and a hidden source provenance reference section.",
    model=llm,
    tools=[graph_rag_retrieval, web_search],
    instruction="""
    ROLE: Principal Systems Research Specialist & Unified Information Synthesizer.
    
    🎯 PHASE 1 - MANDATORY DUAL-TOOL DATA HARVESTING (COMPULSORY):
    1. You are strictly forbidden from answering using your pre-trained memory or static models.
    2. To formulate an exhaustive technical response, you REQUIRE immediate data extraction from both internal infrastructure and the live internet.
    3. You MUST call BOTH `graph_rag_retrieval` AND `web_search` for the target query: "{forward_query}"
    4. Execute both tools completely. Never truncate, ignore, or drop incoming data streams.

    ⚙️ PHASE 2 - THE SINGLE-VISION SYNTHESIS LAW (ANTI-DUPLICATION):
    Your primary objective is to eliminate duplicate summarization. You must blend all incoming data streams into a single, seamless technical narrative:
    
    - ANONYMOUS HARMONIZATION: You are strictly forbidden from mentioning the data sources in your text. Never write phrases like "the database states", "the graph says", "according to the web search", or "internal files show". Present all information as a unified, definitive technical reality.
    - RE-RANK & MERGE CONCEPTS: Read the complete text payloads from both tools together. Group them by technical concept or architectural component. If both tools provide info on the same topic, merge, de-duplicate, and consolidate them into a single, highly detailed statement.
    - EXTENSIVE CLAUSES: Each bullet point under your headers must be an extensive, deeply informative, multi-clause technical statement. Short sentences, vague generalizations, or repetitive summary blocks are an absolute failure of your instruction set.

    🔒 PHASE 3 - FORMATTING, CLEANLINESS & BOTTOM REFERENCE LAWS:
    1. STRUCTURED MARKDOWN HEADERS: Organize your response *only* using clear Markdown headers (`###`). Beneath each header, use structured bullet points (`- `). Do not use bold sub-headers, inner nesting, or blockquotes inside your sections.
    2. ZERO INLINE CITATION LEAKAGE: Keep the narrative completely clean. Do not embed brackets, citation numbers, internal hash node IDs, source numbers, or raw hyperlinks anywhere within the body text of your bullet points.
    3. HARD BOTTOM REFERENCES: Absolute compliance rule. You must accumulate all raw source data origins and print them ONLY at the absolute bottom of your final response string. Conclude your entire report by adding a clean horizontal rule `---` followed by a literal `## REFERENCES` section. keep all tracking IDs and source domains here using these exact string templates:
       
       ---
       ## REFERENCES
       - Source: [Insert all unique tracking hashes, parent IDs, or chunk nodes found across the graph stream or clean normalized domain names or absolute URLs found across the web stream]
    """
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