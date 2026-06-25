# filepath: app/agent.py
import logging
from typing import Any, Optional
from config.settings import settings
from google.adk import Agent, Workflow, Event 
from google.adk.models.lite_llm import LiteLlm

# Import external system tools
from app.tools import graph_rag_retrieval, web_search

logger = logging.getLogger(__name__)

# Initialize local LLMs using project configurations
llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. ⚡ BULLETPROOF INLINE ROUTER NODE
# =========================================================

def inline_router_node(node_input: Any, invocation_context: Any = None) -> Event:
    """
    Safely processes GenAI content streams, decides the path via LLM evaluation,
    and cleanly forwards the user's query into the workflow context.
    """
    # 1. Properly extract string from google.genai.types.Content or standard formats
    if hasattr(node_input, "parts") and node_input.parts:
        user_query = node_input.parts[0].text
    elif hasattr(node_input, "text"):
        user_query = node_input.text
    elif isinstance(node_input, dict) and "text" in node_input:
        user_query = node_input["text"]
    else:
        user_query = str(node_input)

    user_query = user_query.strip()
    logger.info(f"📥 Inline Router received clean query: '{user_query}'")

    # 2. Local evaluation check to bypass LLM classification variance for basic greetings
    clean_check = user_query.lower().strip("?.!,")
    greetings = {"hi", "hello", "hey", "sup", "yo", "greetings", "thanks", "thank you"}
    
    if clean_check in greetings:
        logger.info("🎯 Quick Match: Routing to CHAT_PATH")
        return Event(route="CHAT_PATH", text=user_query, query=user_query)

    # 3. Request classification routing directly from the model
    prompt = f"""You are a strict network router agent. Your only job is to categorize the user query into one of two paths.

[CATEGORIES]
- CHAT_PATH: Choose this for general greetings, casual small talk, pleasantries, or simple chitchat.
- RESEARCH_PATH: Choose this for informational questions, technical queries, data lookups, code requests, or complex explanations.

[RULES]
- Respond with EXACTLY one of the two keywords: CHAT_PATH or RESEARCH_PATH.
- Do NOT include any punctuation, introduction, quotes, or explanation.

User Query: {user_query}
Route Decision:"""
    
    try:
        raw_decision = llm.predict(prompt).strip().upper()
        decision = raw_decision.replace('"', '').replace("'", "").replace(".", "")
    except Exception as e:
        logger.error(f"Router LLM failed: {e}. Defaulting to RESEARCH_PATH.")
        decision = "RESEARCH_PATH"

    logger.info(f"🧠 Router decision: '{decision}'")

    # Determine chosen route destination
    chosen_route = "CHAT_PATH" if "CHAT_PATH" in decision else "RESEARCH_PATH"
    
    # Passing both 'text' and 'query' payload arguments maps perfectly to sub-graph inputs
    return Event(route=chosen_route, text=user_query, query=user_query)

# =========================================================
# 2. AGENTS
# =========================================================

fast_agent = Agent(
    name="FastConversationalAgent",
    model=llm,
    instruction="""
    ROLE: Nexa, a friendly AI collaborator.
    TASK: Generate a brief response to the user's greeting.
    GUARDRAILS: Maximum 2 sentences. No technical explanations. Start directly with the text response.
    """,
    mode="single_turn"
)

planner_agent = Agent(
    name="PlannerAgent",
    model=llm,
    instruction="""
    Analyze the incoming user question text.
    Extract the 2 or 3 most important keywords needed to search a database.
    If the input text does not have explicit technical keywords, just output the original text back.
    Output ONLY the raw keywords. Do not use JSON, notes, or punctuation.
    """,
    mode="single_turn"
)

retrieval_agent = Agent(
    name="RetrievalAgent",
    model=llm,
    instruction="""
    Gather data simultaneously using your tools:
    1. Pass the incoming search keywords into the 'query' argument of graph_rag_retrieval.
    2. Pass the exact same keywords into the 'query' argument of web_search.
    Combine both tool outputs into a single plain text response block.
    """,
    tools=[graph_rag_retrieval, web_search],
    mode="single_turn"
)

analytical_synthesis_agent = Agent(
    name="AnalyticalSynthesisAgent",
    model=llm,
    instruction="""
    Clean and group facts from the provided text payload.
    If no source facts are provided or the payload is empty, use your internal knowledge to answer.
    Write a step-by-step reasoning trail showing how findings align. Do not guess.
    """,
    mode="single_turn"
)

response_agent = Agent(
    name="ResponseAgent",
    model=llm, 
    instruction="""
    Generate the final Markdown answer based on the provided facts.
    Use clear headings and lists. Include inline source citations like [DOC-CHUNK-001] if applicable.
    Start directly with the answer text. No conversational filler or greetings.
    """,
    mode="single_turn"
)

# =========================================================
# 3. SUB-GRAPH WORKFLOW TOPOLOGY
# =========================================================

deep_research_workflow = Workflow(
    name="DeepResearchWorkflow",
    context_propagation=["query"],
    edges=[
        ("START", planner_agent),
        (planner_agent, retrieval_agent),
        (retrieval_agent, analytical_synthesis_agent),
        (analytical_synthesis_agent, response_agent)
    ]
)

# =========================================================
# 4. ROOT GRAPH TOPOLOGY REGISTRATION
# =========================================================

root_agent = Workflow(
    name="RootAgentWorkflow",
    context_propagation=["query"],
    edges=[
        ("START", inline_router_node),
        (inline_router_node, {
            "CHAT_PATH": fast_agent,      
            "RESEARCH_PATH": deep_research_workflow
        })
    ]
)