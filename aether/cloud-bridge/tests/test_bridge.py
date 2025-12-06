import pytest
from unittest.mock import MagicMock, AsyncMock
from src.bridge import CloudBridge


@pytest.fixture
def mock_mavlink():
    mock = MagicMock()
    # Mock async methods with AsyncMock
    mock.arm_async = AsyncMock(return_value=True)
    mock.disarm_async = AsyncMock(return_value=True)
    mock.guided_takeoff_async = AsyncMock(return_value=True)
    # Keep sync methods as regular mocks
    mock.start_mission = MagicMock()
    mock.get_messages = MagicMock(return_value=[])
    return mock

@pytest.fixture
def mock_mqtt():
    return MagicMock()

@pytest.fixture
def mock_mission_manager():
    return MagicMock()

@pytest.fixture
def bridge(mock_mavlink, mock_mqtt, mock_mission_manager):
    return CloudBridge(mock_mavlink, mock_mqtt, mock_mission_manager)


def test_telemetry_loop_global_position(bridge, mock_mavlink, mock_mqtt):
    # Setup - Create a mock MAVLink message
    msg = MagicMock()
    msg.get_type.return_value = 'GLOBAL_POSITION_INT'
    msg.lat = -35363261
    msg.lon = 149165230
    msg.alt = 10000
    msg.relative_alt = 5000
    msg.vx = 10
    msg.vy = 20
    msg.vz = 30
    msg.hdg = 18000

    # Configure mavlink.get_messages to return this message once, then stop
    # logic in telemetry_loop checks self.running, so we just return one list
    mock_mavlink.get_messages.return_value = [msg]
    
    # Run the loop (mocking 1 iteration)
    bridge.running = True
    
    # We need to hack the loop: allow ONE iteration
    # Since telemetry_loop loops on get_messages generator, we can just return one item in list
    # But wait, get_messages yields.
    
    def mock_generator():
        yield msg
    
    mock_mavlink.get_messages.side_effect = mock_generator

    # Run strictly one iteration logic extracted? 
    # Or just call telemetry_loop? 
    # If we call telemetry_loop, it loops 'for msg in self.mavlink.get_messages():'
    # So our generator yielding one item should work perfectly.
    
    bridge.telemetry_loop()
    
    # Verify
    mock_mqtt.publish_telemetry.assert_called_once()
    payload = mock_mqtt.publish_telemetry.call_args[0][0]
    
    assert payload['type'] == 'GLOBAL_POSITION_INT'
    assert payload['lat'] == -3.5363261
    assert payload['lon'] == 14.9165230
    assert payload['alt'] == 10.0

def test_command_received_arm(bridge, mock_mavlink):
    cmd_data = {'command': 'ARM'}
    bridge.on_command_received(cmd_data)
    mock_mavlink.arm_async.assert_called_once()

def test_command_received_takeoff(bridge, mock_mavlink):
    cmd_data = {'command': 'TAKEOFF', 'params': [50]}
    bridge.on_command_received(cmd_data)
    mock_mavlink.guided_takeoff_async.assert_called_once_with(50)


def test_mission_received(bridge, mock_mission_manager):
    """Verify that incoming mission plans are routed to MissionManager."""
    plan = {"mission_id": "test-123", "waypoints": []}
    
    bridge.on_mission_received(plan)
    
    mock_mission_manager.upload_mission.assert_called_once_with(plan)


def test_mission_forwarding(bridge, mock_mavlink, mock_mission_manager):
    """Verify that MAVLink mission messages are forwarded to MissionManager."""
    # Setup mock message
    msg = MagicMock()
    msg.get_type.return_value = 'MISSION_REQUEST'
    
    # Configure bridge loop to yield this message once
    mock_mavlink.get_messages.return_value = [msg]
    bridge.running = True
    
    # Run loop
    bridge.telemetry_loop()
    
    # Verify forwarding
    mock_mission_manager.on_mavlink_message.assert_called_once_with(msg)


