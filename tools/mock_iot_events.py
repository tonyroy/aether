import asyncio
import json
import logging
import math
import time
from dataclasses import asdict
from typing import Dict, Optional

from temporalio import workflow
from temporalio.client import Client
import paho.mqtt.client as mqtt

# Reuse existing schema/logic where possible
from aether_common.telemetry import TelemetrySample

# If we can't import this easily from tools, we'll redefine or fix path
# For now, assuming virtualenv has aether-common installed
# We might need to copy logical distance calc or import it

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_iot_events")

# Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TEMPORAL_HOST = "localhost:7233"

# Detection Config
MIN_DURATION_SEC = 30
MIN_DISTANCE_M = 10

from aether_common.detection import MissionDetector, DetectorState

class DroneStateWrapper:
    """Wrapper to hold state for the shared detector logic."""
    def __init__(self, drone_id):
        self.drone_id = drone_id
        self.state = DetectorState() # Initial IDLE

    def process(self, sample: TelemetrySample) -> bool:
        """
        Delegates checking to MissionDetector pure logic.
        Returns True if MISSION_STARTED event occurred.
        """
        new_state, event = MissionDetector.evaluate(self.state, sample)
        
        # Log transitions
        if new_state.state_name != self.state.state_name:
            logger.info(f"{self.drone_id}: State Change {self.state.state_name} -> {new_state.state_name}")
            
        self.state = new_state
        
        if event == "MISSION_STARTED":
            logger.info(f"{self.drone_id}: ===> MISSION CONFIRMED <===")
            return True
        elif event == "MISSION_ENDED":
             logger.info(f"{self.drone_id}: Mission Ended")
             
        return False
        
    @property
    def start_sample(self):
        return self.state.start_sample

async def main():
    # 1. Connect to Temporal
    try:
        temporal_client = await Client.connect(TEMPORAL_HOST)
        logger.info(f"Connected to Temporal at {TEMPORAL_HOST}")
    except Exception as e:
        logger.error(f"Failed to connect to Temporal: {e}")
        return

    # 2. State Cache
    drone_states: Dict[str, DroneStateWrapper] = {}

    # 3. MQTT Handler
    def on_connect(client, userdata, flags, rc):
        logger.info(f"Connected to MQTT broker (rc={rc})")
        client.subscribe("mav/+/telemetry")

    def on_message(client, userdata, msg):
        try:
            # Topic: mav/{drone_id}/telemetry
            drone_id = msg.topic.split('/')[1]
            payload = json.loads(msg.payload)
            
            # Use shared model
            sample = TelemetrySample.from_dict(payload)
            if not sample.timestamp: 
                sample.timestamp = time.time()
            
            # Update State
            if drone_id not in drone_states:
                drone_states[drone_id] = DroneStateWrapper(drone_id)
            
            detector = drone_states[drone_id]
            mission_detected = detector.process(sample)
            
            # 4. Signal Temporal if Detected
            if mission_detected:
                asyncio.run_coroutine_threadsafe(
                    signal_workflow(temporal_client, drone_id, detector.start_sample),
                    loop
                )

        except Exception as e:
            logger.error(f"Error processing Msg: {e}")

    async def signal_workflow(client, drone_id, start_sample):
        try:
            handle = client.get_workflow_handle(f"entity-{drone_id}")
            # We use a NEW signal for this prototype: 'external_mission_start'
            # Or we can reuse 'assign_mission' but that expects a plan.
            # Let's assume we reuse signal_telemetry but with a rigorous flag?
            # Or better: The User wants to SEE the decouple.
            # Let's signal 'signal_mission_detected' (needs adding to Workflow, or just reuse signal_telemetry logic for now)
            
            # For immediate gratification without changing workflow code:
            # We just LOG it here. The user wants to "test" the architecture.
            logger.info(f"===> SIGNALING TEMPORAL: MISSION START for {drone_id} <===")
            
            # Implementation:
            # await handle.signal("mission_detected", {"start_time": start_sample.timestamp})
            
        except Exception as e:
            logger.error(f"Failed to signal: {e}")

    # 5. Start MQTT
    client = mqtt.Client(client_id="mock_iot_events_service")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
         logger.error(f"Could not connect to MQTT (is Mosquitto running?): {e}")
         return

    # Loop
    client.loop_start()
    
    logger.info("Mock IoT Events Detector is running. Press Ctrl+C to stop.")
    
    # Keep Async Loop Alive
    global loop
    loop = asyncio.get_running_loop()
    
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        client.loop_stop()

if __name__ == "__main__":
    asyncio.run(main())
