# filepath: app/infrastructure/neo4j_service.py
import logging
from neo4j import GraphDatabase
from config.settings import settings

logger = logging.getLogger(__name__)

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
        # Clean label values safely ensuring injection prevention vectors
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