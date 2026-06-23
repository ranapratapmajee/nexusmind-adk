# filepath: config/settings.py
import os
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Define the absolute target directory mapping for the .env file
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

# ⚡ CRITICAL FIX: Explicitly push .env variables into os.environ 
# right here so the Google GenAI core SDK can see them during module imports.
load_dotenv(dotenv_path=ENV_PATH)

class Settings(BaseSettings):
    
    # --- Orchestration Switch ---
    EXECUTION_MODE: str = Field("LOCAL", env="EXECUTION_MODE") # Default to LOCAL if missing

    # --- Model Infrastructure Configurations ---
    GOOGLE_API_KEY: str = Field(..., env="GOOGLE_API_KEY")
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
        env_file = ENV_PATH
        env_file_encoding = "utf-8"
        extra = "ignore"

# Global configuration instance singleton
settings = Settings()