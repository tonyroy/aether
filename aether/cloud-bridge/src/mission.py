import logging

from pymavlink import mavutil

logger = logging.getLogger(__name__)

class MissionItem:
    """Simple container to match MAVLink structure for testing."""
    def __init__(self, command, x, y, z, param1=0, param2=0, param3=0):
        self.command = command
        self.x = x
        self.y = y
        self.z = z
        self.param1 = param1
        self.param2 = param2
        self.param3 = param3

class MissionManager:
    def __init__(self, mavlink_connection):
        self.mavlink = mavlink_connection
        self.current_mission_items = {} # Map[mission_type] -> List[MissionItem]

    def convert_plan_to_items(self, plan):
        """Converts JSON MissionPlan to MAVLink Mission Items."""
        items = []
        waypoints = plan.get('waypoints', [])

        for wp in waypoints:
            # 1. OPTIONAL: Speed Change
            if 'speed' in wp:
                # MAV_CMD_DO_CHANGE_SPEED = 178
                # param1: Speed type (1=Ground Speed, 0=Airspeed)
                # param2: Speed (m/s)
                # param3: Throttle (-1=No Change)
                items.append(MissionItem(
                    command=178,
                    x=0, y=0, z=0,
                    param1=1, # Ground Speed
                    param2=wp['speed'],
                    param3=-1
                ))

            # 2. OPTIONAL: ROI (Region of Interest)
            if 'roi' in wp:
                roi = wp['roi']
                # MAV_CMD_DO_SET_ROI = 201
                # param1: ROI Mode (0=None, 1=Next, 2=Always, 3=Location, 4=WP Index)
                # We use Mode 3 or just standard Location param setting
                items.append(MissionItem(
                    command=201, # DO_SET_ROI
                    x=roi['lat'], # Lat
                    y=roi['lon'], # Lon
                    z=roi.get('alt', 0), # Alt
                    param1=0 # Param1 is actually ROI Mode in some versions, but usually 0 for Location
                ))

            # 3. REQUIRED: Waypoint or Command
            # Default to MAV_CMD_NAV_WAYPOINT (16)
            cmd = 16

            wp_type = wp.get('type', 'WAYPOINT')
            if wp_type == 'TAKEOFF':
                cmd = 22 # MAV_CMD_NAV_TAKEOFF
            elif wp_type == 'LAND':
                cmd = 21 # MAV_CMD_NAV_LAND
            elif wp_type == 'RTL':
                cmd = 20 # MAV_CMD_NAV_RETURN_TO_LAUNCH

            item = MissionItem(
                command=cmd,
                x=wp.get('lat', 0),
                y=wp.get('lon', 0),
                z=wp.get('alt', 0),
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

        # Store items for retrieval during handshake
        self.current_mission_items[mission_type] = items

        logger.info(f"Uploading {count} items for type {mission_type}...")

        self.mavlink.mav.mission_count_send(
            self.mavlink.target_system,
            self.mavlink.target_component,
            count,
            mission_type
        )

    def on_mavlink_message(self, msg):
        """Processes incoming MAVLink messages for mission protocol."""
        msg_type = msg.get_type()

        if msg_type == 'MISSION_REQUEST':
            # Handle request for specific item
            seq = msg.seq
            mission_type = getattr(msg, 'mission_type', 0) # Default to 0 if not present (MAVLink 1)

            items = self.current_mission_items.get(mission_type)
            if items and seq < len(items):
                item = items[seq]
                logger.debug(f"Sending MISSION_ITEM {seq} type {mission_type} command {item.command}")

                # Send item
                # Using mission_item_int_send for better precision
                self.mavlink.mav.mission_item_int_send(
                    self.mavlink.target_system,
                    self.mavlink.target_component,
                    seq,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    item.command,
                    0, # current (not used for upload)
                    1, # autocontinue
                    item.param1, item.param2, item.param3, 0, # p1-p4
                    int(item.x * 1e7), # lat (int)
                    int(item.y * 1e7), # lon (int)
                    item.z, # alt (float)
                    mission_type
                )
            else:
                logger.warning(f"Received MISSION_REQUEST for invalid seq {seq} or type {mission_type}")

    def upload_mission(self, plan):
        """Orchestrates mission upload for all types."""
        # Clear previous state
        self.current_mission_items = {}

        # 1. Waypoints (Type 0)
        mission_items = self.convert_plan_to_items(plan)
        self._upload_list(mission_items, 0) # MAV_MISSION_TYPE_MISSION

        # 2. Fence (Type 1)
        fence_items = self.convert_fence_to_items(plan)
        self._upload_list(fence_items, 1) # MAV_MISSION_TYPE_FENCE

        # 3. Rally Points (Type 2 = MAV_MISSION_TYPE_RALLY)
        rally_items = self.convert_rally_to_items(plan)
        self._upload_list(rally_items, 2)



