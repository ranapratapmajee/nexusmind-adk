# filepath: app/tools/indexer_tools.py
import logging
from typing import List, Dict, Any
from app.infrastructure.chroma_service import chroma_service
from app.infrastructure.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)

def chroma_write_tool(chunks: List[str], filename: str) -> int:
    """Insert a list of raw split text strings straight into the Chroma vector store index."""
    written_count = 0
    for idx, chunk in enumerate(chunks):
        try:
            chroma_service.insert_chunk(chunk_text=chunk, document_name=filename, chunk_index=idx)
            written_count += 1
        except Exception as e:
            logger.error(f"Failed to index piece {idx} for {filename}: {str(e)}")
    return written_count

def neo4j_merge_tool(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> int:
    """Commit verified graph structural records directly into Neo4j using Cypher MERGE commands."""
    mutations = 0
    
    # 1. Commit Nodes
    for node in nodes:
        try:
            neo4j_service.merge_entity_node(
                node_id=node.get("id"),
                label_type=node.get("label", "Concept"),
                property_map=node.get("properties", {})
            )
            mutations += 1
        except Exception as e:
            logger.error(f"Node entry fail: {str(e)}")

    # 2. Commit Connections
    for edge in edges:
        try:
            neo4j_service.merge_relationship_edge(
                source_id=edge.get("source"),
                target_id=edge.get("target"),
                edge_type=edge.get("type", "RELATED_TO")
            )
            mutations += 1
        except Exception as e:
            logger.error(f"Edge entry fail: {str(e)}")
            
    return mutations