import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, call
from src.bridge import CloudBridge

@pytest.fixture
def mock_mavlink():
    mock = MagicMock()
    mock.request_home_position = MagicMock()
    mock.request_autopilot_version = MagicMock()
    mock.request_param = MagicMock()
    # Mock master methods
    mock.master = MagicMock()
    mock.master.motors_armed.return_value = False
    mock.master.target_system = 1
    mock.master.target_component = 1
    # Mock message loop
    mock.get_next_message = MagicMock(return_value=None)
    return mock

@pytest.fixture
def mock_mqtt():
    mock = MagicMock()
    mock.publish_telemetry = MagicMock()
    mock.publish_mission_plan = MagicMock()
    mock.publish_context_firmware = MagicMock()
    mock.publish_context_param = MagicMock()
    mock.client_id = "test-drone-1" # Ensure client_id is set
    return mock

@pytest.fixture
def bridge(mock_mavlink, mock_mqtt):
    b = CloudBridge(mock_mavlink, mock_mqtt)
    return b

@pytest.mark.asyncio
async def test_arming_triggers_context_fetch(bridge, mock_mavlink):
    """Test that transitioning from Disarmed to Armed triggers context fetch."""
    
    # 1. Setup HEARTBEAT message (Armed=True)
    msg = MagicMock()
    msg.get_type.return_value = 'HEARTBEAT'
    msg.get_srcComponent.return_value = 1
    msg.system_status = 0
    # ensure motors_armed returns True when asked
    mock_mavlink.master.motors_armed.return_value = True

    # 2. Configure Bridge State
    bridge.running = True
    bridge._last_armed_state = False # Simulating transition

    # 3. Message Sequence: Heartbeat -> Stop
    call_count = 0
    def side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return msg
        bridge.running = False
        return None
    mock_mavlink.get_next_message.side_effect = side_effect

    # 4. Run Loop
    await bridge.telemetry_loop()

    # 5. Verify Context Requests
    mock_mavlink.request_autopilot_version.assert_called_once()
    mock_mavlink.request_param.assert_any_call("RTL_ALT")
    mock_mavlink.request_param.assert_any_call("FENCE_ACTION")

@pytest.mark.asyncio
async def test_autopilot_version_publishing_delegated(bridge, mock_mavlink, mock_mqtt):
    """Test that AUTOPILOT_VERSION messages use the new delegated publish method."""
    
    msg = MagicMock()
    msg.get_type.return_value = 'AUTOPILOT_VERSION'
    msg.flight_sw_version = 12345
    msg.board_version = 1
    msg.flight_custom_version = [0] * 8 

    # Mock Loop
    bridge.running = True
    call_count = 0
    def side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return msg
        bridge.running = False
        return None
    mock_mavlink.get_next_message.side_effect = side_effect

    await bridge.telemetry_loop()

    # Verify mqtt.publish_context_firmware called
    mock_mqtt.publish_context_firmware.assert_called_once()
    # Ensure raw publish_topic was NOT called for this
    # (Note: publish_topic exists on mock but shouldn't be called for this type)
    # Actually mock_mqtt doesn't have publish_topic unless we added it to fixture, which we didn't.
    # So if code called publish_topic, it would be a failure if we restricted mock, but here we just check positive case.

@pytest.mark.asyncio
async def test_param_value_publishing_delegated(bridge, mock_mavlink, mock_mqtt):
    """Test that PARAM_VALUE messages use delegated publish."""
    
    msg = MagicMock()
    msg.get_type.return_value = 'PARAM_VALUE'
    msg.param_id = "RTL_ALT"
    msg.param_value = 1500.0
    msg.param_type = 9

    bridge.running = True
    mock_mavlink.get_next_message.side_effect = [msg, None]
    
    # We need to manually stop loop if it gets None and continues or simple None logic
    # The loop usually waits on None? No, code has sleep(0.001) continue.
    # So we need side_effect to toggle running=False
    def side_effect():
        bridge.running = False
        return msg
    mock_mavlink.get_next_message.side_effect = side_effect

    await bridge.telemetry_loop()

    mock_mqtt.publish_context_param.assert_called_once()
    args = mock_mqtt.publish_context_param.call_args[0][0]
    assert args['param_id'] == "RTL_ALT"
    assert args['param_value'] == 1500.0
