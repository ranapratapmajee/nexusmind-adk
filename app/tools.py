# filepath: app/tools.py
import logging
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse

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

# filepath: app/tools.py

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

    cypher_hybrid_query = """
    MATCH (c:DocumentNode {id: $chunk_id})
    OPTIONAL MATCH (c)-[:CHILD_OF]->(p:DocumentNode)
    OPTIONAL MATCH (entity)-[:MENTIONED_IN]->(c)
    RETURN DISTINCT p.id AS parent_id, 
                    coalesce(p.text, p.content, p.body, '') AS parent_text, 
                    collect(DISTINCT {
                        name: coalesce(entity.id, entity.name, ''), 
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


def web_search(query: str) -> str:
    """
    Queries live public internet directories for current information, 
    extracts the top results, and scrapes the full content of those pages 
    to provide deep technical facts. Skips tracking redirects.
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
        if scraped_count >= 2:  # Scaled down to 2 targets to prevent context explosion
            break

        link_el = result.select_one(".result__title a")
        if not link_el:
            continue

        title = _clean_text(link_el.get_text(" ", strip=True))
        raw_href = _clean_text(link_el.get("href", ""))

        if not raw_href:
            continue

        # 🛡️ FIX: Intercept domain redirects and tracking variables safely
        try:
            parsed_url = urlparse(raw_href)
            domain = str(parsed_url.netloc).lower()
            path = str(parsed_url.path).lower()
            
            # Instantly drop ad redirect networks
            if "duckduckgo.com" in domain and ("y.js" in path or "click" in path):
                continue
            if any(bad_token in domain for bad_token in ["bing.com", "doubleclick", "adservice", "googleadservices"]):
                continue
            if "ad_domain" in str(parsed_url.query).lower():
                continue

            # Strip tracking queries for clean citation logging
            clean_href = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, "", ""))
        except Exception:
            continue

        deep_content = _fetch_url_text_sync(clean_href, max_chars=2000)
        
        if deep_content:
            scraped_count += 1
            compiled_blocks.append(
                f"\n--- [Web Source Reference: {title}] ---\n"
                f"URL Address: {clean_href}\n"
                f"Full Scraped Webpage Content:\n{deep_content}"
            )
        else:
            snippet_el = result.select_one(".result__snippet")
            fallback_snippet = _clean_text(snippet_el.get_text(" ", strip=True) if snippet_el else "")
            if fallback_snippet:
                scraped_count += 1
                compiled_blocks.append(
                    f"\n--- [Web Source Snippet: {title}] ---\n"
                    f"URL Address: {clean_href}\n"
                    f"Summary Insight: {fallback_snippet}"
                )

    if scraped_count == 0:
        return "Search engine returned results, but the organic landing targets rejected connections."

    return "\n".join(compiled_blocks)