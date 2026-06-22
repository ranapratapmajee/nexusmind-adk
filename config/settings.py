# filepath: config/settings.py
import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # --- Model Infrastructure Configurations ---
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    LOCAL_LLM_URL: str = Field(..., env="LOCAL_LLM_URL")
    
    # Provider-Specific Model Selections
    OLLAMA_MODEL: str = Field(..., env="OLLAMA_MODEL")
    GEMINI_MODEL: str = Field(..., env="GEMINI_MODEL")

    # --- Core Database Cluster Topology ---
    # Vector Engine Links (Chroma DB)
    CHROMA_HOST: str = Field("localhost", env="CHROMA_HOST")
    CHROMA_PORT: int = Field(8000, env="CHROMA_PORT")
    
    # Relational Entity Engine Links (Neo4j Graph)
    NEO4J_URI: str = Field("bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field("neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field("password", env="NEO4J_PASSWORD")

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

# Global configuration instance singleton
settings = Settings()