import asyncio
import json
import logging
import os

import activities

# Import artifacts
from activities import send_command, wait_for_telemetry
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

# Load environment variables
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker
from workflows import MissionWorkflow

load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mqtt_connection():
    endpoint = os.getenv("IOT_ENDPOINT")
    cert_path = os.getenv("IOT_CERT")
    key_path = os.getenv("IOT_KEY")
    root_ca_path = os.getenv("IOT_ROOT_CA")
    client_id = "orchestrator"

    if not all([endpoint, cert_path, key_path, root_ca_path]):
        logger.warning("AWS IoT credentials not fully configured. MQTT will definitely fail.")
        # We might want to exit or retry, but let's try to connect only if configured
        if not endpoint:
            return None

    logger.info(f"Connecting to AWS IoT at {endpoint}...")
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath=cert_path,
        pri_key_filepath=key_path,
        client_bootstrap=client_bootstrap,
        ca_filepath=root_ca_path,
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=6
    )

    connect_future = mqtt_connection.connect()
    connect_future.result()
    logger.info("Connected to AWS IoT!")
    return mqtt_connection

async def main():
    logger.info("Starting Orchestrator Worker...")

    # 1. Connect to AWS IoT
    try:
        activities.mqtt_connection = create_mqtt_connection()
    except Exception as e:
        logger.error(f"Failed to connect to AWS IoT: {e}")
        # Depending on resilience requirements, we might want to retry loop here

    # 2. Connect to Temporal Service
    temporal_host = os.getenv("TEMPORAL_SERVICE_ADDRESS", "temporal:7233")
    logger.info(f"Connecting to Temporal at {temporal_host}...")

    # Wait for temporal to be ready
    while True:
        try:
            client = await Client.connect(temporal_host)
            break
        except Exception as e:
            logger.warning(f"Waiting for Temporal... {e}")
            await asyncio.sleep(2)

    logger.info("Connected to Temporal Server")

    # 3. Create Worker
    from activities import update_shadow_status

    # 3. Create Worker
    from workflows import DroneEntityWorkflow, SessionRecordingWorkflow

    worker = Worker(
        client,
        task_queue="mission-queue",
        workflows=[MissionWorkflow, DroneEntityWorkflow, SessionRecordingWorkflow],
        activities=[send_command, wait_for_telemetry, update_shadow_status],
    )

    # 4. Subscribe to Telemetry (Ingestor Role)
    # 4. Subscribe to Telemetry (Ingestor Role)
    # 4. Subscribe to Telemetry (Ingestor Role)
    if activities.mqtt_connection:
        logger.info("Subscribing to 'mav/+/telemetry'...")

        # Capture the main loop to bridge threads
        main_loop = asyncio.get_running_loop()

        # Cache for Drone State to implement suppression
        # {drone_id: {'armed': bool, 'last_signal_time': float}}
        drone_states = {}

        def on_telemetry(topic, payload, dup, qos, retain, **kwargs):
            try:
                # Topic format: mav/{drone_id}/telemetry
                parts = topic.split('/')
                if len(parts) >= 3:
                     drone_id = parts[1]
                     data = json.loads(payload.decode('utf-8'))

                     # --- Suppression Logic ---
                     should_signal = True

                     # Update Cache
                     incoming_armed = data.get('armed')
                     current_state = drone_states.setdefault(drone_id, {'armed': None})
                     last_known_armed = current_state['armed']

                     if incoming_armed is not None:
                         # This causes a state update
                         current_state['armed'] = incoming_armed

                         # Logic:
                         # 1. If State CHANGED (True->False or False->True) -> Signal
                         # 2. If State is TRUE (Staying Armed) -> Signal
                         # 3. If State is FALSE (Staying Disarmed) -> SUPPRESS

                         # Check "Falsey" (0 or False) but ensure not None
                         if not incoming_armed and (last_known_armed is not None and not last_known_armed):
                             should_signal = False

                     else:
                         # Partial update (Position, Battery, etc) without armed status
                         # If we KNOW it's disarmed, suppress position updates (drifting GPS on ground)
                         if last_known_armed is not None and not last_known_armed:
                             should_signal = False

                     if not should_signal:
                         return # Suppress
                     # -------------------------

                     async def _signal():
                         try:
                             # We use the handle to signal ONLY if running.
                             # But get_workflow_handle just creates a stub, doesn't check existence.
                             handle = client.get_workflow_handle(
                                 workflow_id=f"entity-{drone_id}",
                                 run_id=None
                             )
                             await handle.signal(DroneEntityWorkflow.signal_telemetry, data)
                             logger.info(f"Signaled {drone_id} (armed={current_state['armed']})")
                         except Exception as err:
                             logger.error(f"Failed to signal {drone_id}: {err}")

                     # Schedule in the main loop using the CAPTURED loop object
                     future = asyncio.run_coroutine_threadsafe(_signal(), main_loop)

            except Exception as e:
                logger.error(f"Error processing telemetry: {e}")

        # Subscribe
        subscribe_future, _ = activities.mqtt_connection.subscribe(
            topic="mav/+/telemetry",
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_telemetry
        )
        subscribe_future.result()

    logger.info("Worker started. Listening on 'mission-queue'")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
