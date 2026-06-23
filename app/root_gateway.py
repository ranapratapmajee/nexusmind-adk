import logging
from typing import Any
from config.settings import settings
from google.adk import Agent, Workflow, Event 
from google.adk.models.lite_llm import LiteLlm
from app.research_pipeline import deep_research_subgraph

logger = logging.getLogger(__name__)

# Initialize configurations
llm = LiteLlm(model=settings.OLLAMA_MODEL)

# =========================================================
# 1. AGENTS & INSTRUCTIONS (REWORKED FOR LOCAL LLMs)
# =========================================================

root_gate_node = Agent(
    name="RootAgent",  
    model=llm,
    description="Context rewriter optimizing multi-turn history into standalone queries.",
    instruction="""
    ROLE: Standalone Query Builder.
    TASK: Look at the conversation history and turn the latest input into a single standalone question for next agent or pipelines.
    
    CRITICAL RULES:
    1. Do NOT answer the question.
    2. Do NOT write conversational filler (e.g., "Sure, here it is:").
    3. Output ONLY the clear, rewritten question string.
    
    EXAMPLES:
    User: what is RAG
    Output: What is Retrieval-Augmented Generation?
    
    User: hey there
    Output: hey there
    """,
    mode="single_turn" 
)

router_agent = Agent(
    name="ControlEngineRouter",
    model=llm,
    description="Traffic router directing queries to casual chat or deep research.",
    instruction="""
    ROLE: Intent Classifier.
    TASK: Classify the input text into exactly ONE of these two categories.
    
    CATEGORIES:
    - RESEARCH: Technical acronyms (RAG, LLM, DB), programming, or explanatory questions.
    - CASUAL_CHAT: Simple greetings, casual talk, or pleasantries.
    
    CRITICAL RULES:
    1. Output EXACTLY the uppercase keyword token. No punctuation, no markdown blocks.
    2. Output ONLY the word 'RESEARCH' or the word 'CASUAL_CHAT'.
    
    EXAMPLES:
    Input: What is Retrieval-Augmented Generation?
    Output: RESEARCH
    
    Input: hello
    Output: CASUAL_CHAT
    """,
    mode="single_turn"
)

fast_agent = Agent(
    name="FastConversationalAgent",
    model=llm,
    description="Lightweight handler for casual greetings.",
    instruction="""
    ROLE: Nexa, an approachable AI collaborator.
    TASK: Respond to greetings and casual chit-chat briefly, clearly, and warmly.
    Never append menus, interactive feature options, or conversational lists.
    """,
    mode="single_turn"
)

# =========================================================
# 2. GRAPH ROUTING & STATE CONTROLLERS
# =========================================================

def capture_and_forward_query(node_input: Any, invocation_context: Any = None) -> str:
    """Interceptor that saves the RootAgent standalone query to context state before routing."""
    query_text = getattr(node_input, "text", str(node_input)).strip()
    logger.info(f"💾 Root Gateway State Saved: '{query_text}'")
    
    if invocation_context and hasattr(invocation_context, "state"):
        invocation_context.state["resolved_query"] = query_text
        
    return query_text

def determine_workflow_path(node_input: Any, invocation_context: Any = None) -> Event:
    """Evaluates the classification token and directly assigns the captured query text."""
    decision = getattr(node_input, "text", str(node_input)).strip().upper()
    logger.info(f"🔮 Native Router Selection: '{decision}'")
    
    # Explicitly pull our custom isolated state payload 
    user_query = ""
    if invocation_context and hasattr(invocation_context, "state"):
        user_query = invocation_context.state.get("resolved_query", "")
        
    # Strict validation boundary to shield your pipeline from token confusion
    if not user_query or user_query.upper() in ["RESEARCH", "CASUAL_CHAT"]:
        user_query = str(node_input)

    if "RESEARCH" in decision:
        # Securely forward the clean, text-based query payload down into the research pipeline
        return Event(route="RESEARCH_PATH", output=user_query)
        
    return Event(route="CHAT_PATH", output=user_query)

# =========================================================
# 3. CLEAN WORKFLOW TOPOLOGY
# =========================================================

root_agent = Workflow(
    name="SystemRootGateway",
    edges=[
        # Entry Phase & State Capture
        ("START", root_gate_node),
        (root_gate_node, capture_and_forward_query),
        (capture_and_forward_query, router_agent),
        
        # Branch Evaluation Phase
        (router_agent, determine_workflow_path),
        (determine_workflow_path, {
            "CHAT_PATH": fast_agent,      
            "RESEARCH_PATH": deep_research_subgraph  
        })
    ]
)