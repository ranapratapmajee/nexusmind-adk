# filepath: app/core/llm_router.py
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class LlmRouter:
    """Dynamically monitors context length and allocates hardware tiers."""
    
    @staticmethod
    def select_target_model(context_string: str, force_premium: bool = False) -> str:
        # Approximate token count via character heuristic
        estimated_tokens = len(context_string) / 4
        
        if estimated_tokens > 100000 or force_premium:
            logger.info(f"🚀 Context length ({estimated_tokens} tokens) exceeds local limits. Escalating to Cloud Gemini.")
            return settings.GEMINI_MODEL
            
        logger.info(f"⚡ Context length ({estimated_tokens} tokens) within boundaries. Utilizing local Ollama.")
        return settings.OLLAMA_MODEL

llm_router = LlmRouter()