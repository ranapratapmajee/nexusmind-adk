# filepath: app/infrastructure/chroma_service.py
import logging
import requests
from chromadb import HttpClient
from config.settings import settings

logger = logging.getLogger(__name__)

class ChromaService:
    """Manages persistent HTTP vector collection connections and local embedding hooks."""
    
    def __init__(self):
        self.client = HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.embedding_url = f"{settings.LOCAL_LLM_URL}/api/embeddings"
        self.model_name = "nomic-embed-text"  # Verified default embedding engine
        
    def _generate_embedding(self, text_content: str) -> list[float]:
        """Queries local Ollama endpoint to return dense vector representations."""
        try:
            response = requests.post(
                self.embedding_url,
                json={"model": self.model_name, "prompt": text_content},
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            logger.error(f"❌ Failed to extract dense embeddings from Ollama: {str(e)}")
            raise e

    def get_or_create_collection(self, collection_name: str = "nexus_knowledge_pool"):
        """Returns target collection handles from the running storage pool."""
        return self.client.get_or_create_collection(name=collection_name)

    def insert_chunk(self, chunk_text: str, document_name: str, chunk_index: int):
        """Vectorizes text fragments and commits them to the vector array index."""
        collection = self.get_or_create_collection()
        vector_embedding = self._generate_embedding(chunk_text)
        
        unique_id = f"{document_name}_chunk_{chunk_index}"
        collection.add(
            ids=[unique_id],
            embeddings=[vector_embedding],
            metadatas=[{"source_file": document_name, "position": chunk_index}],
            documents=[chunk_text]
        )
        logger.info(f"✅ Successfully registered embedding ID: {unique_id} to Chroma DB.")

chroma_service = ChromaService()