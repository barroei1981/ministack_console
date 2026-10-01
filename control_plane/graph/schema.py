"""
FalkorDB Schema Definition and Initialization.

Defines the core node types, relationship types, and indexes for the resource graph.
Follows Hybrid Schema Evolution Strategy (AD-11):
- Core structure (node/relationship types) is fixed and stable
- Resource metadata uses flexible JSON `state` property
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

# Schema Definition
SCHEMA: Dict[str, Any] = {
    "node_types": [
        {
            "label": "Tenant",
            "description": "MiniStack tenant (12-digit access key)",
            "properties": ["id", "name", "created_at"],
        },
        {
            "label": "Project",
            "description": "Logical grouping of resources within a tenant",
            "properties": ["name", "description", "tenant_id", "created_at"],
        },
        {
            "label": "Resource",
            "description": "AWS resource (S3 bucket, Lambda function, etc.)",
            "properties": [
                "id",  # Unique resource ID
                "type",  # e.g., "s3:bucket", "lambda:function"
                "name",  # Resource name
                "tenant_id",  # Owner tenant
                "arn",  # AWS ARN format
                "state",  # JSON blob of resource state (flexible per AD-11)
                "created_at",
                "updated_at",
            ],
        },
        {
            "label": "ServiceType",
            "description": "AWS service type category",
            "properties": ["name", "category"],
        },
        {
            "label": "Tag",
            "description": "Resource tag (key-value pair)",
            "properties": ["key", "value"],
        },
    ],
    "relationship_types": [
        {
            "type": "OWNS",
            "description": "Tenant owns Project",
            "from": "Tenant",
            "to": "Project",
        },
        {
            "type": "CONTAINS",
            "description": "Project contains Resource",
            "from": "Project",
            "to": "Resource",
        },
        {
            "type": "DEPENDS_ON",
            "description": "Resource depends on another Resource",
            "from": "Resource",
            "to": "Resource",
        },
        {
            "type": "TAGGED_WITH",
            "description": "Resource tagged with Tag",
            "from": "Resource",
            "to": "Tag",
            "properties": ["key", "value"],
        },
        {
            "type": "INSTANCE_OF",
            "description": "Resource is instance of ServiceType",
            "from": "Resource",
            "to": "ServiceType",
        },
    ],
    "indexes": [
        {
            "label": "Resource",
            "property": "tenant_id",
            "description": "Query resources by tenant",
        },
        {
            "label": "Resource",
            "property": "type",
            "description": "Query resources by service type",
        },
        {
            "label": "Resource",
            "property": "name",
            "description": "Query resources by name",
        },
        {
            "label": "Project",
            "property": "name",
            "description": "Query projects by name",
        },
    ],
}


def initialize_schema(graph) -> None:
    """
    Initialize FalkorDB schema with all node types, relationship types, and indexes.

    Idempotent: Can be called multiple times without errors. Will create missing indexes
    if schema already exists.

    Args:
        graph: FalkorDB graph instance

    Raises:
        Exception: If FalkorDB is unavailable or initialization fails
    """
    logger.info("Initializing FalkorDB schema...")

    try:
        # Create indexes (idempotent - will skip if already exists)
        for index_def in SCHEMA["indexes"]:
            label = index_def["label"]
            property_name = index_def["property"]

            try:
                # FalkorDB index creation syntax
                query = f"CREATE INDEX FOR (n:{label}) ON (n.{property_name})"
                graph.query(query)
                logger.info(f"Created index on {label}.{property_name}")
            except Exception as e:
                # Index may already exist - this is OK
                error_msg = str(e).lower()
                if "already indexed" in error_msg or "index already exists" in error_msg:
                    logger.debug(f"Index on {label}.{property_name} already exists")
                else:
                    logger.warning(f"Error creating index on {label}.{property_name}: {e}")

        logger.info("Schema initialization complete")

    except Exception as e:
        logger.error(f"Schema initialization failed: {e}")
        raise


def verify_schema(graph) -> Dict[str, Any]:
    """
    Verify that the FalkorDB schema is complete.

    Checks:
    - All indexes exist
    - Can query basic schema metadata

    Args:
        graph: FalkorDB graph instance

    Returns:
        Dict with verification results:
        {
            "valid": bool,
            "indexes": List[str],
            "missing_indexes": List[str],
            "message": str
        }
    """
    logger.info("Verifying FalkorDB schema...")

    result = {
        "valid": True,
        "indexes": [],
        "missing_indexes": [],
        "message": "Schema verification successful",
    }

    try:
        # Query existing indexes
        query = "CALL db.indexes()"
        response = graph.query(query)

        # Parse index results
        existing_indexes = set()
        for record in response.result_set:
            # FalkorDB returns: [label, properties, types, language, stopwords, entitytype]
            if len(record) >= 2:
                label = record[0]
                properties = record[1]

                # properties is a list like ['tenant_id']
                if isinstance(properties, list):
                    for prop in properties:
                        index_key = f"{label}.{prop}"
                        existing_indexes.add(index_key)
                        result["indexes"].append(index_key)

        # Check for missing indexes
        for index_def in SCHEMA["indexes"]:
            label = index_def["label"]
            property_name = index_def["property"]
            index_key = f"{label}.{property_name}"

            if index_key not in existing_indexes:
                result["missing_indexes"].append(index_key)
                result["valid"] = False

        if not result["valid"]:
            result["message"] = (
                f"Schema incomplete: missing indexes: {result['missing_indexes']}"
            )
            logger.warning(result["message"])
        else:
            logger.info("Schema verification passed")

        return result

    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        result["valid"] = False
        result["message"] = f"Schema verification error: {e}"
        return result


def get_node_types() -> List[str]:
    """Get list of all node type labels."""
    return [node["label"] for node in SCHEMA["node_types"]]


def get_relationship_types() -> List[str]:
    """Get list of all relationship type names."""
    return [rel["type"] for rel in SCHEMA["relationship_types"]]


def get_indexes() -> List[Dict[str, str]]:
    """Get list of all index definitions."""
    return SCHEMA["indexes"].copy()
