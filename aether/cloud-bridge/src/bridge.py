import logging
import threading
from .mavlink import MavlinkConnection
from .mavlink import MavlinkConnection
from pymavlink import mavutil

logger = logging.getLogger(__name__)

class CloudBridge:
    def __init__(self, mavlink: MavlinkConnection, mqtt, mission_manager=None):
        self.mavlink = mavlink
        self.mqtt = mqtt
        self.mission_manager = mission_manager
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
                 # Also subscribe to Mission Plan topic
                 if self.mission_manager:
                     # Assuming mqtt has a generic subscribe method or we add a specific one
                     # For now, let's assume we can reuse subscribe_command or add subscribe_mission
                     # But checking mqtt.py, it likely only has subscribe_command.
                     # We should add subscribe_topic to mqtt.py or just use subscribe_command logic.
                     # However, to be clean, let's assume we add subscribe_mission to mqtt.py later
                     # or use a generic one. 
                     # Let's rely on mqtt.py having generic features or just add a new method.
                     # Since I can't see mqtt.py right now, I'll assume subscribe_command takes a topic?
                     # No, previous usage imply it defaults to a command topic.
                     
                     # Let's add subscription to mission topic. 
                     # We need to update MQTT class too for this.
                     # For now, let's call self.mqtt.subscribe_mission(self.on_mission_received)
                     # expecting we add it.
                     if hasattr(self.mqtt, 'subscribe_mission'):
                        self.mqtt.subscribe_mission(self.on_mission_received)
                     else:
                        logger.warning("MQTT class does not have subscribe_mission method.")

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

            # Forward mission messages to MissionManager
            if self.mission_manager and msg_type in ['MISSION_REQUEST', 'MISSION_ACK', 'MISSION_ITEM_REACHED']:
                self.mission_manager.on_mavlink_message(msg)
            
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
            self.mavlink.guided_takeoff(alt)
        elif cmd == 'START_MISSION':
            self.mavlink.start_mission()
        else:
            logger.warning(f"Unknown command: {cmd}")


    def on_mission_received(self, mission_plan: dict):
        """Handler for incoming mission plan JSON."""
        logger.info("Received Mission Plan.")
        if self.mission_manager:
            try:
                self.mission_manager.upload_mission(mission_plan)
                logger.info("Mission Plan uploaded successfully.")
            except Exception as e:
                logger.error(f"Failed to upload mission: {e}")
        else:
            logger.warning("Received Mission Plan but no MissionManager configured.")

