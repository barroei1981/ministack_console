"""
Unit tests for FalkorDB schema initialization and verification.

Tests:
- Schema initialization idempotency
- Index creation verification
- Node type existence checks
"""

import pytest
from control_plane.graph.schema import (
    initialize_schema,
    verify_schema,
    get_node_types,
    get_relationship_types,
    get_indexes,
    SCHEMA,
)
from control_plane.graph.query import get_graph, reset_graph, health_check


@pytest.fixture(scope="module")
def graph():
    """Provide FalkorDB graph instance for tests."""
    try:
        g = get_graph()
        yield g
    finally:
        # Clean up after all tests
        reset_graph()


@pytest.fixture(autouse=True)
def reset_before_test(graph):
    """Reset graph before each test to ensure clean state."""
    reset_graph()
    yield


def test_health_check():
    """Test FalkorDB connection health check."""
    assert health_check(), "FalkorDB should be healthy"


def test_schema_constant_structure():
    """Test that SCHEMA constant has correct structure."""
    assert "node_types" in SCHEMA
    assert "relationship_types" in SCHEMA
    assert "indexes" in SCHEMA

    assert len(SCHEMA["node_types"]) > 0
    assert len(SCHEMA["relationship_types"]) > 0
    assert len(SCHEMA["indexes"]) > 0

    # Verify expected node types exist
    node_labels = [nt["label"] for nt in SCHEMA["node_types"]]
    assert "Tenant" in node_labels
    assert "Project" in node_labels
    assert "Resource" in node_labels
    assert "ServiceType" in node_labels
    assert "Tag" in node_labels


def test_schema_indexes():
    """Test that SCHEMA defines required indexes."""
    indexes = SCHEMA["indexes"]

    # Verify required indexes
    index_keys = [f"{idx['label']}.{idx['property']}" for idx in indexes]

    assert "Resource.tenant_id" in index_keys
    assert "Resource.type" in index_keys
    assert "Resource.name" in index_keys
    assert "Project.name" in index_keys


def test_initialize_schema_first_time(graph):
    """Test schema initialization on fresh database."""
    # Initialize schema
    initialize_schema(graph)

    # Verify indexes were created
    verification = verify_schema(graph)

    assert verification["valid"], f"Schema should be valid: {verification['message']}"
    assert len(verification["indexes"]) >= 4, "Should have at least 4 indexes"
    assert len(verification["missing_indexes"]) == 0, "No indexes should be missing"


def test_initialize_schema_idempotent(graph):
    """Test that schema initialization is idempotent (can run multiple times)."""
    # Initialize schema first time
    initialize_schema(graph)

    verification1 = verify_schema(graph)
    assert verification1["valid"]

    # Initialize schema second time (should not fail)
    initialize_schema(graph)

    verification2 = verify_schema(graph)
    assert verification2["valid"]

    # Verify same number of indexes
    assert len(verification1["indexes"]) == len(verification2["indexes"])


def test_verify_schema_on_empty_graph():
    """Test schema verification on empty graph (before initialization)."""
    # Use a fresh graph connection without initialization
    from control_plane.graph.query import reset_graph, get_graph, drop_all_indexes

    reset_graph()  # Ensure no nodes/relationships
    drop_all_indexes()  # Ensure no indexes (they persist across reset)
    graph = get_graph()

    # Don't initialize schema - verify should detect missing indexes
    verification = verify_schema(graph)

    # Schema should be invalid (no indexes yet)
    assert not verification["valid"], "Schema should be invalid on empty graph"
    assert len(verification["missing_indexes"]) > 0, "Should detect missing indexes"


def test_get_node_types():
    """Test get_node_types helper function."""
    node_types = get_node_types()

    assert isinstance(node_types, list)
    assert len(node_types) == 5
    assert "Tenant" in node_types
    assert "Project" in node_types
    assert "Resource" in node_types
    assert "ServiceType" in node_types
    assert "Tag" in node_types


def test_get_relationship_types():
    """Test get_relationship_types helper function."""
    rel_types = get_relationship_types()

    assert isinstance(rel_types, list)
    assert len(rel_types) == 5
    assert "OWNS" in rel_types
    assert "CONTAINS" in rel_types
    assert "DEPENDS_ON" in rel_types
    assert "TAGGED_WITH" in rel_types
    assert "INSTANCE_OF" in rel_types


def test_get_indexes():
    """Test get_indexes helper function."""
    indexes = get_indexes()

    assert isinstance(indexes, list)
    assert len(indexes) >= 4

    # Verify index structure
    for idx in indexes:
        assert "label" in idx
        assert "property" in idx
        assert "description" in idx


def test_schema_relationship_definitions():
    """Test that relationship definitions have correct structure."""
    for rel in SCHEMA["relationship_types"]:
        assert "type" in rel
        assert "description" in rel
        assert "from" in rel
        assert "to" in rel

        # Verify from/to reference valid node types
        node_types = get_node_types()
        assert rel["from"] in node_types, f"Invalid 'from' node type: {rel['from']}"
        assert rel["to"] in node_types, f"Invalid 'to' node type: {rel['to']}"


def test_schema_node_properties():
    """Test that Resource node has all required properties."""
    resource_node = next(
        (nt for nt in SCHEMA["node_types"] if nt["label"] == "Resource"),
        None
    )

    assert resource_node is not None

    required_props = [
        "id", "type", "name", "tenant_id", "arn",
        "state", "created_at", "updated_at"
    ]

    for prop in required_props:
        assert prop in resource_node["properties"], \
            f"Resource node missing required property: {prop}"
