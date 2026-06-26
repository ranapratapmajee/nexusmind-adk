# filepath: app/tools.py
import logging
from app.services import vector_store, graph_db

logger = logging.getLogger(__name__)

def graph_rag_retrieval(query: str) -> str:
    """
    Looks up internal vector chunks matching your search query, matches 
    them to their structural parent files in Neo4j, deduplicates parent contexts, 
    and returns a clean, non-repetitive reference summary.
    """
    query_clean = str(query).strip()
    print(f"🛰️ [GraphRAG Retrieval] Pulling hybrid knowledge paths for: '{query_clean}'")
    
    try:
        collection = vector_store.get_or_create_collection()
        query_vector = vector_store._generate_embedding(query_clean)
        # Pull 3 chunks to ensure high recall; Python will safely clean duplicates
        results = collection.query(query_embeddings=[query_vector], n_results=3)
        
        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
    except Exception as e:
        logger.error(f"❌ Chroma runtime read error: {str(e)}")
        return "Internal vector document index lookup timed out."

    if not ids:
        return "No local company records matched your query terms."

    narrative = ["INTERNAL COMPANY FACT CHUNKS:"]
    
    # 🛡️ THE DEDUPLICATION GUARD: Tracks parent nodes we've already printed
    seen_parent_ids = set()

    # 🛠️ FIXED: Cleaned up properties mismatch to permanently stop DBMS notification warnings
    cypher_hybrid_query = """
    MATCH (c:DocumentNode {id: $chunk_id})
    OPTIONAL MATCH (c)-[:CHILD_OF]->(p:DocumentNode)
    OPTIONAL MATCH (entity)-[:MENTIONED_IN]->(c)
    RETURN DISTINCT p.id AS parent_id, 
                    coalesce(p.text, '') AS parent_text, 
                    collect(DISTINCT {
                        name: coalesce(entity.id, ''), 
                        type: labels(entity)[0]
                    }) AS concepts
    """
    
    for raw_chunk_id, child_text in zip(ids, documents):
        chunk_id = str(raw_chunk_id).strip()
        
        try:
            with graph_db._driver.session() as session:
                res = session.run(cypher_hybrid_query, chunk_id=chunk_id)
                record = res.single()
                
                if record:
                    parent_id = str(record["parent_id"] or "").strip()
                    parent_text = str(record["parent_text"] or "").strip()
                    valid_concepts = [f"{c['name']}" for c in record["concepts"] if c.get("name")]
                    
                    # Case A: We haven't seen this parent text block yet -> Print everything
                    if parent_id and parent_id not in seen_parent_ids:
                        seen_parent_ids.add(parent_id)
                        
                        narrative.append(f"\n[Source Citation ID: {chunk_id}]")
                        narrative.append(f"Specific matching fact: '{child_text}'")
                        if parent_text:
                            narrative.append(f" └── Full Parent Context ({parent_id}): '{parent_text}'")
                        if valid_concepts:
                            concept_string = ", ".join(set(valid_concepts))
                            narrative.append(f" └── Connected Topical Metadata tags: {concept_string}")
                    
                    # Case B: Parent text block was already printed -> Only attach new specific chunk info
                    else:
                        narrative.append(f"\n[Source Citation ID: {chunk_id}]")
                        narrative.append(f"Specific matching fact: '{child_text}'")
                        narrative.append(f" └── Full Parent Context ({parent_id}): [OMITTED DUP - SEE ABOVE FOR CONTEXT]")
                        if valid_concepts:
                            concept_string = ", ".join(set(valid_concepts))
                            narrative.append(f" └── Additional Topical Metadata tags: {concept_string}")
                else:
                    # Fallback if graph links are empty
                    narrative.append(f"\n[Source Citation ID: {chunk_id}]")
                    narrative.append(f"Specific matching fact: '{child_text}'")
        except Exception as e:
            logger.error(f"❌ Neo4j link query broken for {chunk_id}: {str(e)}")
            continue

    return "\n".join(narrative)