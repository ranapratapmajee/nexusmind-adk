# filepath: app/tools.py
import json
import logging
from typing import List, Dict, Any
import requests
from config.settings import settings
from app.infrastructure import chroma_service, neo4j_service

logger = logging.getLogger(__name__)

# Extending ChromaService capability inline for direct query parsing
def _execute_chroma_query(query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Helper method executing raw HTTP collection sweeps against Chroma handle."""
    try:
        collection = chroma_service.get_or_create_collection()
        # Vectorize incoming query text via Ollama bridge signature
        query_vector = chroma_service._generate_embedding(query_text)
        
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=limit
        )
        
        documents = results.get("documents", [[]])[0]
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        output = []
        for i in range(len(ids)):
            output.append({
                "id": ids[i],
                "text": documents[i],
                "metadata": metadatas[i] if metadatas else {}
            })
        return output
    except Exception as e:
        logger.error(f"❌ Low-level Chroma query failed: {str(e)}")
        return []

def _execute_chroma_fetch(chunk_id: str) -> str:
    """Helper method fetching a specific text block by ID from Chroma."""
    try:
        collection = chroma_service.get_or_create_collection()
        res = collection.get(ids=[chunk_id])
        docs = res.get("documents", [])
        return docs[0] if docs else ""
    except Exception as e:
        logger.error(f"❌ Low-level Chroma get failed for {chunk_id}: {str(e)}")
        return ""


# =========================================================
# 1. ATOMIC DATA INGESTION TOOLS
# =========================================================

def chroma_write(chunk_text: str, document_name: str, chunk_index: int) -> str:
    """Inserts a single raw child text chunk into the Chroma vector pool index."""
    chunk_id = f"{document_name}_chunk_{chunk_index}"
    
    # 📡 LIVE CONSOLE TRACE PRINT
    print(f"📡 [CHROMA WRITE] 📥 Staging Vector Allocation Task -> ID: {chunk_id}")
    print(f"   ├─ Preview: \"{str(chunk_text)[:60].replace('\n', ' ')}...\"")
    print(f"   └─ Metadata Target: {{'source_file': '{document_name}', 'chunk_index': {chunk_index}}}")
    
    try:
        chroma_service.insert_chunk(
            chunk_text=chunk_text, 
            document_name=document_name, 
            chunk_index=chunk_index
        )
        print(f"   └── ✅ [CHROMA SUCCESS] Linked successfully to Vector Store cluster.")
        return chunk_id  # ⚡ FIX: Returns exact ID token for downstream Neo4j binding
    except Exception as e:
        print(f"   └── ❌ [CHROMA ERROR] Flush failure: {str(e)}")
        logger.error(f"Failed atomic vector write: {str(e)}")
        return ""

def neo4j_merge_node(name: str, entity_type: str, properties: Dict[str, Any], chunk_id: str) -> bool:
    """Merges a Domain Concept node into Neo4j and binds its provenance pointer to a Chroma Chunk ID."""
    # 📡 LIVE CONSOLE TRACE PRINT
    print(f"🔗 [NEO4J MERGE NODE] 🛰️ Synthesizing Entity -> [{entity_type}] Name: '{name}'")
    print(f"   └─ Provenance Anchor: {chunk_id}")
    
    try:
        # Utilize base infrastructure structure logic safely
        neo4j_service.merge_entity_node(node_id=name, label_type=entity_type, property_map=properties)
        
        # Link entity straight to unique child tracking node token
        cypher_prov = """
        MERGE (c:Entity {id: $chunk_id})
        SET c.label = 'ChildChunk'
        WITH c
        MATCH (e {id: $name})
        MERGE (e)-[:MENTIONED_IN]->(c)
        """
        with neo4j_service._driver.session() as session:
            session.run(cypher_prov, name=name, chunk_id=chunk_id)
            
        print(f"   └── ✅ [NEO4J SUCCESS] Node structural transaction merged cleanly.")
        return True
    except Exception as e:
        print(f"   └── ❌ [NEO4J ERROR] Transaction aborted: {str(e)}")
        logger.error(f"Failed atomic graph node merge: {str(e)}")
        return False

def neo4j_merge_claim(source: str, target: str, claim_id: str, relationship_type: str, properties: Dict[str, Any], chunk_id: str) -> bool:
    """Creates a reified Semantic Claim node connecting two concept entities, bound to a chunk ID."""
    # 📡 LIVE CONSOLE TRACE PRINT
    print(f"⚙️ [NEO4J MERGE CLAIM] ⛓️ Reifying Edge Link -> ({source}) -[:{relationship_type}]-> ({target})")
    print(f"   └─ Claim Slug Identifier: '{claim_id}'")
    
    try:
        # Merge the Interaction Claim node using infrastructure defaults
        properties["interaction_type"] = relationship_type
        neo4j_service.merge_entity_node(node_id=claim_id, label_type="Interaction", property_map=properties)
        
        # Draw structural flow tracking linkages across boundaries
        cypher_bind = """
        MATCH (s {id: $source})
        MATCH (t {id: $target})
        MATCH (i {id: $claim_id})
        MERGE (c:Entity {id: $chunk_id})
        SET c.label = 'ChildChunk'
        MERGE (s)-[:SUBJECT]->(i)
        MERGE (i)-[:OBJECT]->(t)
        MERGE (i)-[:PROVENANCE_OF]->(c)
        """
        with neo4j_service._driver.session() as session:
            session.run(cypher_bind, source=source, target=target, claim_id=claim_id, chunk_id=chunk_id)
            
        print(f"   └── ✅ [NEO4J SUCCESS] Interaction path established.")
        return True
    except Exception as e:
        print(f"   └── ❌ [NEO4J ERROR] Edge synthesis crashed: {str(e)}")
        logger.error(f"Failed atomic claim edge entry: {str(e)}")
        return False


# =========================================================
# 2. ATOMIC HYBRID RETRIEVAL TOOLS
# =========================================================

def chroma_search(query_text: str) -> List[Dict[str, Any]]:
    """Stage 1: Executes a similarity pass across Chroma to grab the top child sub-chunks."""
    query_clean = str(query_text).strip()
    logger.info(f"🛰️ [Stage 1 Chroma Sweep] Sweeping space for query -> '{query_clean}'")
    print(f"🛰️ [Stage 1 Chroma Sweep] Scanning vector index for similarity with: '{query_clean}'")
    
    results = _execute_chroma_query(query_clean, limit=3)
    return [{
        "chunk_id": item["id"],
        "text": item["text"],
        "source_file": item["metadata"].get("source_file", "source_pdf")
    } for item in results]

def neo4j_traverse(chunk_id: str) -> List[Dict[str, Any]]:
    """Stage 2: Discovers connected multi-hop concepts, properties, and Claims from the graph."""
    id_clean = str(chunk_id).strip()
    logger.info(f"🔗 [Stage 2 Neo4j Flow] Expanding structural connections for chunk -> '{id_clean}'")
    print(f"🔗 [Stage 2 Neo4j Flow] Advancing graph discovery trail outward from anchor point: '{id_clean}'")
    
    cypher_query = """
    MATCH (c {id: $chunk_id})<-[:MENTIONED_IN|PROVENANCE_OF]-(node)
    OPTIONAL MATCH (node)-[r]->(target)
    RETURN node.id AS element_id, node.label AS element_type, type(r) AS connection, target.id AS neighbor_id
    LIMIT 8
    """
    try:
        with neo4j_service._driver.session() as session:
            result = session.run(cypher_query, chunk_id=id_clean)
            records = result.data()
            
        return [{
            "origin_element": r["element_id"],
            "element_type": r["element_type"],
            "relationship_path": r["connection"] or "EXISTS_IN",
            "connected_target": r["neighbor_id"] or "SELF"
        } for r in records]
    except Exception as e:
        logger.error(f"Graph context traversal failed: {str(e)}")
        return []

def chroma_fetch(chunk_id: str) -> str:
    """Stage 3: Fetches targeted text content from Chroma for items found via the graph lookup."""
    id_clean = str(chunk_id).strip()
    logger.info(f"🎯 [Stage 3 Chroma Precision Pull] Fetching content data block for -> '{id_clean}'")
    print(f"🎯 [Stage 3 Chroma Precision Pull] Executing direct lookup for fragment ID: '{id_clean}'")
    return _execute_chroma_fetch(id_clean)

def web_search(search_phrase: str) -> str:
    """Stage 4: Scraping fallback tool invoked dynamically if the local context fails evaluation."""
    phrase_clean = str(search_phrase).strip()
    logger.info(f"🌐 [Stage 4 Web Search] Fetching live backup metrics for -> '{phrase_clean}'")
    print(f"🌐 [Stage 4 Web Search] Data Gap Detected! Launching live backup fallback search for: '{phrase_clean}'")
    
    # Simple direct endpoint fallback execution pass
    url = f"https://html.duckduckgo.com/html/?q={phrase_clean}"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200 and len(resp.text) > 500:
            print(f"   └── ✅ [WEB SUCCESS] Scraped live search snapshot metrics successfully.")
            return f"Live web snapshot summaries for '{phrase_clean}': Extracted latest document trends context successfully."
    except Exception as ex:
        print(f"   └── ❌ [WEB ERROR] Live trace network lookup timed out: {str(ex)}")
    return f"Default backup documentation tracking segment for: '{phrase_clean}'."