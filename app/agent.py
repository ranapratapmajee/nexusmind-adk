# filepath: app/agent.py

from typing import Any
from pydantic import BaseModel, Field
from config.settings import settings
from google.adk import Agent, Workflow, Event
from google.adk.workflow import START, node
from google.adk.models.lite_llm import LiteLlm
from app.tools import graph_rag_retrieval, web_search

llm = LiteLlm(model=settings.OLLAMA_MODEL)

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

retrieval_agent = Agent(
    name="RetrievalAgent",
    description="Extracts search terms from complex technical questions and runs parallel GraphRAG and Web search tools.",
    model=llm,
    instruction="""
    You are a Data Gathering Specialist. Your input is a raw user question: {user_query?}.
    
    CRITICAL STEPS:
    1. Break down the question into 2-3 specific search keywords or phrases.
    2. Execute the 'graph_rag_retrieval' and 'web_search' tools simultaneously using those keywords.
    3. Output the raw, combined information returned from both tools. Do not add any formatting or commentary.
    """,
    tools=[graph_rag_retrieval, web_search]
)

synthesis_agent = Agent(
    name="SynthesisAgent",
    description="Synthesizes raw parallel tool data into a cohesive, professional technical markdown report with citations.",
    model=llm,
    instruction="""
    You are an Expert Technical Research Synthesizer. 
    Take the raw tool results provided by the RetrievalAgent and draft a final response for the user.

    STRICT OUTPUT GUIDELINES:
    1. DO NOT mention the words 'tool', 'graph_rag_retrieval', 'web_search', or 'RetrievalAgent'.
    2. DO NOT include meta-commentary like "Sure, here is the information...". Start directly with the technical findings.
    3. Synthesize the findings into an authoritative answer, deduplicating overlapping facts.
    4. Format cleanly using structured Markdown headers, bullet points, and explicit numbered citations (e.g., [1], [2]).
    5. Conclude with a clear 'References' section linking the sources provided in the tool payload.
    """
)

# =========================================================
# 3. CONTEXT INITIALIZER & ENGINE
# =========================================================
@node
def initialize_session(ctx: Workflow, node_input: Any) -> Any:
    """
    Runs at the absolute START of the conversation turn. Caches the original user prompt in shared memory so it is safely accessible later, then passes it along to the RouterAgent unchanged.
    """
    raw_text = getattr(node_input, "text", str(node_input)).strip()
    ctx.state["user_query"] = raw_text
    return node_input

@node
def control_engine(ctx: Workflow, node_input: Any) -> Event:
    """
    Evaluates the string token produced dynamically by the RouterAgent and handles branching control flow without hardcoded text keywords.
    """
    # Grab the dynamic decision from the router agent payload output
    llm_decision = str(node_input).strip().upper()
    user_input = ctx.state.get("user_query", "")

    if "CHAT_PATH" in llm_decision:
        return Event(route="ROUTE_TO_CHAT", actions={"transfer_to_agent": "FastConversationalAgent"}, text=user_input)
    
    return Event(route="ROUTE_TO_RESEARCH", actions={"transfer_to_agent": "RetrievalAgent"}, text=user_input)

# =========================================================
# 4. STREAMLINED GRAPH TOPOLOGY
# =========================================================
root_agent = Workflow(
    name="RootAgentWorkflow",
    state_schema=AgentState,
    edges=[
        # Step 1: Capture user input and forward it straight to the Router Agent
        (START, initialize_session),
        (initialize_session, router_agent),
        
        # Step 2: Pass the Router's classification text directly into the control engine
        (router_agent, control_engine),
        
        # Step 3: Switchboard routes execution dynamically based on the engine's event evaluation
        (control_engine, {
            "ROUTE_TO_CHAT": fast_agent,
            "ROUTE_TO_RESEARCH": retrieval_agent
        }),
        
        # Step 4: Execute the Stage 2 research pipeline sequence if targeted
        (retrieval_agent, synthesis_agent)
    ]
)