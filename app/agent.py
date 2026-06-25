# filepath: app/agent.py

from typing import Any
from pydantic import BaseModel, Field
from config.settings import settings
from google.adk import Agent, Workflow, Event
from google.adk.workflow import START, node
from google.adk.models.lite_llm import LiteLlm
from app.tools import graph_rag_retrieval, web_search

local_llm = LiteLlm(model=settings.OLLAMA_MODEL)
cloud_llm = settings.GEMINI_MODEL
llm= local_llm

# =========================================================
# 1. STRUCTURAL GLOBAL STATE SCHEMA
# =========================================================
class AgentState(BaseModel):
    user_query: str = Field(default="", description="The original raw text query submitted by the user.")
    route_decision: str = Field(default="", description="The raw routing classification string produced by the LLM.")

# =========================================================
# 2. DEFINITION OF REFINED COHESIVE SYSTEM AGENTS (NODES)
# =========================================================

router_agent = Agent(
    name="RouterAgent",
    description="Dynamically classifies whether the incoming user input is a casual greeting or a research question.",
    model=llm,
    instruction="""Analyze the user prompt. Determine the intent and respond with EXACTLY one word:
    - CHAT_PATH: if the user is saying hi, hello, greeting you, or making casual pleasantries.
    - RESEARCH_PATH: if the user is asking an informational, technical, or analytical question.
    Do not add markdown formatting, commentary, quotes, or periods. Output ONLY the word.""",
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
    description="Executes tools directly and synthesizes data into a highly comprehensive plain bulleted report with isolated references.",
    model=llm,
    instruction="""
    ROLE: Expert Technical Research Synthesizer. 
    
    TARGET GOAL: Exhaustively answer the user's core query string.
    
    TASK: You must call your attached tools to gather data, then combine the full text payloads from BOTH your internal knowledge base logs and your live web scraping search paths to build a comprehensive summary. Do not miss any details.

    ⚙️ MANDATORY INGESTION LAWS:
    1. Extract all definitions, structures, and statistical rules present in your tool results. 
    2. Isolate specific technical deep learning definitions, structural layers (hidden networks, neurons), active network architectures (CNN, RNN, LSTM, Transformers, GANs), and core structural comparisons between Machine Learning vs Deep Learning.
    3. Maximize informational density. Ensure your output contains multiple detailed bullet points explaining these architectures comprehensively.

    🔒 STYLING GUIDELINES:
    1. Output your entire response using ONLY plain bullet points. DO NOT use any Markdown headers (like # or ##), bold text section dividers, asterisks for sections, or blockquotes.
    2. Start directly with the bulleted findings. DO NOT include introductory text, meta-commentary, or call out function parameter objects.
    3. KEEP INLINE FACTS CLEAN: Do not place brackets, citation tags, or raw string URLs inside the core body bullet points. Keep the sentences clean.
    4. REFERENCES SECTION: Conclude your response with explicit bullet points labeled exactly as 'REFERENCES - Source Parent ID:' and 'REFERENCES - Source Website URL:' to cleanly isolate all chunk hashes and domain strings collected at the very bottom.
    """,
    tools=[graph_rag_retrieval, web_search]
)

# =========================================================
# 3. CONTEXT INITIALIZER & ENGINE
# =========================================================
@node
def initialize_session(ctx: Workflow, node_input: Any) -> Any:
    """
    Runs at the absolute START of the conversation turn. Strips out wrapper meta-objects 
    to extract a clean string primitive for the target query state.
    """
    if hasattr(node_input, "text"):
        raw_text = str(node_input.text).strip()
    elif isinstance(node_input, dict) and "text" in node_input:
        raw_text = str(node_input["text"]).strip()
    else:
        raw_text = str(node_input).strip()
        
    ctx.state["user_query"] = raw_text
    return raw_text

@node
def control_engine(ctx: Workflow, node_input: Any) -> Event:
    """
    Evaluates the string token produced dynamically by the RouterAgent and handles branching control flow.
    Enforces a clean string extraction right before passing control to prevent object bleeding.
    """
    llm_decision = str(node_input).strip().upper()
    
    # 🧼 CRITICAL FIX: Extract the pristine string primitive from our state cache
    clean_query_string = str(ctx.state.get("user_query", "")).strip()

    if "CHAT_PATH" in llm_decision:
        return Event(route="ROUTE_TO_CHAT", actions={"transfer_to_agent": "FastConversationalAgent"}, text=clean_query_string)
    
    return Event(route="ROUTE_TO_RESEARCH", actions={"transfer_to_agent": "ResearchAgent"}, text=clean_query_string)

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