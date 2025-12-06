import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.bridge import CloudBridge


@pytest.fixture
def mock_mavlink():
    mock = MagicMock()
    # Mock async methods with AsyncMock
    mock.arm_async = AsyncMock(return_value=True)
    mock.disarm_async = AsyncMock(return_value=True)
    mock.guided_takeoff_async = AsyncMock(return_value=True)
    # Mock sync methods
    mock.connect = MagicMock()
    mock.request_data_stream = MagicMock()
    mock.start_mission = MagicMock()
    mock.handle_command_ack = MagicMock()
    mock.get_next_message = MagicMock(return_value=None)  # No messages by default
    return mock

@pytest.fixture
def mock_mqtt():
    mock = MagicMock()
    mock.connect = MagicMock()
    mock.subscribe_command = MagicMock()
    mock.subscribe_mission = MagicMock()
    mock.publish_telemetry = MagicMock()
    mock.publish_status = MagicMock()
    return mock

@pytest.fixture
def mock_mission_manager():
    mock = MagicMock()
    mock.on_mavlink_message = MagicMock()
    mock.upload_mission = MagicMock()
    return mock

@pytest.fixture
def bridge(mock_mavlink, mock_mqtt, mock_mission_manager):
    return CloudBridge(mock_mavlink, mock_mqtt, mock_mission_manager)


@pytest.mark.asyncio
async def test_telemetry_loop_global_position(bridge, mock_mavlink, mock_mqtt):
    """Test that telemetry loop processes GLOBAL_POSITION_INT messages"""
    # Setup - Create a mock MAVLink message
    msg = MagicMock()
    msg.get_type.return_value = 'GLOBAL_POSITION_INT'
    msg.lat = -35363261
    msg.lon = 149.165230
    msg.alt = 10000
    msg.relative_alt = 5000
    msg.vx = 10
    msg.vy = 20
    msg.vz = 30
    msg.hdg = 18000

    # Configure get_next_message to return message once, then None
    call_count = 0
    def get_next_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return msg
        bridge.running = False  # Stop after one message
        return None
    
    mock_mavlink.get_next_message.side_effect = get_next_side_effect
    bridge.running = True
    
    # Run telemetry loop for one iteration
    await bridge.telemetry_loop()
    
    # Verify telemetry was published
    mock_mqtt.publish_telemetry.assert_called_once()


@pytest.mark.asyncio
async def test_command_received_arm(bridge, mock_mavlink):
    """Test ARM command execution"""
    cmd_data = {'command': 'ARM'}
    await bridge.on_command_received(cmd_data)
    mock_mavlink.arm_async.assert_called_once()

@pytest.mark.asyncio
async def test_command_received_takeoff(bridge, mock_mavlink):
    """Test TAKEOFF command execution"""
    cmd_data = {'command': 'TAKEOFF', 'params': [50]}
    await bridge.on_command_received(cmd_data)
    mock_mavlink.guided_takeoff_async.assert_called_once_with(50)


def test_mission_received(bridge, mock_mission_manager):
    """Test mission plan reception"""
    mission_data = {'mission_id': 'test-001', 'waypoints': []}
    bridge.on_mission_received(mission_data)
    mock_mission_manager.upload_mission.assert_called_once_with(mission_data)


@pytest.mark.asyncio
async def test_mission_forwarding(bridge, mock_mavlink, mock_mission_manager):
    """Test that MISSION_REQUEST messages are forwarded to MissionManager"""
    # Setup mission request message
    msg = MagicMock()
    msg.get_type.return_value = 'MISSION_REQUEST'
    
    # Configure get_next_message
    call_count = 0
    def get_next_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return msg
        bridge.running = False
        return None
    
    mock_mavlink.get_next_message.side_effect = get_next_side_effect
    bridge.running = True
    
    # Run telemetry loop
    await bridge.telemetry_loop()
    
    # Verify message was forwarded
    mock_mission_manager.on_mavlink_message.assert_called_once_with(msg)
