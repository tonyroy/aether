import logging
from pymavlink import mavutil

logger = logging.getLogger(__name__)

class MissionItem:
    """Simple container to match MAVLink structure for testing."""
    def __init__(self, command, x, y, z, param1=0):
        self.command = command
        self.x = x
        self.y = y
        self.z = z
        self.param1 = param1

class MissionManager:
    def __init__(self, mavlink_connection):
        self.mavlink = mavlink_connection

    def convert_plan_to_items(self, plan):
        """Converts JSON MissionPlan to MAVLink Mission Items."""
        items = []
        waypoints = plan.get('waypoints', [])
        
        for wp in waypoints:
            # MAV_CMD_NAV_WAYPOINT = 16
            item = MissionItem(
                command=16,
                x=wp['lat'],
                y=wp['lon'],
                z=wp['alt'],
                param1=wp.get('hold_time', 0)
            )
            items.append(item)
            
        return items

    def convert_fence_to_items(self, plan):
        """Converts JSON Fence to MAVLink Fence Items."""
        items = []
        fence = plan.get('fence', {})
        if not fence.get('enabled', False) and not fence.get('polygon'):
             return items

        polygon = fence.get('polygon', [])
        for vertex in polygon:
             # MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION = 5001
             item = MissionItem(
                 command=5001,
                 x=vertex['lat'],
                 y=vertex['lon'],
                 z=0, # Not used for vertex inclusion usually
                 param1=len(polygon) # Count is often required
             )
             items.append(item)
        return items

    def convert_rally_to_items(self, plan):
        """Converts JSON Rally Points to MAVLink Rally Items."""
        items = []
        rally_points = plan.get('rally_points', [])
        for rp in rally_points:
             # MAV_CMD_NAV_RALLY_POINT = 5100
             item = MissionItem(
                 command=5100,
                 x=rp['lat'],
                 y=rp['lon'],
                 z=rp['alt'],
                 param1=0
             )
             items.append(item)
        return items

    def _upload_list(self, items, mission_type):
        """Helper to upload a list of items of a specific type."""
        count = len(items)
        if count == 0:
            return

        logger.info(f"Uploading {count} items for type {mission_type}...")
        
        self.mavlink.mav.mission_count_send(
            self.mavlink.target_system,
            self.mavlink.target_component,
            count,
            mission_type
        )
        # Note: In real implementation, we would wait for MISSION_REQUEST
        # and send items one by one. For this prototype, we just send COUNT.

    def upload_mission(self, plan):
        """Orchestrates mission upload for all types."""
        # 1. Waypoints (Type 0)
        mission_items = self.convert_plan_to_items(plan)
        self._upload_list(mission_items, 0) # MAV_MISSION_TYPE_MISSION

        # 2. Fence (Type 1)
        fence_items = self.convert_fence_to_items(plan)
        self._upload_list(fence_items, 1) # MAV_MISSION_TYPE_FENCE

        # 3. Rally Points (Type 2 = MAV_MISSION_TYPE_RALLY)
        rally_items = self.convert_rally_to_items(plan)
        self._upload_list(rally_items, 2)


