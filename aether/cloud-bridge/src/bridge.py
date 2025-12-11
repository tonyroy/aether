import logging
import asyncio
from typing import Optional
from .mavlink import MavlinkConnection
try:
    from aether_common.telemetry import TelemetrySample
except ImportError:
    # Fallback or error if common not installed
    pass

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
        """Async telemetry processing loop with Shadow sync."""
        import time
        logger.info("Starting async telemetry loop...")
        
        # State tracking for Shadow sync
        last_shadow_update = 0
        shadow_state = {}
        
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
                sample = TelemetrySample(
                    type='GLOBAL_POSITION_INT',
                    # timestamp will be defaulted or set if needed
                    lat=msg.lat / 1e7,
                    lon=msg.lon / 1e7,
                    alt=msg.alt / 1000.0,
                    relative_alt=msg.relative_alt / 1000.0,
                    vx=msg.vx / 100.0,
                    vy=msg.vy / 100.0,
                    vz=msg.vz / 100.0,
                    hdg=msg.hdg / 100.0
                )
                payload = sample.to_dict()

                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"Position: {payload}")
                
                # Track for Shadow
                shadow_state['position'] = {
                    'lat': sample.lat,
                    'lon': sample.lon,
                    'alt': sample.relative_alt
                }
            
            elif msg_type == 'ATTITUDE':
                sample = TelemetrySample(
                    type='ATTITUDE',
                    roll=msg.roll,
                    pitch=msg.pitch,
                    yaw=msg.yaw
                )
                payload = sample.to_dict()
                
                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"Attitude: {payload}")
            
            elif msg_type == 'HEARTBEAT':
                # Only process heartbeats from the autopilot (compid 1)
                if msg.get_srcComponent() != 1:
                    continue
                    
                mode_name = "UNKNOWN"
                if hasattr(self.mavlink.master, 'flightmode'):
                    mode_name = self.mavlink.master.flightmode
                
                is_armed = self.mavlink.master.motors_armed()
                
                sample = TelemetrySample(
                    type='HEARTBEAT',
                    mode=mode_name,
                    armed=is_armed,
                    system_status=msg.system_status
                )
                payload = sample.to_dict()

                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"Heartbeat: {payload}")
                
                shadow_state['mode'] = mode_name
                shadow_state['armed'] = is_armed
            
            elif msg_type == 'BATTERY_STATUS':
                sample = TelemetrySample(
                    type='BATTERY_STATUS',
                    voltage=msg.voltages[0] / 1000.0 if len(msg.voltages) > 0 else 0,
                    remaining=msg.battery_remaining
                )
                payload = sample.to_dict()

                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"Battery: {payload}")
                
                shadow_state['battery'] = msg.battery_remaining
            
            # Update Shadow every 5 seconds with critical state
            current_time = time.time()
            if current_time - last_shadow_update > 5 and shadow_state:
                if self.mqtt and hasattr(self.mqtt, 'sync_shadow'):
                    self.mqtt.sync_shadow(shadow_state)
                    logger.debug(f"Synced shadow: {shadow_state}")
                last_shadow_update = current_time

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


    async def on_mission_received(self, mission_data):
        """Handle incoming mission plan."""
        logger.info(f"Received mission plan with {len(mission_data.get('waypoints', []))} waypoints")
        
        if self.mission_manager:
            success = self.mission_manager.upload_mission(mission_data)
            if success:
                logger.info("Mission uploaded successfully")
            else:
                logger.error("Mission upload failed")
