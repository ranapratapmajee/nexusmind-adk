# filepath: app/agent.py
import asyncio
import json
from typing import Any
from pydantic import BaseModel, Field
from config.settings import settings
from google.genai import types
from google.adk import Agent, Workflow, Event
from google.adk.workflow import START, node
from google.adk.models.lite_llm import LiteLlm
from app.mcp_client import web_search, hybrid_kg_vector_search

local_llm = LiteLlm(model=settings.OLLAMA_MODEL)
llm = local_llm

# =========================================================
# 1. GLOBAL STATE SCHEMA
# =========================================================
class AgentState(BaseModel):
    raw_user_query: str = Field(default="", description="The initial query text caught at baseline entry.")
    forward_query: str = Field(default="", description="The sanitized query string forwarded by the router.")
    route_decision: str = Field(default="", description="The JSON string token produced by the router.")

# =========================================================
# 2. AGENT DEFINITIONS
# =========================================================

router_agent = Agent(
    name="RouterAgent",
    description="Dynamically classifies user intent and bundles output as a clean JSON payload structure.",
    model=llm,
    instruction="""Analyze the user prompt. Classify as CHAT_PATH for casual turns/pleasantries/greetings, or RESEARCH_PATH for technical/informational lookups. 
    Respond ONLY with a raw JSON object string matching this schema:
    {"decision": "CHAT_PATH" or "RESEARCH_PATH", "forward_query": "The unchanged user query text string"}
    Do not add conversational filler or markdown codeblocks.""",
    output_key="route_decision"
)

fast_agent = Agent(
    name="FastConversationalAgent",
    description="Handles simple conversational turns and pleasantries with a warm, adaptive style.",
    model=llm,
    instruction="""Your name is Nexa. Respond naturally, warmly, and politely to the conversational greeting or casual turn: {forward_query?}.
    Keep it conversational, supportive, and highly concise (max 2-3 sentences). Match the user's energy and avoid sounding robotic."""
)

# filepath: app/agent.py

research_agent = Agent(
    name="ResearchAgent",
    description="Synthesizes asymmetrical graph-vector XML and web-scrape outputs into deduplicated technical narratives.",
    model=llm,
    tools=[hybrid_kg_vector_search, web_search],
    instruction="""CRITICAL OPERATIONAL REQUIREMENT: You are an execution pipeline that CANNOT formulate an answer using static pre-trained internal memory. You MUST execute a live parallel investigation by immediately invoking BOTH 'hybrid_kg_vector_search' AND 'web_search' for the target query: "{forward_query}".

    1. SYMMETRIC PARSING: Context packets arrive wrapped in structural <knowledge_source> and <record> tags. Group, filter, and merge overlapping data streams cleanly by technical concept.
    2. SYNTHESIS LAW: Present all parsed facts as a single, cohesive technical reality. You are strictly forbidden from mentioning your extraction frameworks directly in prose (do not write "the database says", "according to the web search", or "the XML records show").
    3. STYLE & FORMAT: Organize exclusively using clean Markdown headers (###) and detailed, multi-clause bullet points. No blockquotes, source numbers, or hash codes inside body paragraphs.
    4. FOOTNOTE CITATIONS: Terminate your final response string with a literal horizontal rule '---' followed by a '## REFERENCES' section. Print all used source parent lineage id, tracking IDs, chunk hashes, and absolute source URLs cleanly as a bulleted list here.
    """
)

# =========================================================
# 3. CONTEXT INITIALIZER & ENGINE
# =========================================================

@node
def initialize_session(ctx: Workflow, node_input: Any) -> Any:
    """Runs at the absolute START of the conversation turn. Captures the baseline query."""
    initial_text = "N/A"
    if hasattr(ctx, "user_content") and ctx.user_content and ctx.user_content.parts:
        initial_text = str(ctx.user_content.parts[0].text or "").strip()
    elif hasattr(node_input, "text"):
        initial_text = str(node_input.text).strip()
        
    ctx.state["raw_user_query"] = initial_text
    return node_input

@node
def control_engine(ctx: Workflow, node_input: Any) -> Event:
    """Decodes JSON router tokens and routes execution paths explicitly."""
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

# =========================================================
# 4. WORKFLOW TOPOLOGY DEFINITION
# =========================================================
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