import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt

from aether_common.detection import DetectorState, MissionDetector
from aether_common.telemetry import DroneState

# Configuration (Env vars in real life)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_SUB = "mav/#"
TOPIC_PUB_EVENT = "aether/events/mission_started"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StreamProcessor")

@dataclass
class DroneContext:
    drone_id: str
    detector_state: DetectorState = field(default_factory=DetectorState)
    firmware: Dict = field(default_factory=dict)
    params: Dict = field(default_factory=dict)
    last_mission_plan: Optional[Dict] = None # Keeping raw dict for simplicity or MissionPlan obj
    last_geofence: List[Dict] = field(default_factory=list)

class StreamProcessor:
    def __init__(self):
        self.client = mqtt.Client(client_id="aether_processor")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.drones: Dict[str, DroneContext] = {}

    def start(self):
        logger.info(f"Connecting to MQTT Broker {MQTT_BROKER}:{MQTT_PORT}...")
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"Connected to MQTT (rc={rc})")
        client.subscribe(TOPIC_SUB)
        logger.info(f"Subscribed to {TOPIC_SUB}")

    def on_message(self, client, userdata, msg):
        logger.info(f"Received message on {msg.topic}")
        try:
            topic = msg.topic.split('/')
            # Expected topic format: mav/{drone_id}/{type}/...
            if len(topic) < 3:
                return

            drone_id = topic[1]
            msg_type = topic[2]
            payload = json.loads(msg.payload.decode())

            if drone_id not in self.drones:
                self.drones[drone_id] = DroneContext(drone_id=drone_id)

            context = self.drones[drone_id]

            if msg_type == "telemetry":
                self.handle_telemetry(context, payload)
            elif msg_type == "context":
                self.handle_context(context, topic, payload)
            elif msg_type == "mission" and topic[3] == "detected":
                self.handle_mission_plan(context, payload)

        except Exception as e:
            logger.error(f"Error processing message on {msg.topic}: {e}", exc_info=True)

    def handle_context(self, context: DroneContext, topic_parts: List[str], payload: Dict):
        subtype = topic_parts[3] if len(topic_parts) > 3 else ""
        if subtype == "firmware":
            context.firmware = payload
            logger.info(f"[{context.drone_id}] Updated Firmware Context")
        elif subtype == "param":
            # payload = { param_id, param_value, ... }
            pid = payload.get("param_id")
            pval = payload.get("param_value")
            if pid:
                context.params[pid] = pval
                logger.debug(f"[{context.drone_id}] Updated Param {pid}={pval}")

    def handle_mission_plan(self, context: DroneContext, payload: Dict):
        context.last_mission_plan = payload
        logger.info(f"[{context.drone_id}] Captured Mission Plan")

    def handle_telemetry(self, context: DroneContext, payload: Dict):
        # Convert dict to DroneState
        # Handle Type Enum conversion safely
        # Handle Type Enum conversion safely
        # Map string back to Enum if needed
        # Use existing from_dict helper which handles Enum conversion
        sample = DroneState.from_dict(payload)

        # Run Detector
        new_state, event = MissionDetector.evaluate(context.detector_state, sample)

        if new_state.state_name != context.detector_state.state_name:
            logger.info(f"[{context.drone_id}] State Transition: {context.detector_state.state_name} -> {new_state.state_name}")

        context.detector_state = new_state

        if event == "MISSION_STARTED":
            self.publish_mission_started(context, sample)

    def publish_mission_started(self, context: DroneContext, trigger_sample: DroneState):
        logger.info(f"[{context.drone_id}] !!! MISSION STARTED !!! Emitting Enriched Event.")

        # Build Enriched Event
        event_payload = {
            "event_id": str(time.time()),
            "drone_id": context.drone_id,
            "timestamp": time.time(),
            "trigger": "MOVEMENT", # Could derive from Detector logic
            "start_location": {
                "lat": context.detector_state.start_sample.lat if context.detector_state.start_sample else 0,
                "lon": context.detector_state.start_sample.lon if context.detector_state.start_sample else 0,
                "alt": context.detector_state.start_sample.alt if context.detector_state.start_sample else 0
            },
            "context": {
                "firmware": context.firmware,
                "params": context.params,
                "geofence": context.last_geofence
            },
            "mission_plan": context.last_mission_plan
        }

        # Publish
        self.client.publish(TOPIC_PUB_EVENT, json.dumps(event_payload))
        logger.info(f"Published to {TOPIC_PUB_EVENT}")

if __name__ == "__main__":
    processor = StreamProcessor()
    try:
        processor.start()
    except KeyboardInterrupt:
        logger.info("Stopping...")
