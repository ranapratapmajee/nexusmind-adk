# filepath: app/core/control_engine.py
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ControlEngine:
    """Analyzes safe inputs to determine structural execution pathways."""
    
    @staticmethod
    def evaluate_routing(query_text: str) -> Dict[str, Any]:
        # Direct structural check for the PDF text payload signature
        if "DOCUMENT_INJECT_STREAM:" in query_text:
            logger.info("📁 Explicit document inject stream signature detected. Routing to Ingestion Pipeline.")
            return {"intent": "INGESTION_UPLOAD", "complexity": "STANDARD"}

        lowered_query = query_text.lower()
        
        # Rule-based orchestration matching the matrix definitions
        if any(g in lowered_query for g in ["hello", "hi", "hey", "who are you"]):
            return {"intent": "CASUAL_CHAT", "complexity": "STANDARD"}
        elif any(i in lowered_query for i in ["upload", "file", "ingest", "index"]):
            return {"intent": "INGESTION_UPLOAD", "complexity": "STANDARD"}
        else:
            # Complex research reasoning defaults
            complexity = "EXTREME" if len(query_text) > 100 or "compare" in lowered_query else "STANDARD"
            return {"intent": "RESEARCH", "complexity": complexity}

control_engine = ControlEngine()