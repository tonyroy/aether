import logging
import asyncio
from .mavlink import MavlinkConnection

logger = logging.getLogger(__name__)

class CloudBridge:
    def __init__(self, mavlink: MavlinkConnection, mqtt, mission_manager=None):
        self.mavlink = mavlink
        self.mqtt = mqtt
        self.mission_manager = mission_manager
        self.running = False

    async def start(self):
        """Start the bridge (async version)."""
        logger.info("Starting Cloud Bridge (async mode)...")
        self.running = True
        
        # Connect both ends
        self.mavlink.connect()
        self.mavlink.request_data_stream()
        
        if self.mqtt:
            try:
                self.mqtt.connect()
                self.mqtt.subscribe_command(self.on_command_received)
                if self.mission_manager:
                    self.mqtt.subscribe_mission(self.on_mission_received)
            except Exception as e:
                logger.error(f"MQTT connection or subscription failed: {e}")
        
        # Run telemetry loop
        await self.telemetry_loop()

    async def telemetry_loop(self):
        """Async telemetry processing loop."""
        logger.info("Starting async telemetry loop...")
        while self.running:
            msg = self.mavlink.get_next_message()
            
            if not msg:
                await asyncio.sleep(0.001)  # Yield control, prevent busy loop
                continue
            
            msg_type = msg.get_type()
            logger.debug(f"Received MAVLink message: {msg_type}")

            # Forward COMMAND_ACK to MAVLink layer for async command completion
            if msg_type == 'COMMAND_ACK':
                self.mavlink.handle_command_ack(msg)
                continue

            # Forward mission messages to MissionManager
            if self.mission_manager and msg_type in ['MISSION_REQUEST', 'MISSION_ACK', 'MISSION_ITEM_REACHED']:
                self.mission_manager.on_mavlink_message(msg)
            
            # Filter interesting messages
            if msg_type == 'GLOBAL_POSITION_INT':
                payload = {
                    'type': 'GLOBAL_POSITION_INT',
                    'lat': msg.lat / 1e7,
                    'lon': msg.lon / 1e7,
                    'alt': msg.alt / 1000.0,
                    'relative_alt': msg.relative_alt / 1000.0,
                    'vx': msg.vx / 100.0,
                    'vy': msg.vy / 100.0,
                    'vz': msg.vz / 100.0,
                    'hdg': msg.hdg / 100.0
                }
                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"[SIM] Position: {payload}")
            
            elif msg_type == 'ATTITUDE':
                payload = {
                    'type': 'ATTITUDE',
                    'roll': msg.roll,
                    'pitch': msg.pitch,
                    'yaw': msg.yaw
                }
                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"[SIM] Attitude: {payload}")
            
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

    async def on_command_received(self, command_data):
        """Handle incoming command asynchronously and publish status.
        
        Uses proper async/await for non-blocking command execution.
        """
        import time
        
        cmd = command_data.get('command')
        params = command_data.get('params', [])
        
        logger.info(f"Executing command: {cmd} with params {params}")
        
        # Execute command asynchronously with await
        success = False
        try:
            if cmd == 'ARM':
                success = await self.mavlink.arm_async()
            elif cmd == 'DISARM':
                success = await self.mavlink.disarm_async()
            elif cmd == 'TAKEOFF':
                alt = params[0] if len(params) > 0 else 10
                success = await self.mavlink.guided_takeoff_async(alt)
            elif cmd == 'RTL':
                success = await self.mavlink.rtl_async()
            elif cmd == 'LAND':
                success = await self.mavlink.land_async()
            elif cmd == 'START_MISSION':
                self.mavlink.start_mission()
                success = True
            else:
                logger.warning(f"Unknown command: {cmd}")
                success = False
        except Exception as e:
            logger.error(f"Command {cmd} failed with exception: {e}")
            success = False
        
        # Publish status
        status = {
            "command": cmd,
            "status": "success" if success else "failed",
            "timestamp": time.time()
        }
        
        if self.mqtt:
            self.mqtt.publish_status(status)
        
        logger.info(f"Command {cmd} {'succeeded' if success else 'failed'}")


    def on_mission_received(self, mission_plan: dict):
        logger.info("Received Mission Plan.")
        if self.mission_manager:
            self.mission_manager.upload_mission(mission_plan)
