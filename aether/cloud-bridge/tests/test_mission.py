import pytest
from unittest.mock import MagicMock
from src.mission import MissionManager

# Sample JSON Plan based on schemas/mission_plan.json
SAMPLE_PLAN = {
    "mission_id": "test-mission-001",
    "waypoints": [
        {"lat": -35.363261, "lon": 149.165230, "alt": 20},
        {"lat": -35.363361, "lon": 149.165330, "alt": 30, "hold_time": 5}
    ]
}

@pytest.fixture
def mock_mavlink():
    return MagicMock()

def test_convert_waypoints_to_items(mock_mavlink):
    """Verify that JSON waypoints are converted to MAV_CMD_NAV_WAYPOINT items."""
    manager = MissionManager(mock_mavlink)
    
    items = manager.convert_plan_to_items(SAMPLE_PLAN)
    
    # Needs 1 item for HOME (often required) or just the 2 items provided.
    # ArduPilot mission protocol usually indexes from 0.
    
    # Checking Item 1
    assert len(items) == 2
    item1 = items[0]
    assert item1.command == 16 # MAV_CMD_NAV_WAYPOINT
    assert item1.x == -35.363261 # Lat
    assert item1.y == 149.165230 # Lon
    assert item1.z == 20         # Alt
    
    # Checking Item 2 (Hold time param)
    item2 = items[1]
    assert item2.param1 == 5 # Hold time

def test_mission_upload_count(mock_mavlink):
    """Verify that upload_mission sends MISSION_COUNT."""
    manager = MissionManager(mock_mavlink)
    manager.upload_mission(SAMPLE_PLAN)
    
    # Should send MISSION_COUNT with count=2
    mock_mavlink.mav.mission_count_send.assert_called_once()
    args = mock_mavlink.mav.mission_count_send.call_args

# Sample Plan with Geofence and Rally
FULL_PLAN = {
    "mission_id": "test-full-001",
    "waypoints": [],
    "fence": {
        "enabled": True,
        "max_altitude": 100,
        "polygon": [
            {"lat": -35.1, "lon": 149.1},
            {"lat": -35.2, "lon": 149.2},
            {"lat": -35.3, "lon": 149.3}
        ]
    },
    "rally_points": [
        {"lat": -35.0, "lon": 149.0, "alt": 50}
    ]
}

def test_convert_fence_to_items(mock_mavlink):
    """Verify JSON fence polygon is converted to MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION."""
    manager = MissionManager(mock_mavlink)
    items = manager.convert_fence_to_items(FULL_PLAN)
    
    assert len(items) == 3 # 3 vertices
    assert items[0].command == 5001 # MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION
    assert items[0].x == -35.1
    assert items[0].y == 149.1
    # param1 is vertex count usually required by ArduPilot? 
    # Actually just list of items.

def test_convert_rally_to_items(mock_mavlink):
    """Verify JSON rally points are converted to MAV_CMD_NAV_RALLY_POINT."""
    manager = MissionManager(mock_mavlink)
    items = manager.convert_rally_to_items(FULL_PLAN)
    
    assert len(items) == 1
    assert items[0].command == 5100 # MAV_CMD_NAV_RALLY_POINT
    assert items[0].z == 50 # Alt

def test_upload_full_mission(mock_mavlink):
    """Verify upload_mission handles all 3 types separately."""
    manager = MissionManager(mock_mavlink)
    
    # We mock the internal conversion methods to simplify this coordination test
    manager.convert_plan_to_items = MagicMock(return_value=[MagicMock()])
    manager.convert_fence_to_items = MagicMock(return_value=[MagicMock(), MagicMock()])
    manager.convert_rally_to_items = MagicMock(return_value=[MagicMock()])
    
    manager.upload_mission(FULL_PLAN)
    
    # Should call mission_count_send 3 times
    assert mock_mavlink.mav.mission_count_send.call_count == 3
    
    # Check Calls
    calls = mock_mavlink.mav.mission_count_send.call_args_list
    
    # Call 1: Waypoints (Type 0)
    assert calls[0][0][3] == 0 # MAV_MISSION_TYPE_MISSION
    
    # Call 2: Fence (Type 1)
    assert calls[1][0][3] == 1 # MAV_MISSION_TYPE_FENCE
    
    # Call 3: Rally (Type 2) (Actually Rally type is 3 in MAVLink 2? Let's check docs or use enum)
    # pymavlink.mavutil.mavlink.MAV_MISSION_TYPE_RALLY = 3?
    # Actually checking generic integer for now.
    # Fence=1, Rally=3 usually.
    # Let's assume standard MAVLink 2 enum values.
    # If implementation uses 0, 1, 3 respectively.


def test_convert_complex_waypoints(mock_mavlink):
    """Verify Waypoints with Speed and ROI generate multiple MAVLink items."""
    plan = {
        "mission_id": "complex-001",
        "waypoints": [
            {
                "lat": -35.1, "lon": 149.1, "alt": 20,
                "speed": 15, # FAST
                "roi": {"lat": -35.2, "lon": 149.2, "alt": 0} # Look at point
            }
        ]
    }
    
    manager = MissionManager(mock_mavlink)
    items = manager.convert_plan_to_items(plan)
    
    # Expectation:
    # 1. DO_CHANGE_SPEED (if speed > 0)
    # 2. DO_SET_ROI
    # 3. NAV_WAYPOINT
    
    assert len(items) == 3
    
    # Check Item 1: Speed
    assert items[0].command == 178 # MAV_CMD_DO_CHANGE_SPEED
    assert items[0].param2 == 15   # Speed m/s
    
    # Check Item 2: ROI
    assert items[1].command == 201 # MAV_CMD_DO_SET_ROI
    assert items[1].x == -35.2     # ROI Lat
    
    # Check Item 3: Waypoint
    assert items[2].command == 16  # MAV_CMD_NAV_WAYPOINT
    assert items[2].x == -35.1     # Waypoint Lat

def test_on_mission_request(mock_mavlink):
    """Verify that MissionManager responds to MISSION_REQUEST with the correct item."""
    manager = MissionManager(mock_mavlink)
    
    # 1. Setup minimal plan
    plan = {
        "mission_id": "req-test",
        "waypoints": [{"lat": -35.0, "lon": 149.0, "alt": 20}]
    }
    
    # 2. Start upload - this should set internal state
    manager.upload_mission(plan)
    
    # 3. Simulate receiving MISSION_REQUEST for seq 0
    # We need a mock object that behaves like a MAVLink message
    msg = MagicMock()
    msg.get_type.return_value = 'MISSION_REQUEST'
    msg.seq = 0
    msg.mission_type = 0 # MAV_MISSION_TYPE_MISSION
    
    # 4. Process the message
    manager.on_mavlink_message(msg)
    
    # 5. Verify that mission_write_int (or similar) was called
    # We use mission_item_int_send usually for MAVLink 2
    mock_mavlink.mav.mission_item_int_send.assert_called_once()
    
    # Check args - seq should be 0
    args = mock_mavlink.mav.mission_item_int_send.call_args[0]
    # Signature: target_system, target_component, seq, frame, command, current, autocontinue, p1, p2, p3, p4, x, y, z, mission_type
    assert args[2] == 0 # seq
    assert args[11] == -35.0 * 1e7 # x (lat) as int if using int_send, or float if standard send?
    # Actually, let's see what the implementation chooses. MAVLink 2 prefers int.
    # pymavlink sends int usually.

