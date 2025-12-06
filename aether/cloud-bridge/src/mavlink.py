import os
import time
import json
import logging
from pymavlink import mavutil

logger = logging.getLogger(__name__)

class MavlinkConnection:
    def __init__(self, connection_string, baudrate=57600):
        self.connection_string = connection_string
        self.baudrate = baudrate
        self.master = None
        self.connected = False

    def connect(self):
        logger.info(f"Connecting to MAVLink on {self.connection_string}...")
        while not self.connected:
            try:
                self.master = mavutil.mavlink_connection(self.connection_string, baud=self.baudrate)
                logger.info(f"Connected to {self.connection_string}. Waiting for heartbeat...")
                self.master.wait_heartbeat()
                self.connected = True
                logger.info(f"Heartbeat received from system {self.master.target_system} component {self.master.target_component}")
            except Exception as e:
                logger.error(f"Failed to connect to MAVLink: {e}. Retrying in 5s...")
                time.sleep(5)

    def get_messages(self):
        """Yields MAVLink messages as they arrive."""
        if not self.master:
            raise RuntimeError("MAVLink not connected")
        
        while True:
            msg = self.master.recv_match(blocking=True)
            if msg:
                yield msg

    @property
    def mav(self):
        if self.master:
            return self.master.mav
        return None

    @property
    def target_system(self):
        if self.master:
            return self.master.target_system
        return 0

    @property
    def target_component(self):
        if self.master:
            return self.master.target_component
        return 0


    def send_command_long(self, command, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
        """Sends a COMMAND_LONG message."""
        if not self.master:
            logger.warning("MAVLink not connected, cannot send command")
            return

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            command,
            0, # Confirmation
            param1, param2, param3, param4, param5, param6, param7
        )
        logger.info(f"Sent COMMAND_LONG {command}")

    def arm(self):
        """Arms the drone."""
        self.send_command_long(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)

    def disarm(self):
        """Disarms the drone."""
        self.send_command_long(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0)

    def set_mode(self, mode):
        """Set flight mode (e.g., 'GUIDED', 'AUTO', 'STABILIZE')."""
        if not self.master:
            raise RuntimeError("MAVLink not connected")
        
        # Get mode number from string
        mode_mapping = self.master.mode_mapping()
        if mode.upper() not in mode_mapping:
            raise ValueError(f"Unknown mode: {mode}. Available: {list(mode_mapping.keys())}")
        
        mode_id = mode_mapping[mode.upper()]
        self.master.set_mode(mode_id)
        logger.info(f"Set mode to {mode.upper()}")

    def guided_takeoff(self, altitude):
        """Simple takeoff in GUIDED mode (like MAVProxy 'takeoff' command).
        
        This is the recommended method for simple takeoff operations.
        Automatically switches to GUIDED mode, arms, and takes off.
        """
        # Switch to GUIDED mode
        self.set_mode('GUIDED')
        
        # Arm
        self.arm()
        
        # Send simple takeoff command (works in GUIDED mode)
        # In GUIDED mode, ArduCopter accepts simple parameters
        self.send_command_long(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,        # param1: pitch (ignored for copter)
            0,        # param2: empty
            0,        # param3: empty
            0,        # param4: yaw (0 = current)
            0,        # param5: lat (0 = current in GUIDED)
            0,        # param6: lon (0 = current in GUIDED)
            altitude  # param7: altitude
        )
        logger.info(f"Initiated GUIDED takeoff to {altitude}m")
    
    def takeoff(self, altitude):
        """Takeoff to specified altitude at current position (for mission use).
        
        This version uses NaN for lat/lon to explicitly indicate current position.
        Use guided_takeoff() for simple interactive takeoff operations.
        """
        # MAV_CMD_NAV_TAKEOFF parameters:
        # param1: Minimum pitch (copter: ignored)
        # param2: Empty
        # param3: Empty
        # param4: Yaw angle (NaN = use current yaw)
        # param5: Latitude (NaN = current position)
        # param6: Longitude (NaN = current position)
        # param7: Altitude (meters)
        import math
        self.send_command_long(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,              # param1: pitch (ignored for copter)
            0,              # param2: empty
            0,              # param3: empty
            math.nan,       # param4: yaw (NaN = current)
            math.nan,       # param5: lat (NaN = current position)
            math.nan,       # param6: lon (NaN = current position)
            altitude        # param7: altitude
        )

    def request_data_stream(self):
        """Requests data streams from the autopilot."""
        if not self.master:
            return
        
        # Request all data streams at 2 Hz
        # MAV_DATA_STREAM_ALL = 0
        self.master.mav.request_data_stream_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            2, # Rate in Hz
            1  # Start (1 to start, 0 to stop)
        )
        logger.info("Requested all data streams at 2Hz")

    def start_mission(self):
        """Starts the mission (switches to AUTO mode or sends MISSION_START)."""
        # Option A: MAV_CMD_MISSION_START (300)
        self.send_command_long(mavutil.mavlink.MAV_CMD_MISSION_START, 0, 0)
        # Option B: Set Mode to AUTO (often more robust for straight mission start)
        # But MAV_CMD_MISSION_START is the precise command.
        # Let's also ensure we arm? No, separate command.


