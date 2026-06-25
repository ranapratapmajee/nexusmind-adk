# filepath: app/services.py
import io
import logging
from typing import List, Dict, Any
import requests
from pypdf import PdfReader
from chromadb import HttpClient
from neo4j import GraphDatabase
from config.settings import settings

logger = logging.getLogger(__name__)

# =========================================================
# 1. HIERARCHICAL TEXT EXTRACTION ENGINE
# =========================================================

class PDFProcessorService:
    """Handles text extraction and standardized hierarchical chunking of binary data streams."""
    
    @staticmethod
    def extract_clean_text(file_bytes: bytes) -> str:
        """Reads raw bytes using pypdf to consolidate page paragraphs into a single text block."""
        try:
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() for page in pdf_reader.pages if page.extract_text()]
            return "\n\n".join(pages)
        except Exception as e:
            logger.error(f"Failed to read PDF stream: {str(e)}")
            raise RuntimeError(f"PDF extraction failure: {str(e)}")

    @staticmethod
    def slice_hierarchical_chunks(text: str, document_name: str, parent_size: int = 2000, child_size: int = 400, overlap: int = 100) -> List[Dict[str, Any]]:
        """
        Slices text into paired parent and child chunks using a standardized string 
        identification convention to match Chroma and Neo4j keys cleanly.
        """
        logger.info(f"Slicing document context: {document_name}")
        hierarchical_map = []
        
        start_idx = 0
        parent_idx = 1
        child_idx = 1
        
        # Build clean uppercase prefix token for standardized lookup keys (e.g., "REPORT")
        base_doc_name = document_name.split(".")[0].upper()
        
        while start_idx < len(text):
            end_idx = min(start_idx + parent_size, len(text))
            parent_chunk = text[start_idx:end_idx].strip()
            
            if parent_chunk:
                parent_id = f"{base_doc_name}-PARENT-{parent_idx:03d}"
                child_records = []
                
                child_start = 0
                while child_start < len(parent_chunk):
                    child_end = min(child_start + child_size, len(parent_chunk))
                    child_text = parent_chunk[child_start:child_end].strip()
                    
                    if child_text:
                        child_id = f"{base_doc_name}-CHUNK-{child_idx:03d}"
                        child_records.append({
                            "id": child_id,
                            "text": child_text
                        })
                        child_idx += 1
                        
                    child_start += (child_size - overlap)
                    if child_end == len(parent_chunk):
                        break
                        
                hierarchical_map.append({
                    "parent_id": parent_id,
                    "parent_text": parent_chunk,
                    "children": child_records
                })
                parent_idx += 1
                
            start_idx += parent_size
            
        return hierarchical_map


# =========================================================
# 2. CHROMA VECTOR STORAGE ENGINE
# =========================================================

class VectorStoreService:
    """Manages persistent HTTP vector collection connections and local embedding hooks."""
    
    def __init__(self):
        self.client = HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.embedding_url = f"{settings.LOCAL_LLM_URL}/api/embeddings"
        self.model_name = settings.EMBEDDING_MODEL
        
    def _generate_embedding(self, text_content: str) -> List[float]:
        """Queries local Ollama endpoint to return dense vector representations."""
        try:
            resp = requests.post(
                self.embedding_url, 
                json={"model": self.model_name, "prompt": text_content}, 
                timeout=15
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Dense vector embedding generation failure: {str(e)}")
            raise RuntimeError(f"Vector embedding failure: {str(e)}")

    def get_or_create_collection(self, collection_name: str = "nexus_knowledge_pool"):
        """Returns targeted HTTP collection instance."""
        return self.client.get_or_create_collection(name=collection_name)

    def insert_child_vector(self, child_id: str, child_text: str, parent_id: str):
        """Commits standard child vector with explicit parent reference metadata."""
        collection = self.get_or_create_collection()
        embedding = self._generate_embedding(child_text)
        
        collection.add(
            ids=[child_id],
            embeddings=[embedding],
            metadatas=[{"parent_id": parent_id}],
            documents=[child_text]
        )
        logger.info(f"✅ Chroma Vector Registered: {child_id}")


# =========================================================
# 3. NEO4J GRAPH DATABASE ENGINE
# =========================================================

class GraphDBService:
    """Manages transactional schema optimizations and hierarchical graph edge structures."""
    
    def __init__(self):
        self._driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self._initialize_constraints()

    def close(self):
        """Gracefully shuts down driver pools."""
        self._driver.close()

    def _initialize_constraints(self):
        """Creates unique constraints automatically on core node primitives."""
        query = "CREATE CONSTRAINT unique_doc_node_id IF NOT EXISTS FOR (d:DocumentNode) REQUIRE d.id IS UNIQUE;"
        try:
            with self._driver.session() as session:
                session.run(query)
                logger.info("📐 Verified unique identity constraints on graph schema fields.")
        except Exception as e:
            logger.warning(f"Could not apply structural constraints automatically: {str(e)}")

    def save_hierarchical_edge(self, child_id: str, parent_id: str, parent_text: str):
        """Natively maps a Child chunk to its Parent context frame in Neo4j."""
        cypher_query = """
        MERGE (c:DocumentNode {id: $child_id})
        SET c.type = 'ChildChunk'
        WITH c
        MERGE (p:DocumentNode {id: $parent_id})
        SET p.type = 'ParentChunk', p.text = $parent_text
        WITH c, p
        MERGE (c)-[:CHILD_OF]->(p);
        """
        try:
            with self._driver.session() as session:
                session.run(cypher_query, child_id=child_id, parent_id=parent_id, parent_text=parent_text)
        except Exception as e:
            logger.error(f"Neo4j write transaction crashed: {str(e)}")
            raise e

    def save_concept_mention(self, entity_name: str, entity_type: str, chunk_id: str):
        """
        Binds extracted conceptual entity nodes directly to a standardized child chunk.
        Enables Layer-2 expansions completely decoupled from document geometry.
        """
        safe_label = "".join([c for c in entity_type if c.isalnum()]).upper()
        clean_entity_id = entity_name.strip().upper()

        cypher_query = f"""
        MERGE (e:{safe_label} {{id: $entity_id}})
        WITH e
        MATCH (c:DocumentNode {{id: $chunk_id}})
        MERGE (e)-[:MENTIONED_IN]->(c);
        """
        try:
            with self._driver.session() as session:
                session.run(cypher_query, entity_id=clean_entity_id, chunk_id=chunk_id)
        except Exception as e:
            logger.error(f"Neo4j concept linkage failure: {str(e)}")


# =========================================================
# GLOBAL SINGLETON INSTANTIATION EXPORTS
# =========================================================

pdf_processor = PDFProcessorService()
vector_store = VectorStoreService()
graph_db = GraphDBService()
