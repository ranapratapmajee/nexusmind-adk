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

# =========================================================
# 1. STRUCTURAL GLOBAL STATE SCHEMA (ADK 2.0 WORKFLOW STATE)
# =========================================================
class AgentState(BaseModel):
    user_query: str = Field(default="", description="The clean string primitive question.")
    route_decision: str = Field(default="", description="The JSON string token produced by the router.")

# =========================================================
# 2. DEFINITION OF REFINED COHESIVE SYSTEM AGENTS (NODES)
# =========================================================

router_agent = Agent(
    name="RouterAgent",
    description="Dynamically classifies user intent and bundles output as a clean JSON payload structure.",
    model=llm,
    instruction="""Analyze the user prompt. You must classify the intent and respond with a strict raw JSON object string matching this exact schema:
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
    instruction="Respond warmly and politely to the user greeting: {user_query?}. Keep your answer friendly and concise (max 2 sentences)."
)

research_agent = Agent(
    name="ResearchAgent",
    description="Executes tools directly and synthesizes data into an exhaustive, multi-point technical summary with clean, isolated references.",
    model=llm,
    instruction="""
    ROLE: Senior Technical Research Systems Architect.
    
    TARGET GOAL: Provide a deeply comprehensive, highly detailed response to the active inquiry: "{user_query}"
    
    TASK: You must call your attached retrieval tools. You are required to fully extract, synthesize, and expand upon the technical insights returned by BOTH your internal knowledge records and your live web scrapers.

    ⚙️ EXHAUSTIVE DATA HARVESTING LAWS:
    1. READ ALL TOOL SEGMENTS: Inspect every single data payload block from your tools. Do not stop reading after the first record.
    2. RESOLVE DEDUPLICATED GRAPH CONTEXTS: If a chunk contains the label '[OMITTED DUP - SEE ABOVE FOR CONTEXT]', you must look back up at the previously printed 'Full Parent Context' block and explicitly extract its details to support the current matching fact.
    3. MAXIMIZE CONTENT DEPTH: You are strictly forbidden from writing a short summary. Aim to produce at least 6 to 10 highly granular, technically dense, informative bullet points expanding on definitions, architectural hidden layers, components, and statistical rules.

    🔒 COMPLIANCE & STYLING LAWS:
    1. RENDER FLAT BULLETS ONLY: Your entire response must consist solely of standard, plain bullet points. You are completely restricted from using Markdown headers (such as #, ##, or ###), bold section dividers, asterisks lines, or blockquotes.
    2. ZERO INLINE LEAKAGE: Keep the informational bullet points completely clean. You must not include any brackets, citation keys, chunk hashes, or URLs within the technical body sentences.
    3. START IMMEDIATELY: Begin your output directly with the first technical fact. Do not use filler introductions or mention your tool workflows.
    4. SYSTEM FOOTER REFERENCES: Conclude the flat list by dedicating the final bullet points strictly to mapping data origins using these exact literal formats:
       - REFERENCES - Source Parent ID: [Insert all unique parent hashes found]
       - REFERENCES - Source Website URL: [Insert all clean scraped domain links found]
    """,
    tools=[graph_rag_retrieval, web_search]
)

# =========================================================
# 3. CONTEXT INITIALIZER & ENGINE
# =========================================================
@node
def initialize_session(ctx: Workflow, node_input: Any) -> Any:
    """
    Runs at the absolute START of the conversation turn. Safely reads the original 
    user text from the framework context without bleeding object tracking wrappers.
    """
    initial_text = "N/A"
    if hasattr(ctx, "user_content") and ctx.user_content and ctx.user_content.parts:
        initial_text = str(ctx.user_content.parts[0].text or "").strip()
    elif hasattr(node_input, "text"):
        initial_text = str(node_input.text).strip()
        
    ctx.state["user_query"] = initial_text
    return node_input

@node
def control_engine(ctx: Workflow, node_input: Any) -> Event:
    """
    ADK 2.0 Compliant Engine. Decodes the LLM's structured JSON payload, updates the state 
    variables, and issues a pure routing Event. The graph engine handles message-passing 
    and target token injection natively via the state schema mapping fields.
    """
    raw_payload_str = str(ctx.state.get("route_decision", "")).strip()
    
    decision_path = "RESEARCH_PATH"
    clean_query = str(ctx.state.get("user_query", "")).strip()

    # Normalize response variations if the 7B model uses string markdown formatting blocks
    if raw_payload_str.startswith("```"):
        raw_payload_str = raw_payload_str.strip("`").replace("json", "", 1).strip()

    try:
        parsed_payload = json.loads(raw_payload_str)
        decision_path = str(parsed_payload.get("decision", "RESEARCH_PATH")).strip().upper()
        extracted_query = str(parsed_payload.get("forward_query", "")).strip()
        if extracted_query:
            clean_query = extracted_query
    except Exception:
        # Strict token matching fallback in case of JSON syntax anomalies
        if "CHAT_PATH" in raw_payload_str:
            decision_path = "CHAT_PATH"

    # Save the sanitized text parameter back to our tracking schema state block
    ctx.state["user_query"] = clean_query

    # ⚡ ADK 2.0 ENGINE SPECIFICATION COMPLIANCE:
    # We drop manual text= parameters. The 2.0 router engine will orchestrate 
    # the target execution nodes, while tracking graph state histories natively via state_schema.
    if "CHAT_PATH" in decision_path:
        return Event(route="ROUTE_TO_CHAT", actions={"transfer_to_agent": "FastConversationalAgent"})
    
    return Event(route="ROUTE_TO_RESEARCH", actions={"transfer_to_agent": "ResearchAgent"})

# =========================================================
# 4. STREAMLINED GRAPH TOPOLOGY
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