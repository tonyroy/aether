import pytest
from unittest.mock import AsyncMock, MagicMock
from src.dispatcher import FleetDispatcher, NoDroneAvailableError
from src.workflows import DroneEntityWorkflow

# TDD Specification for Smart Dispatcher

@pytest.fixture
def mock_iot():
    return MagicMock()

@pytest.fixture
def mock_temporal():
    return AsyncMock()

@pytest.fixture
def dispatcher(mock_temporal, mock_iot):
    return FleetDispatcher(mock_temporal, mock_iot)

@pytest.mark.asyncio
async def test_dispatch_finds_idle_drone(dispatcher, mock_iot, mock_temporal):
    """
    Scenario: Fleet has one IDLE and CONNECTED drone.
    Given: AWS IoT Index returns 'drone-1'.
    When: dispatch_mission is called.
    Then: It should signal the 'entity-drone-1' workflow with the mission.
    """
    # Mock IoT Search Index Response
    mock_iot.search_index.return_value = {
        'things': [{'thingName': 'drone-1'}]
    }

    # Mock Temporal Workflow Handle
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle.return_value = mock_handle

    mission = {"id": "mission-123", "waypoints": []}
    
    # Execute
    drone_id = await dispatcher.dispatch_mission(mission)

    # Verify
    assert drone_id == "drone-1"
    
    # Verify Query
    mock_iot.search_index.assert_called_once()
    query_arg = mock_iot.search_index.call_args[1]['queryString']
    assert "connectivity.connected:true" in query_arg
    assert "shadow.reported.orchestrator.status:IDLE" in query_arg
    assert "attributes.type:aether-drone" in query_arg

    # Verify Signal
    mock_temporal.get_workflow_handle.assert_called_with("entity-drone-1")
    mock_handle.signal.assert_called_once_with(DroneEntityWorkflow.assign_mission, mission)


@pytest.mark.asyncio
async def test_dispatch_no_drones_available(dispatcher, mock_iot):
    """
    Scenario: Fleet is fully BUSY or Offline.
    Given: AWS IoT Index returns empty list.
    When: dispatch_mission is called.
    Then: It should raise NoDroneAvailableError.
    """
    mock_iot.search_index.return_value = {'things': []}

    with pytest.raises(NoDroneAvailableError):
        await dispatcher.dispatch_mission({})

@pytest.mark.asyncio
async def test_dispatch_ignores_other_things(dispatcher, mock_iot):
    """
    Scenario: Index query should include type filtering.
    Given: Implementation details (verified in test_dispatch_finds_idle_drone query string).
    """
    pass # Covered by query string assertion
