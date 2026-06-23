# filepath: app/infrastructure.py
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
# 1. BINARY FILE PARSING EXTRACTION ENGINE
# =========================================================

class PDFExtractor:
    """Extracts raw text strings from byte buffers and provides native chunking."""
    
    @staticmethod
    def extract_clean_text(file_bytes: bytes) -> str:
        """Reads stream bytes using pypdf to consolidate page paragraphs."""
        try:
            bytes_stream = io.BytesIO(file_bytes)
            pdf_reader = PdfReader(bytes_stream)
            
            extracted_pages = []
            for idx, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text)
                    
            consolidated_text = "\n\n".join(extracted_pages)
            logger.info(f"📄 Extracted {len(pdf_reader.pages)} pages from the uploaded stream.")
            return consolidated_text
            
        except Exception as e:
            logger.error(f"❌ Failed to extract text from PDF data stream: {str(e)}")
            raise RuntimeError(f"PDF extraction error: {str(e)}")

    @staticmethod
    def slice_hierarchical_chunks(text: str, parent_size: int = 2000, child_size: int = 400, overlap: int = 100) -> List[Dict[str, Any]]:
        """
        ⚡ PRE-FLIGHT TIMEOUT FIX: Programmatically windows text strings on the CPU.
        Returns a structured hierarchical map of Parent chunks containing overlapping Child slices.
        """
        print(f"⚙️ [NATIVE CHUNKER] Programmatically slicing text into parent/child boundaries...")
        hierarchical_map = []
        
        # 1. Split text into large parent chunks based on size boundaries
        start_idx = 0
        parent_index = 1
        child_global_index = 1
        
        while start_idx < len(text):
            end_idx = min(start_idx + parent_size, len(text))
            parent_chunk = text[start_idx:end_idx].strip()
            
            if parent_chunk:
                child_chunks = []
                # 2. Slice this parent chunk into smaller overlapping child chunks
                child_start = 0
                while child_start < len(parent_chunk):
                    child_end = min(child_start + child_size, len(parent_chunk))
                    child_text = parent_chunk[child_start:child_end].strip()
                    
                    if child_text:
                        child_chunks.append({
                            "id": child_global_index,
                            "text": child_text
                        })
                        child_global_index += 1
                        
                    # Advance child by chunk size minus overlap
                    child_start += (child_size - overlap)
                    if child_end == len(parent_chunk):
                        break
                        
                hierarchical_map.append({
                    "parent_index": parent_index,
                    "parent_chunk": parent_chunk,
                    "child_chunks": child_chunks
                })
                parent_index += 1
                
            start_idx += parent_size
            
        print(f"   └── ✅ [CHUNKER COMPLETE] Generated {len(hierarchical_map)} Parent contexts and {child_global_index - 1} Child sub-chunks.")
        return hierarchical_map

pdf_extractor = PDFExtractor()


# =========================================================
# 2. CHROMA HTTP CLIENT SERVICE ENGINE
# =========================================================

class ChromaService:
    """Manages persistent HTTP vector collection connections and local embedding hooks."""
    
    def __init__(self):
        self.client = HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.embedding_url = f"{settings.LOCAL_LLM_URL}/api/embeddings"
        self.model_name = settings.EMBEDDING_MODEL
        
    def _generate_embedding(self, text_content: str) -> list[float]:
        """Queries local Ollama endpoint to return dense vector representations using Nomic."""
        try:
            response = requests.post(
                self.embedding_url,
                json={"model": self.model_name, "prompt": text_content},
                timeout=15
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            logger.error(f"❌ Failed to extract dense embeddings from Ollama model '{self.model_name}': {str(e)}")
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


# =========================================================
# 3. NEO4J GRAPH DATABASE CONNECTION POOL
# =========================================================

class Neo4jService:
    """Manages transactional link operations and entity schema indexing."""
    
    def __init__(self):
        self._driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self._initialize_constraints()

    def close(self):
        """Gracefully closes open driver connections in the instance pool."""
        self._driver.close()

    def _initialize_constraints(self):
        """Ensures database optimization uniqueness bounds exist across entity domains."""
        query = "CREATE CONSTRAINT unique_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;"
        try:
            with self._driver.session() as session:
                session.run(query)
                logger.info("📐 Verified unique identity constraints on (:Entity) node structures.")
        except Exception as e:
            logger.warning(f"Could not apply structural constraints automatically: {str(e)}")

    def merge_entity_node(self, node_id: str, label_type: str, property_map: dict):
        """Creates or updates a single domain node without creating duplicate keys."""
        safe_label = "".join([char for char in label_type if char.isalnum()])
        
        cypher_query = f"""
        MERGE (e:Entity {{id: $node_id}})
        SET e.label = $label_type
        SET e += $properties
        REMOVE e:Entity
        WITH e
        CALL apoc.create.addLabels(e, [$safe_label]) YIELD node
        RETURN node;
        """
        with self._driver.session() as session:
            session.run(
                cypher_query, 
                node_id=node_id, 
                label_type=label_type, 
                properties=property_map, 
                safe_label=safe_label
            )

    def merge_relationship_edge(self, source_id: str, target_id: str, edge_type: str):
        """Establishes clear directional connection tracks between unique entities."""
        safe_type = "".join([char for char in edge_type if char.isalnum() or char == '_']).upper()
        
        cypher_query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:{safe_type}]->(target)
        RETURN r;
        """
        with self._driver.session() as session:
            session.run(cypher_query, source_id=source_id, target_id=target_id)
            logger.info(f"🔗 Merged Graph Edge: ({source_id})-[:{safe_type}]->({target_id})")

neo4j_service = Neo4jService()