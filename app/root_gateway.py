# filepath: app/root_gateway.py
import logging
from typing import Any
from config.settings import settings
from google.adk import Agent, Workflow, Event 
from google.adk.models.lite_llm import LiteLlm
from app.research_pipeline import deep_research_workflow

logger = logging.getLogger(__name__)

# ⚡ KEEP LOCAL: Root gateway initialized cleanly via your local model handle
llm = LiteLlm(model=settings.OLLAMA_MODEL)

# Dictionary scoped to the active execution turn to keep state isolated
_turn_cache = {}

# =========================================================
# 1. INTERCEPTOR & DETERMINISTIC SWITCHER
# =========================================================

def capture_active_input(node_input: Any, invocation_context: Any = None) -> Any:
    """
    Runs immediately at START. Intercepts and caches the current turn's
    exact string payload, isolating it from history bleeding.
    """
    global _turn_cache
    raw_text = getattr(node_input, "text", str(node_input)).strip()
    _turn_cache["current_query"] = raw_text
    
    # Pass the input cleanly forward to the router agent
    return node_input

def determine_workflow_path(node_input: Any, invocation_context: Any = None) -> Event:
    """
    Evaluates the router's intent classification decision string.
    Pulls the strictly isolated text captured at the beginning of this specific turn.
    """
    decision = getattr(node_input, "text", str(node_input)).strip().upper()
    
    # Retrieve the cached message string for the active turn
    raw_user_query = _turn_cache.get("current_query", "hi")

    logger.info(f"🔮 Router Classification: '{decision}' | Forwarding Raw Input: '{raw_user_query}'")

    # Defensive fallback parsing to handle potential model string leaking variations
    if "RESEARCH" in decision:
        return Event(route="RESEARCH_PATH", output=raw_user_query)
        
    return Event(route="CHAT_PATH", output=raw_user_query)

# =========================================================
# 2. AGENTS & HIGH-DENSITY INSTRUCTIONS
# =========================================================

router_agent = Agent(
    name="RouterAgent",
    model=llm,
    description="Traffic router directing queries to casual chat or deep research based on raw user text.",
    instruction="""
    ROLE: High-Precision Intent Classification Router.
    
    TASK: Analyze the incoming raw user message text and evaluate whether it requires a factual deep-dive research pipeline or a fast conversational greeting reaction.
    
    INTENT ROUTING SIGNATURES:
    
    1. RESEARCH (Technical / Analytical / Informational):
       - Trigger this intent if the user is asking a direct question, asking for definitions, seeking an explanation of a concept, or exploring structural data patterns.
       - Linguistic Patterns: "what is...", "how does...", "explain...", "define...", "why is...", "ML", "RAG", "Python", "code", "database".
       - Example Inputs: "what is ML", "explain RAG systems", "how do vectors work", "tell me about neural networks".
    
    2. CASUAL_CHAT (Greetings / Social / Polite Closures):
       - Trigger this intent if the user's message is a greeting, a brief social sign-off, an expression of gratitude, or generic small talk that does not ask for information or technical data.
       - Linguistic Patterns: "hi", "hello", "hey", "good morning", "thanks", "thank you", "bye", "how are you", "who are you".
       - Example Inputs: "hi", "hey there", "thanks for the help!", "hello nexa".
    
    STRICT OPERATIONAL CONTROLS:
    - Respond with EXACTLY one uppercase token string: either 'RESEARCH' or 'CASUAL_CHAT'.
    - Do NOT include any introductory phrases, explanatory text, punctuation marks, or metadata.
    - Do NOT wrap the output token inside markdown styling code blocks (e.g., do not write ```text).
    """,
    mode="single_turn"
)

fast_agent = Agent(
    name="FastConversationalAgent",
    model=llm,
    description="Lightweight handler for casual greetings.",
    instruction="""
    ROLE: Nexa, an approachable, highly authentic AI collaborator.
    
    TASK: Generate brief, warm, natural, and helpful reactions to user greetings, small talk, or polite sign-offs.
    
    STRICT OPERATIONAL CONTROLS:
    1. CONCISENESS GUARDRAIL: Limit your entire response to a maximum of 2 sentences. Keep it punchy and welcoming.
    2. CONTENT ISOLATION: Do NOT answer technical questions or offer deep factual breakdowns here. If the input contains a subtle technical question, rely on the router to have handled it; your job here is strictly social harmony.
    3. NO INTERACTION LITTER: Do NOT append systemic task lists, options menus, internal classification tokens, or generic interactive questions (e.g., do NOT write "How can I assist your deep research journey today?").
    4. NO填充 TEXT: Start directly with the conversational message string.
    """,
    mode="single_turn"
)

# =========================================================
# 3. SECURE STATELESS TOPOLOGY
# =========================================================

root_agent = Workflow(
    name="RootAgentWorkflow",
    edges=[
        # 1. Capture the fresh incoming user message immediately at START
        ("START", capture_active_input),
        
        # 2. Pass that fresh captured input down into the intent router agent
        (capture_active_input, router_agent),
        
        # 3. Feed the router's categorization word token into our mapping switcher
        (router_agent, determine_workflow_path),
        
        # 4. Route to the correct subgraph along with the original raw text string
        (determine_workflow_path, {
            "CHAT_PATH": fast_agent,      
            "RESEARCH_PATH": deep_research_workflow
        })
    ]
)