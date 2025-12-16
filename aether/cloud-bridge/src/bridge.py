import asyncio
import logging

from aether_common.telemetry import DroneState

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

            # --- Flight Plan Sniffing (Passive) ---
            if msg_type == 'MISSION_ACK':
                # External upload completed? Triger download.
                # msg.type==0 means MA_MISSION_ACCEPTED
                if msg.type == 0:
                    logger.info("Mission Upload Detected (ACK). Triggering sync...")
                    self.mavlink.master.mav.mission_request_list_send(self.mavlink.master.target_system, self.mavlink.master.target_component)
                    self._mission_downloading = True
                    self._mission_expected_count = 0
                    self._mission_items = []

            elif msg_type == 'MISSION_COUNT':
                 if getattr(self, '_mission_downloading', False):
                     self._mission_expected_count = msg.count
                     self._mission_items = []
                     logger.info(f"Downloading Mission: {msg.count} items expected.")
                     if msg.count > 0:
                         self.mavlink.master.mav.mission_request_int_send(self.mavlink.master.target_system, self.mavlink.master.target_component, 0)
                     else:
                         self._mission_downloading = False # Empty mission

            elif msg_type == 'MISSION_ITEM_INT':
                if getattr(self, '_mission_downloading', False):
                    # Store item
                    item = {
                        "seq": msg.seq,
                        "command": msg.command,
                        "frame": msg.frame,
                        "param1": msg.param1,
                        "param2": msg.param2,
                        "param3": msg.param3,
                        "param4": msg.param4,
                        "x": msg.x / 1e7, # Lat
                        "y": msg.y / 1e7, # Lon
                        "z": msg.z        # Alt
                    }
                    self._mission_items.append(item)

                    if len(self._mission_items) < self._mission_expected_count:
                        # Request next
                        next_seq = len(self._mission_items)
                        self.mavlink.master.mav.mission_request_int_send(self.mavlink.master.target_system, self.mavlink.master.target_component, next_seq)
                    else:
                        # Complete!
                        self._mission_downloading = False
                        logger.info(f"Mission Download Complete ({len(self._mission_items)} items). Publishing...")

                        # Construct Payload (using dict for now to avoid importing generated MissionPlan explicitly in this loop context,
                        # though ideally we use it. We'll use dict to match existing pattern for simple publishing)
                        plan_payload = {
                            "mission_id": str(time.time()), # Simple ID
                            "timestamp": time.time(),
                            "waypoints": self._mission_items
                        }

                        if self.mqtt:
                            self.mqtt.publish_mission_plan(plan_payload)
                        else:
                            logger.info(f"Detected Plan: {plan_payload}")

            # Filter interesting messages
            if msg_type == 'GLOBAL_POSITION_INT':
                sample = DroneState(
                    type='GLOBAL_POSITION_INT',
                    timestamp=time.time(),
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
                payload['timestamp'] = time.time()

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
                sample = DroneState(
                    type='ATTITUDE',
                    timestamp=time.time(),
                    roll=msg.roll,
                    pitch=msg.pitch,
                    yaw=msg.yaw
                )
                payload = sample.to_dict()
                payload['timestamp'] = time.time()

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

                sample = DroneState(
                    type='HEARTBEAT',
                    timestamp=time.time(),
                    mode=mode_name,
                    armed=is_armed,
                    system_status=msg.system_status
                )
                payload = sample.to_dict()
                payload['timestamp'] = time.time()

                if self.mqtt:
                    self.mqtt.publish_telemetry(payload)
                else:
                    logger.info(f"Heartbeat: {payload}")

                shadow_state['mode'] = mode_name

                # Check for transition to ARMED
                # Store previous state in self if needed, buy for now simple edge detection
                if is_armed and hasattr(self, '_last_armed_state') and not self._last_armed_state:
                     logger.info("Drone ARMED - Triggering Context Refresh")
                     self.mavlink.request_home_position()
                     self.mavlink.request_autopilot_version() # [NEW] Fetch Version
                     # [NEW] Fetch Critical Params
                     for param in ["RTL_ALT", "FENCE_ACTION", "FENCE_ENABLE", "FLTMODE_CH"]:
                         self.mavlink.request_param(param)

                self._last_armed_state = is_armed
                shadow_state['armed'] = is_armed

            # --- Context Messages ---
            elif msg_type == 'AUTOPILOT_VERSION':
                # Parse and publish firmware context
                context = {
                    "flight_sw_version": msg.flight_sw_version,
                    "board_version": msg.board_version,
                    "flight_custom_version": bytes(msg.flight_custom_version).hex() # Git Hash usually
                }
                if self.mqtt:
                    self.mqtt.publish_context_firmware(context)
                else:
                    logger.info(f"Context (Firmware): {context}")

            elif msg_type == 'PARAM_VALUE':
                # Publish individual param updates
                param_id = msg.param_id
                param_value = msg.param_value
                context = {
                    "param_id": param_id,
                    "param_value": param_value,
                    "param_type": msg.param_type
                }
                if self.mqtt:
                    self.mqtt.publish_context_param(context)
                else:
                    logger.info(f"Context (Param): {param_id}={param_value}")

            elif msg_type == 'HOME_POSITION':
                sample = DroneState(
                    type='HOME_POSITION',
                    timestamp=time.time(),
                    lat=msg.latitude / 1e7,
                    lon=msg.longitude / 1e7,
                    alt=msg.altitude / 1000.0,
                    # We can put approach info in other fields if needed, or extend DroneState
                )
                payload = sample.to_dict()
                payload['timestamp'] = time.time()

                if self.mqtt:
                     self.mqtt.publish_telemetry(payload)
                else:
                     logger.info(f"Home Position: {payload}")

                shadow_state['home_position'] = {
                    'lat': sample.lat,
                    'lon': sample.lon,
                    'alt': sample.alt
                }

            elif msg_type == 'BATTERY_STATUS':
                sample = DroneState(
                    type='BATTERY_STATUS',
                    timestamp=time.time(),
                    voltage=msg.voltages[0] / 1000.0 if len(msg.voltages) > 0 else 0,
                    remaining=msg.battery_remaining
                )
                payload = sample.to_dict()
                payload['timestamp'] = time.time()

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
