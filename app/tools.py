# filepath: app/tools.py
import json
import logging
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from app.infrastructure import chroma_service, neo4j_service

logger = logging.getLogger(__name__)

DUCKDUCKGO_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"

def _clean_text(value: str) -> str:
    """White-space compressor utility."""
    return " ".join((value or "").split()).strip()

# =========================================================
# 1. ATOMIC DATA INGESTION TOOLS
# =========================================================

def chroma_write(chunk_text: str, document_name: str, chunk_index: int) -> str:
    """Inserts a single raw child text chunk into the Chroma vector pool index."""
    chunk_id = f"{document_name}_chunk_{chunk_index}"
    print(f"📡 [CHROMA WRITE] 📥 Staging Vector Allocation Task -> ID: {chunk_id}")
    try:
        chroma_service.insert_chunk(
            chunk_text=chunk_text, 
            document_name=document_name, 
            chunk_index=chunk_index
        )
        print(f"   └── ✅ [CHROMA SUCCESS] Linked successfully to Vector Store cluster.")
        return chunk_id  
    except Exception as e:
        print(f"   └── ❌ [CHROMA ERROR] Flush failure: {str(e)}")
        logger.error(f"Failed atomic vector write: {str(e)}")
        return ""

def neo4j_merge_node(name: str, entity_type: str, properties: Dict[str, Any], chunk_id: str) -> bool:
    """Merges a Domain Concept node into Neo4j and binds its provenance pointer to a Chroma Chunk ID."""
    print(f"🔗 [NEO4J MERGE NODE] 🛰️ Synthesizing Entity -> [{entity_type}] Name: '{name}'")
    try:
        neo4j_service.merge_entity_node(node_id=name, label_type=entity_type, property_map=properties)
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
    print(f"⚙️ [NEO4J MERGE CLAIM] ⛓️ Reifying Edge Link -> ({source}) -[:{relationship_type}]-> ({target})")
    try:
        properties["interaction_type"] = relationship_type
        neo4j_service.merge_entity_node(node_id=claim_id, label_type="Interaction", property_map=properties)
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
# 2. HIGH-RELIABILITY RETRIEVAL TOOLS
# =========================================================

def graph_rag_retrieval(query_text: str) -> str:
    """
    Executes a complete Bottom-Up GraphRAG retrieval pass natively in Python.
    Finds top 3 child chunks in Chroma, climbs up to Neo4j for parent context.
    """
    query_clean = str(query_text).strip()
    print(f"🛰️ [GraphRAG Pipeline] Initiating unified retrieval pass for: '{query_clean}'")
    
    try:
        collection = chroma_service.get_or_create_collection()
        query_vector = chroma_service._generate_embedding(query_clean)
        results = collection.query(query_embeddings=[query_vector], n_results=3)
        documents = results.get("documents", [[]])[0]
        ids = results.get("ids", [[]])[0]
    except Exception as e:
        logger.error(f"❌ Low-level Chroma step failed: {str(e)}")
        return "Error gathering local vector chunks."

    if not ids:
        return "No local matching vector documents found."

    combined_context = ["=== LOCAL TEXT CHUNKS (CHROMA) ==="]
    for idx, doc_text in zip(ids, documents):
        combined_context.append(f"[{idx}]: {doc_text}")

    combined_context.append("\n=== KNOWLEDGE GRAPH RELATIONSHIPS & PARENTS (NEO4J) ===")
    cypher_query = """
    MATCH (c {id: $chunk_id})<-[:MENTIONED_IN|PROVENANCE_OF]-(node)
    OPTIONAL MATCH (node)-[r]->(target)
    RETURN node.id AS element_id, node.label AS element_type, type(r) AS connection, target.id AS neighbor_id
    LIMIT 5
    """
    try:
        with neo4j_service._driver.session() as session:
            for chunk_id in ids:
                res = session.run(cypher_query, chunk_id=chunk_id)
                records = res.data()
                if records:
                    combined_context.append(f"\nStructure linked to Child chunk [{chunk_id}]:")
                    for r in records:
                        combined_context.append(
                            f" - Entity: {r['element_id']} ({r['element_type']}) "
                            f"-[:{r['connection'] or 'EXISTS_IN'}]-> Neighbor: {r['neighbor_id'] or 'SELF'}"
                        )
    except Exception as e:
        logger.error(f"❌ Low-level Neo4j step failed: {str(e)}")
        combined_context.append("[Warning: Knowledge graph links could not be read]")

    return "\n".join(combined_context)


def web_search(search_phrase: str) -> str:
    """
    Executes a functional form-encoded POST lookup against DuckDuckGo.
    Returns clean structural result snippets.
    """
    phrase_clean = str(search_phrase).strip()
    if not phrase_clean:
        return "No search query provided."

    print(f"🌐 [Web Search Node] Dispatching POST form-vector lookup for: '{phrase_clean}'")

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        # ⚡ Utilizing the exact high-density form-encoded execution pass
        resp = requests.post(DUCKDUCKGO_HTML_ENDPOINT, data={"q": phrase_clean}, headers=headers, timeout=10.0)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.error(f"[Core Web Search Failure Exception] Query: {phrase_clean} | Log: {e}")
        return f"Web search could not retrieve live documentation insights for tracking frame: '{phrase_clean}'."

    soup = BeautifulSoup(html, "html.parser")
    compiled_blocks = []
    
    # Trace through exact matching visual classes from your utility tool code
    for result in soup.select(".result")[:3]:
        link_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")

        title = _clean_text(link_el.get_text(" ", strip=True) if link_el else "")
        body = _clean_text(snippet_el.get_text(" ", strip=True) if snippet_el else "")

        if title or body:
            compiled_blocks.append(f"- Title: {title}\n  Snippet: {body}")

    if not compiled_blocks:
        return f"No visual text records parsed out of raw document results for: '{phrase_clean}'."

    return "=== LIVE INTERNET CONTEXT ===\n" + "\n\n".join(compiled_blocks)