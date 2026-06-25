# filepath: app/tools.py
import logging
import httpx
from bs4 import BeautifulSoup

# Point straight to unified, thread-isolated consolidated singletons
from app.services import vector_store, graph_db

logger = logging.getLogger(__name__)

DUCKDUCKGO_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"

def _clean_text(value: str) -> str:
    """White-space compressor utility."""
    return " ".join((value or "").split()).strip()


def _fetch_url_text_sync(url: str, max_chars: int = 4000) -> str:
    """
    Synchronous implementation of your scraper project.
    Fetches the deep web page using trafilatura with a BeautifulSoup fallback.
    """
    if not url or not url.strip():
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(timeout=8.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"⚠️ Could not deep scrape URL: {url} | Reason: {e}")
        return ""

    # Attempt high-performance extraction via trafilatura first
    try:
        import trafilatura
        extracted = trafilatura.extract(html) or ""
    except Exception:
        extracted = ""

    # Native BeautifulSoup fallback if trafilatura yields nothing
    if not extracted:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "header", "footer", "svg"]):
                tag.decompose()
            extracted = soup.get_text(" ", strip=True)
        except Exception:
            return ""

    clean_payload = _clean_text(extracted)
    return (
        f"{clean_payload[:max_chars]}..."
        if len(clean_payload) > max_chars
        else clean_payload
    )


# =========================================================
# HIGH-RELIABILITY HYBRID RETRIEVAL TOOLS (UNIFIED INTERFACE)
# =========================================================

def graph_rag_retrieval(query: str) -> str:
    """
    Looks up internal vector chunks matching your search query, matches 
    them to their structural parent files in Neo4j, extracts conceptual metadata,
    and returns clean, easy-to-read natural sentences.
    """
    query_clean = str(query).strip()
    print(f"🛰️ [GraphRAG Retrieval] Pulling hybrid knowledge paths for: '{query_clean}'")
    
    try:
        collection = vector_store.get_or_create_collection()
        query_vector = vector_store._generate_embedding(query_clean)
        results = collection.query(query_embeddings=[query_vector], n_results=2)
        
        # Extract the collection layers safely out of the first matrix list envelope
        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
    except Exception as e:
        logger.error(f"❌ Chroma runtime read error: {str(e)}")
        return "Internal vector document index lookup timed out."

    if not ids:
        return "No local company records matched your query terms."

    narrative = ["INTERNAL COMPANY FACT CHUNKS:"]

    cypher_hybrid_query = """
    MATCH (c:DocumentNode {id: $chunk_id})
    OPTIONAL MATCH (c)-[:CHILD_OF|PARENT_OF|PART_OF]*..1-(p:DocumentNode)
    OPTIONAL MATCH (entity)-[:MENTIONED_IN|EXTRACTED_FROM|HAS_CONCEPT]*..1-(c)
    WHERE p <> c
    RETURN DISTINCT p.id AS parent_id, 
                    coalesce(p.text, p.content, p.body, '') AS parent_text, 
                    collect(DISTINCT {name: coalesce(entity.id, entity.name, ''), type: labels(entity)}) AS concepts
    """
    
    for raw_chunk_id, child_text in zip(ids, documents):
        # 🌟 FIXED: Coerce the element directly to a clean string primitive to prevent list reference bleeding
        chunk_id = str(raw_chunk_id).strip()
        
        narrative.append(f"\n[Source Citation ID: {chunk_id}]")
        narrative.append(f"Specific matching fact: '{child_text}'")
        
        try:
            with graph_db._driver.session() as session:
                res = session.run(cypher_hybrid_query, chunk_id=chunk_id)
                record = res.single()
                
                if record:
                    if record["parent_text"] and str(record["parent_text"]).strip():
                        parent_body = str(record["parent_text"]).strip()
                        narrative.append(f" └── Full Parent Context ({record['parent_id']}): '{parent_body}'")
                    
                    valid_concepts = [f"{c['name']}" for c in record["concepts"] if c.get("name")]
                    if valid_concepts:
                        concept_string = ", ".join(set(valid_concepts))
                        narrative.append(f" └── Connected Topical Metadata tags: {concept_string}")
                else:
                    logger.info(f"ℹ️ No structural links or properties resolved in Neo4j for Chunk ID: {chunk_id}")
        except Exception as e:
            logger.error(f"❌ Neo4j link query broken for {chunk_id}: {str(e)}")
            continue

    return "\n".join(narrative)


def web_search(query: str) -> str:
    """
    Queries live public internet directories for current information, 
    extracts the top results, and scrapes the full content of those pages 
    to provide deep technical facts.
    
    Args:
        query: The plain-text search terms or keywords extracted from the user request.
    """
    phrase_clean = str(query).strip()
    if not phrase_clean:
        return "No live internet search keywords were provided."

    print(f"🌐 [Web Search] Dispatching high-density search & deep scrape for: '{phrase_clean}'")

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(timeout=10.0, headers=headers, follow_redirects=True) as client:
            resp = client.post(DUCKDUCKGO_HTML_ENDPOINT, data={"q": phrase_clean})
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.error(f"❌ Live external web lookup network failure: {e}")
        return f"Web search could not retrieve live documentation insights for: '{phrase_clean}'."

    soup = BeautifulSoup(html, "html.parser")
    compiled_blocks = ["LIVE PUBLIC INTERNET DEEP-SCRAPE DATA:"]
    
    scraped_count = 0
    for result in soup.select(".result"):
        if scraped_count >= 3:
            break

        link_el = result.select_one(".result__title a")
        title = _clean_text(link_el.get_text(" ", strip=True) if link_el else "")
        href = _clean_text(link_el.get("href", "") if link_el else "")

        if not href:
            continue

        deep_content = _fetch_url_text_sync(href, max_chars=3500)
        
        if deep_content:
            scraped_count += 1
            compiled_blocks.append(
                f"\n--- [Web Source Reference: {title}] ---\n"
                f"URL Address: {href}\n"
                f"Full Scraped Webpage Content:\n{deep_content}"
            )
        else:
            snippet_el = result.select_one(".result__snippet")
            fallback_snippet = _clean_text(snippet_el.get_text(" ", strip=True) if snippet_el else "")
            if fallback_snippet:
                scraped_count += 1
                compiled_blocks.append(
                    f"\n--- [Web Source Snippet: {title}] ---\n"
                    f"URL Address: {href}\n"
                    f"Summary Insight: {fallback_snippet}"
                )

    if scraped_count == 0:
        return "Search engine returned results, but the target pages rejected the scraping pipeline connection requests."

    return "\n".join(compiled_blocks)