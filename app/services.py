# filepath: app/services.py
import io
import re
import logging
from typing import List, Dict, Any
import httpx  # 🟢 Upgraded from 'requests' to support true async connection pooling
import chromadb
from chromadb import HttpClient
from neo4j import GraphDatabase
from pypdf import PdfReader
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
        """Slices text into paired parent and child chunks using strict key tracking mappings."""
        logger.info(f"Slicing document context: {document_name}")
        hierarchical_map = []
        
        start_idx = 0
        parent_idx = 1
        child_idx = 1
        
        base_doc_name = document_name.split(".")[0].upper()
        base_doc_name = re.sub(r"[^A-Z0-9_]", "_", base_doc_name)
        
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
# 2. CHROMA VECTOR STORAGE ENGINE (ASYNC UPGRADE)
# =========================================================

class VectorStoreService:
    """Manages persistent vector collection connections with async batch processing capability."""
    
    def __init__(self):
        # We preserve the standard HttpClient for collection setups
        self.client = HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.embedding_url = f"{settings.LOCAL_LLM_URL.rstrip('/')}/api/embeddings"
        self.model_name = settings.EMBEDDING_MODEL
        
    async def _generate_embedding_async(self, client: httpx.AsyncClient, text_content: str) -> List[float]:
        """🟢 Non-blocking async vector computation hitting Ollama thread pools."""
        try:
            resp = await client.post(
                self.embedding_url, 
                json={"model": self.model_name, "prompt": text_content}, 
                timeout=60.0
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Async vector embedding generation failure: {str(e)}")
            raise RuntimeError(f"Vector embedding failure: {str(e)}")

    def get_or_create_collection(self, collection_name: str = "nexus_knowledge_pool"):
        """Returns targeted collection instance."""
        return self.client.get_or_create_collection(name=collection_name)

    async def insert_child_vector_async(self, client: httpx.AsyncClient, child_id: str, child_text: str, parent_id: str):
        """🟢 High-speed async write embedding task utilizing connection-pooled clients."""
        collection = self.get_or_create_collection()
        embedding = await self._generate_embedding_async(client, child_text)
        
        collection.add(
            ids=[child_id],
            embeddings=[embedding],
            metadatas=[{"parent_id": parent_id}],
            documents=[child_text]
        )
        logger.info(f"✅ Chroma Vector Registered: {child_id}")


# =========================================================
# 3. NEO4J GRAPH DATABASE ENGINE (ASYNC UPGRADE)
# =========================================================

class GraphDBService:
    """Manages transactional schema optimizations with high-speed async session operations."""
    
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

    async def save_hierarchical_edge_async(self, child_id: str, parent_id: str, parent_text: str):
        """🟢 Asynchronously maps a Child chunk to its Parent context frame in Neo4j."""
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
            # Utilizing drivers in non-blocking async context managers
            async with self._driver.session() as session:
                await session.run(cypher_query, child_id=child_id, parent_id=parent_id, parent_text=parent_text)
        except Exception as e:
            logger.error(f"Neo4j async edge transaction crashed: {str(e)}")
            raise e

    async def save_concept_mention_async(self, name: str, type: str, target_chunk_id: str):
        """🌐 Asynchronously binds extracted entities directly to target Neo4j nodes."""
        chunk_id = str(target_chunk_id).strip()
        if not name or not chunk_id:
            return

        clean_name = str(name).strip().upper()
        clean_name = re.sub(r'[^\w\s-]', '', clean_name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()

        raw_label = str(type).strip().upper()
        safe_label = "".join([c for c in raw_label if c.isalnum()]).upper()
        
        if safe_label not in ["CONCEPT", "TECHNOLOGY", "SYSTEM"]:
            safe_label = "CONCEPT"

        cypher_query = f"""
        MERGE (e:{safe_label} {{id: $entity_id}})
        WITH e
        MATCH (c:DocumentNode {{id: $chunk_id}})
        MERGE (e)-[:MENTIONED_IN]->(c);
        """
        try:
            async with self._driver.session() as session:
                await session.run(cypher_query, entity_id=clean_name, chunk_id=chunk_id)
        except Exception as e:
            logger.error(f"Neo4j async dynamic linkage failure: {str(e)}")


# =========================================================
# GLOBAL SINGLETON INSTANTIATION EXPORTS
# =========================================================

pdf_processor = PDFProcessorService()
vector_store = VectorStoreService()
graph_db = GraphDBService()