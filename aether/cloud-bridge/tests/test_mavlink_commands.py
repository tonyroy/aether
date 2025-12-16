import pytest
from unittest.mock import MagicMock
from pymavlink import mavutil
from src.mavlink import MavlinkConnection

@pytest.fixture
def mavlink():
    # Instantiate without connecting (connection_string is dummy)
    m = MavlinkConnection("tcp:127.0.0.1:5760")
    # Mock the internal master object, which is usually created by pymavlink
    m.master = MagicMock()
    # Mock .mav attribute
    m.master.mav = MagicMock()
    # Mock target info
    m.master.target_system = 1
    m.master.target_component = 1
    
    return m

def test_request_home_position_sends_correct_command(mavlink):
    """
    Verify that request_home_position sends MAV_CMD_REQUEST_MESSAGE
    with ID 242 (HOME_POSITION).
    """
    mavlink.request_home_position()
    
    # Check that command_long_send was called
    mavlink.master.mav.command_long_send.assert_called_once()
    
    # Verify arguments
    args = mavlink.master.mav.command_long_send.call_args[0]
    # args: (target_system, target_component, command, confirmation, p1, p2, p3, p4, p5, p6, p7)
    
    assert args[2] == mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE # command
    assert args[4] == 242 # param1 (Message ID for HOME_POSITION)

def test_request_autopilot_version_sends_correct_command(mavlink):
    """
    Verify request_autopilot_version sends correct ID.
    """
    mavlink.request_autopilot_version()
    
    mavlink.master.mav.command_long_send.assert_called_once()
    args = mavlink.master.mav.command_long_send.call_args[0]
    assert args[2] == mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE
    assert args[4] == mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION

def test_request_param_sends_read_request(mavlink):
    """
    Verify request_param sends param_request_read_send.
    """
    mavlink.request_param("RTL_ALT")
    
    mavlink.master.mav.param_request_read_send.assert_called_once()
    args = mavlink.master.mav.param_request_read_send.call_args[0]
    # args: (target_system, target_component, param_id_bytes, param_index)
    assert args[2] == b"RTL_ALT"
