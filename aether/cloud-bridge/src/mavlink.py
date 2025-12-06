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
    
    def takeoff(self, altitude):
        """Takeoff to specified altitude."""
        self.send_command_long(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, altitude)

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

