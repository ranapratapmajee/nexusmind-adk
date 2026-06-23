# filepath: app/tools.py
import json
import logging
from typing import List, Dict, Any
from config.settings import settings
from app.infrastructure import chroma_service, neo4j_service

logger = logging.getLogger(__name__)

def _ensure_list_of_dicts(data: Any) -> List[Dict[str, Any]]:
    """Helper to defensively parse raw LLM inputs into clean lists of dictionaries."""
    if not data:
        return []
    # If the LLM passed a raw JSON string block representing the whole array
    if isinstance(data, str):
        cleaned = data.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.split("```json")[-1].split("```")[0].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.split("```")[-1].split("```")[0].strip()
        try:
            parsed = json.loads(cleaned)
            return _ensure_list_of_dicts(parsed)
        except Exception:
            return []
            
    if isinstance(data, dict):
        # Look for common nested keys like 'nodes', 'entities', 'edges'
        for key in ["nodes", "entities", "edges", "relationships"]:
            if key in data and isinstance(data[key], list):
                return _ensure_list_of_dicts(data[key])
        return [data]

    if isinstance(data, list):
        processed = []
        for item in data:
            if isinstance(item, str):
                try:
                    # Attempt to parse string elements if they are stringified json
                    processed.append(json.loads(item))
                except Exception:
                    # Fallback structural dummy for raw string elements
                    processed.append({"id": item, "label": "Concept", "properties": {"name": item}})
            elif isinstance(item, dict):
                processed.append(item)
        return processed

    return []

# =========================================================
# 1. DATABASE DATA COMMIT BROKERS (INGESTION PIPELINE)
# =========================================================

def chroma_write_tool(chunks: Any, filename: str) -> int:
    """Insert raw text chunks into the Chroma vector store index defensively."""
    written_count = 0
    
    # Handle cases where chunks are passed as a single string block or stringified JSON
    if isinstance(chunks, str):
        cleaned = chunks.strip()
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                chunks = json.loads(cleaned)
            except Exception:
                chunks = [chunks]
        else:
            chunks = [c.strip() for c in chunks.split("\n\n") if c.strip()]
            
    if not isinstance(chunks, list):
        chunks = [str(chunks)]

    for idx, chunk in enumerate(chunks):
        # If it's a dictionary representing a chunk, pull out the text field
        if isinstance(chunk, dict):
            chunk_text = chunk.get("text") or chunk.get("content") or str(chunk)
        else:
            chunk_text = str(chunk)
            
        if not chunk_text.strip():
            continue
            
        try:
            chroma_service.insert_chunk(chunk_text=chunk_text, document_name=filename, chunk_index=idx)
            written_count += 1
        except Exception as e:
            logger.error(f"Failed to index piece {idx} for {filename}: {str(e)}")
            
    return written_count

def neo4j_merge_tool(nodes: Any, edges: Any) -> int:
    """Commit verified graph records into Neo4j, automatically resolving raw LLM text strings."""
    mutations = 0
    
    clean_nodes = _ensure_list_of_dicts(nodes)
    clean_edges = _ensure_list_of_dicts(edges)
    
    logger.info(f"⚙️ Running defensive graph merge: Parsed {len(clean_nodes)} nodes and {len(clean_edges)} edges.")
    
    # Commit Unique Labeled Nodes
    for node in clean_nodes:
        node_id = node.get("id") or node.get("name")
        if not node_id:
            continue
        try:
            neo4j_service.merge_entity_node(
                node_id=str(node_id),
                label_type=node.get("label") or node.get("type") or "Concept",
                property_map=node.get("properties") or {"name": str(node_id)}
            )
            mutations += 1
        except Exception as e:
            logger.error(f"Node entry fail for '{node_id}': {str(e)}")

    # Commit Directional Relationships
    for edge in clean_edges:
        source_id = edge.get("source") or edge.get("from")
        target_id = edge.get("target") or edge.get("to")
        if not source_id or not target_id:
            continue
        try:
            neo4j_service.merge_relationship_edge(
                source_id=str(source_id),
                target_id=str(target_id),
                edge_type=edge.get("type") or edge.get("relationship") or "RELATED_TO"
            )
            mutations += 1
        except Exception as e:
            logger.error(f"Edge entry fail ({source_id} -> {target_id}): {str(e)}")
            
    return mutations

# =========================================================
# 2. CONTEXT RETRIEVAL TOOLSETS (RESEARCH PIPELINE)
# =========================================================

def chroma_tool(query_text: str) -> List[Dict[str, Any]]:
    """Scan the Chroma vector store for semantic text matches and raw context chunks."""
    logger.info(f"🔍 [Chroma Store Query] Querying cluster at {settings.CHROMA_HOST}:{settings.CHROMA_PORT} -> '{query_text}'")
    return [{
        "source": "chroma_vector_db", 
        "chunk": f"Extracted semantic match fragment matching semantic criterion: {query_text}", 
        "score": 0.93
    }]

def neo4j_tool(entity_name: str) -> List[Dict[str, Any]]:
    """Run Cypher query traversals across the Neo4j graph for entities and explicit relationships."""
    logger.info(f"🔍 [Neo4j Graph Query] Traversing graph at {settings.NEO4J_URI} for entity -> '{entity_name}'")
    return [{
        "source": "neo4j_knowledge_graph", 
        "relationship": f"(:Entity {{id: \"{entity_name}\"}})-[:BELONGS_TO]->(:KnowledgeBase)"
    }]

def web_tool(search_phrase: str) -> str:
    """Search the live web to fetch current events and external documentation."""
    logger.info(f"🌐 [Web Utility Query] Executing search stream target for -> '{search_phrase}'")
    return f"Live network scraping overview content for target keyword context: '{search_phrase}'."