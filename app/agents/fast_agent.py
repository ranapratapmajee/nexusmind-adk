# filepath: app/agents/fast_agent.py
from google.adk.agents import LlmAgent
from config.settings import settings

fast_agent = LlmAgent(
    name="FastConversationalAgent",
    model=settings.OLLAMA_MODEL,
    description="Lightweight chatbot node handling basic conversation and simple text turns.",
    instruction="""
    You are Nexa, a highly engaging and responsive conversational teammate within the NexusMind platform.
    Respond to the user naturally, clearly, and concisely. Keep an approachable, peer-like tone.
    """
)