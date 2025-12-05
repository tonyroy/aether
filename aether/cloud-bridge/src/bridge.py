import logging
import threading
from .mavlink import MavlinkConnection
from .mavlink import MavlinkConnection
from pymavlink import mavutil

logger = logging.getLogger(__name__)

class CloudBridge:
    def __init__(self, mavlink: MavlinkConnection, mqtt):
        self.mavlink = mavlink
        self.mqtt = mqtt
        self.running = False

    def start(self):
        logger.info("Starting Cloud Bridge...")
        self.running = True

        # Connect both ends
        self.mavlink.connect()
        # Request telemetry explicitly
        self.mavlink.request_data_stream()
        
        if self.mqtt:
            try:
                 self.mqtt.connect()
                 self.mqtt.subscribe_command(self.on_command_received)
            except Exception as e:
                logger.error(f"Failed to connect to AWS IoT: {e}. Bridge will run in telemetry-only mode (logging locally).")
                self.mqtt = None
        else:
            logger.info("No MQTT connection configured. Running in local Sim-Only mode.")

        # Start telemetry loop
        self.telemetry_loop()

    def telemetry_loop(self):
        logger.info("Starting telemetry loop...")
        for msg in self.mavlink.get_messages():
            if not self.running:
                break
            
            msg_type = msg.get_type()
            logger.debug(f"Received MAVLink message: {msg_type}")
            
            # Filter interesting messages
            if msg_type == 'GLOBAL_POSITION_INT':
                payload = {
                    'type': 'GLOBAL_POSITION_INT',
                    'lat': msg.lat / 1e7,
                    'lon': msg.lon / 1e7,
                    'alt': msg.alt / 1000.0, # mm to m
                    'relative_alt': msg.relative_alt / 1000.0,
                    'vx': msg.vx / 100.0,
                    'vy': msg.vy / 100.0,
                    'vz': msg.vz / 100.0,
                    'hdg': msg.hdg / 100.0
                }
                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"[SIM] Telemetry: {payload}")
            
            elif msg_type == 'ATTITUDE':
                payload = {
                    'type': 'ATTITUDE',
                    'roll': msg.roll,
                    'pitch': msg.pitch,
                    'yaw': msg.yaw
                }
                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                # Reduce log spam for high freq attitude
            
            elif msg_type == 'BATTERY_STATUS':
                payload = {
                    'type': 'BATTERY_STATUS',
                    'voltage': msg.voltages[0] / 1000.0 if len(msg.voltages) > 0 else 0,
                    'remaining': msg.battery_remaining
                }
                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"[SIM] Battery: {payload}")

    def on_command_received(self, command_data):
        cmd = command_data.get('command')
        params = command_data.get('params', [])
        
        logger.info(f"Executing command: {cmd} with params {params}")
        
        if cmd == 'ARM':
            self.mavlink.arm()
        elif cmd == 'DISARM':
            self.mavlink.disarm()
        elif cmd == 'TAKEOFF':
            alt = params[0] if len(params) > 0 else 10
            self.mavlink.takeoff(alt)
        # Add more generic command handlers here
        else:
            logger.warning(f"Unknown command: {cmd}")
