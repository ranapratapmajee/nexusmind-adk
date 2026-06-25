# filepath: app/agent.py

import json
from typing import Any
from pydantic import BaseModel, Field
from config.settings import settings
from google.adk import Agent, Workflow, Event
from google.adk.workflow import START, node
from google.adk.models.lite_llm import LiteLlm
from app.tools import graph_rag_retrieval, web_search

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
    description="Executes graph and web searches together, then synthesizes both data payloads into a flat bulleted report.",
    model=llm,
    instruction="""
    ROLE: Dual-Engine Systems Research Specialist.
    
    🎯 PHASE 1 - MANDATORY DUAL-TOOL SEARCH (COMPULSORY):
    1. You are strictly forbidden from answering using your pre-trained memory.
    2. To answer completely, you REQUIRE data from both your internal database and the live internet.
    3. You MUST call BOTH `graph_rag_retrieval` AND `web_search` for the query: "{forward_query}"
    4. Do not stop after executing only one tool. Execute both tools to combine their tracking data.

    ⚙️ PHASE 2 - PAYLOAD HARVESTING LAWS:
    Once BOTH tools have completed their execution cycles, read the full text streams. Merge your internal graph nodes with the live website contents. Write at least 6 to 10 highly granular, technically dense, informative plain bullet points.

    🔒 PHASE 3 - STYLING & COMPLIANCE LAWS:
    1. FLAT BULLETS ONLY: Your entire final response must consist solely of standard, plain bullet points. DO NOT use Markdown headers (# or ##), bold text sections, asterisks dividers, or blockquotes.
    2. ZERO INLINE LEAKAGE: Keep sentences completely clean. Do not include brackets, citation markers, hash IDs, or explicit links within the main body paragraphs.
    3. NO FILLER TEXT: Start your output immediately with the first extracted technical bullet point. Do not talk about your tool workflows.
    4. SYSTEM FOOTER REFERENCES: Conclude your final list items using exactly these literal string prefix templates to isolate data origins at the very bottom:
       - REFERENCES - Source Parent ID: [Insert unique tracking hashes found here]
       - REFERENCES - Source Website URL: [Insert clean scraped domain names found here]
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