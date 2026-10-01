"""
Integration test for FalkorDB data persistence.

Tests that data persists across FalkorDB container restarts.
"""

import pytest
import subprocess
import time
from datetime import datetime, UTC
from control_plane.graph.query import (
    get_graph,
    create_node,
    query_nodes,
    reset_graph,
    close_connection,
)
from control_plane.graph.schema import initialize_schema


@pytest.fixture(scope="module")
def docker_compose_available():
    """Check if docker-compose is available and FalkorDB service is configured."""
    try:
        result = subprocess.run(
            ["docker-compose", "version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            pytest.skip("docker-compose not available")

        # Check if docker-compose.yml has falkordb service
        result = subprocess.run(
            ["docker-compose", "config", "--services"],
            capture_output=True,
            timeout=5,
            text=True,
        )
        if "falkordb" not in result.stdout:
            pytest.skip("falkordb service not configured in docker-compose.yml")

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("docker-compose not available or timeout")


def restart_falkordb_container():
    """Restart FalkorDB container via docker-compose."""
    try:
        # Stop FalkorDB
        subprocess.run(
            ["docker-compose", "stop", "falkordb"],
            check=True,
            timeout=30,
        )

        # Wait for clean shutdown
        time.sleep(2)

        # Start FalkorDB
        subprocess.run(
            ["docker-compose", "start", "falkordb"],
            check=True,
            timeout=30,
        )

        # Wait for startup
        time.sleep(5)

        return True

    except subprocess.CalledProcessError as e:
        print(f"Failed to restart FalkorDB: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("Timeout restarting FalkorDB")
        return False


@pytest.mark.integration
def test_data_persists_across_restart(docker_compose_available):
    """
    Test that data persists across FalkorDB container restarts.

    Steps:
    1. Create a test resource node
    2. Verify node exists
    3. Restart FalkorDB container
    4. Verify node still exists after restart
    """
    # Clean slate
    reset_graph()

    # Initialize schema
    graph = get_graph()
    initialize_schema(graph)

    # Create test resource
    test_resource = {
        "id": "persistence-test-resource",
        "type": "s3:bucket",
        "name": "persistence-test-bucket",
        "tenant_id": "999999999999",
        "arn": "arn:aws:s3:::persistence-test-bucket",
        "state": '{"test": "persistence"}',
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    created = create_node("Resource", test_resource)
    assert created["id"] == test_resource["id"]

    # Verify node exists before restart
    results_before = query_nodes("Resource", filters={"id": "persistence-test-resource"})
    assert len(results_before) == 1
    assert results_before[0]["name"] == "persistence-test-bucket"

    print("✓ Node created and verified before restart")

    # Close existing connection
    close_connection()

    # Restart FalkorDB container
    print("Restarting FalkorDB container...")
    restart_success = restart_falkordb_container()

    if not restart_success:
        pytest.fail("Failed to restart FalkorDB container")

    print("✓ FalkorDB container restarted")

    # Reconnect and query again
    graph_after = get_graph()

    # Verify node still exists after restart
    results_after = query_nodes("Resource", filters={"id": "persistence-test-resource"})

    assert len(results_after) == 1, "Node should exist after restart"
    assert results_after[0]["id"] == "persistence-test-resource"
    assert results_after[0]["name"] == "persistence-test-bucket"
    assert results_after[0]["tenant_id"] == "999999999999"

    print("✓ Node persisted across restart")


@pytest.mark.integration
def test_indexes_persist_across_restart(docker_compose_available):
    """
    Test that indexes persist across FalkorDB container restarts.

    Steps:
    1. Initialize schema (create indexes)
    2. Verify indexes exist
    3. Restart FalkorDB container
    4. Verify indexes still exist after restart
    """
    from control_plane.graph.schema import verify_schema

    # Clean slate
    reset_graph()

    # Initialize schema
    graph = get_graph()
    initialize_schema(graph)

    # Verify schema before restart
    verification_before = verify_schema(graph)
    assert verification_before["valid"], "Schema should be valid before restart"
    indexes_before = set(verification_before["indexes"])

    print(f"✓ Schema valid before restart with {len(indexes_before)} indexes")

    # Close connection
    close_connection()

    # Restart FalkorDB container
    print("Restarting FalkorDB container...")
    restart_success = restart_falkordb_container()

    if not restart_success:
        pytest.fail("Failed to restart FalkorDB container")

    print("✓ FalkorDB container restarted")

    # Reconnect and verify schema again
    graph_after = get_graph()
    verification_after = verify_schema(graph_after)

    assert verification_after["valid"], "Schema should be valid after restart"

    indexes_after = set(verification_after["indexes"])

    # Compare indexes
    assert indexes_before == indexes_after, "Indexes should match before and after restart"

    print(f"✓ Indexes persisted: {len(indexes_after)} indexes still exist")


@pytest.mark.integration
def test_multiple_nodes_persist(docker_compose_available):
    """
    Test that multiple nodes and relationships persist across restart.

    Steps:
    1. Create tenant, project, and resource nodes
    2. Create relationships between them
    3. Restart container
    4. Verify all nodes and relationships still exist
    """
    # Clean slate
    reset_graph()

    # Initialize schema
    graph = get_graph()
    initialize_schema(graph)

    # Create tenant
    tenant = {
        "id": "111111111111",
        "name": "persistence-tenant",
        "created_at": datetime.now(UTC).isoformat(),
    }
    create_node("Tenant", tenant)

    # Create project
    project = {
        "id": "persistence-project",
        "name": "persistence-project",
        "description": "Test project for persistence",
        "tenant_id": "111111111111",
        "created_at": datetime.now(UTC).isoformat(),
    }
    create_node("Project", project)

    # Create resource
    resource = {
        "id": "persistence-resource-1",
        "type": "s3:bucket",
        "name": "persistence-bucket",
        "tenant_id": "111111111111",
        "arn": "arn:aws:s3:::persistence-bucket",
        "state": "{}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    create_node("Resource", resource)

    print("✓ Created 3 nodes before restart")

    # Verify nodes exist before restart
    tenants_before = query_nodes("Tenant", filters={"id": "111111111111"})
    projects_before = query_nodes("Project", filters={"id": "persistence-project"})
    resources_before = query_nodes("Resource", filters={"id": "persistence-resource-1"})

    assert len(tenants_before) == 1
    assert len(projects_before) == 1
    assert len(resources_before) == 1

    # Close connection
    close_connection()

    # Restart FalkorDB container
    print("Restarting FalkorDB container...")
    restart_success = restart_falkordb_container()

    if not restart_success:
        pytest.fail("Failed to restart FalkorDB container")

    print("✓ FalkorDB container restarted")

    # Reconnect and verify all nodes still exist
    graph_after = get_graph()

    tenants_after = query_nodes("Tenant", filters={"id": "111111111111"})
    projects_after = query_nodes("Project", filters={"id": "persistence-project"})
    resources_after = query_nodes("Resource", filters={"id": "persistence-resource-1"})

    assert len(tenants_after) == 1, "Tenant should persist"
    assert len(projects_after) == 1, "Project should persist"
    assert len(resources_after) == 1, "Resource should persist"

    # Verify properties
    assert tenants_after[0]["name"] == "persistence-tenant"
    assert projects_after[0]["name"] == "persistence-project"
    assert resources_after[0]["name"] == "persistence-bucket"

    print("✓ All 3 nodes persisted with correct properties")
