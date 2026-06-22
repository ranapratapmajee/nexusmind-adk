# filepath: app/agents/router_agent.py
from google.adk.agents import LlmAgent
from config.settings import settings
from app.models.chat_state import RouterResponse

router_agent = LlmAgent(
    name="ControlEngineRouter",
    model=settings.OLLAMA_MODEL,
    description="Orchestration router evaluating transactional intentions and model tiers.",
    instruction="""
    Analyze the user's incoming transaction string and map it to a deliberate path:
    1. 'CASUAL_CHAT': Standard conversational conversational statements, jokes, greetings, or clarifications.
    2. 'INGESTION_UPLOAD': Text containing document streams, file drops, raw data dumps, indexing logs, or lines starting with 'DOCUMENT_INJECT_STREAM:'.
    3. 'RESEARCH': Analytical requests needing concrete data lookup, multi-database lookups, or system comparisons.
    
    SPECIAL RULE: If the input contains the explicit marker 'DOCUMENT_INJECT_STREAM:', you MUST classify the intent as 'INGESTION_UPLOAD' and set complexity to 'STANDARD'.
    
    Score complexity as 'EXTREME' if processing requires deep reasoning, multi-turn comparisons, or complex structural dependencies. Otherwise, set as 'STANDARD'.
    """,
    output_schema=RouterResponse
)