# filepath: main.py
import asyncio
import logging
import sys
import requests
from config.settings import settings

# Fixed Import Paths matching your shared infrastructure module file layout
from app.infrastructure import chroma_service, neo4j_service

# Configure basic logging layout
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def verify_infrastructure() -> bool:
    logger.info("🕵️ Starting NexusMind Infrastructure Connectivity Tests...")
    all_passed = True

    # 1. Test Ollama Embedding Endpoint
    try:
        url = f"{settings.LOCAL_LLM_URL}/api/tags"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            logger.info("✅ Ollama Service Status: ONLINE")
        else:
            logger.error(f"❌ Ollama Service Status: Error Code {res.status_code}")
            all_passed = False
    except Exception as e:
        logger.error(f"❌ Ollama Service Connectivity Failure: {str(e)}")
        all_passed = False

    # 2. Test ChromaDB Connection
    try:
        collection = chroma_service.get_or_create_collection()
        logger.info(f"✅ ChromaDB Cluster Connection: ONLINE (Collection: '{collection.name}')")
    except Exception as e:
        logger.error(f"❌ ChromaDB Cluster Connection Failure: {str(e)}")
        all_passed = False

    # 3. Test Neo4j Graph Driver
    try:
        with neo4j_service._driver.session() as session:
            res = session.run("RETURN 1 AS test_val").single()
            if res and res["test_val"] == 1:
                logger.info("✅ Neo4j Graph Database Driver: ONLINE")
            else:
                logger.error("❌ Neo4j Graph Driver test returned an invalid payload.")
                all_passed = False
    except Exception as e:
        logger.error(f"❌ Neo4j Graph Cluster Failure: {str(e)}")
        all_passed = False
    finally:
        # Gracefully disconnect test hooks to avoid ghost socket states
        try:
            neo4j_service.close()
        except Exception:
            pass

    return all_passed

if __name__ == "__main__":
    success = verify_infrastructure()
    if success:
        logger.info("🚀 All Infrastructure layers verified successfully. Ready to launch!")
        sys.exit(0)
    else:
        logger.error("🛑 Infrastructure checks failed. Please check your docker containers.")
        sys.exit(1)
        