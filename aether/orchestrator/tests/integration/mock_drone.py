import asyncio
import json
import logging
import uuid
from awscrt import mqtt, io
from awsiot import mqtt_connection_builder

logger = logging.getLogger(__name__)

class MockDrone:
    """
    Simulates a Drone on AWS IoT.
    - Connects to IoT Core.
    - Responds to 'mav/{id}/cmd' with ACKs.
    - Updates Shadow 'reported.battery'.
    """
    def __init__(self, thing_name: str, endpoint: str, cert: str, key: str, ca: str):
        self.thing_name = thing_name
        self.endpoint = endpoint
        self.cert = cert
        self.key = key
        self.ca = ca
        self.connection = None
        self.cmd_topic = f"mav/{thing_name}/cmd"
        self.pub_topic = f"mav/{thing_name}/pub"

    async def start(self):
        # Create Connection
        # Note: In a real test we might need unique client_ids
        client_id = f"mock-drone-{self.thing_name}-{uuid.uuid4()}"
        
        event_loop_group = io.EventLoopGroup(1)
        host_resolver = io.DefaultHostResolver(event_loop_group)
        client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

        self.connection = mqtt_connection_builder.mtls_from_path(
            endpoint=self.endpoint,
            cert_filepath=self.cert,
            pri_key_filepath=self.key,
            ca_filepath=self.ca,
            client_id=client_id,
            clean_session=True, 
            keep_alive_secs=30,
            client_bootstrap=client_bootstrap
        )

        connect_future = self.connection.connect()
        connect_future.result()
        logger.info(f"{self.thing_name} Connected!")

        # Subscribe to Commands
        subscribe_future, _ = self.connection.subscribe(
            topic=self.cmd_topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._on_command
        )
        subscribe_future.result()
        
        # Publish initial Battery/State (Simulate "Connected")
        # We might need to update Shadow manually if the simple "update_shadow_status" activity relies on it?
        # Actually, Entity Workflow updates .orchestrator.status.
        # But pre-flight checks battery.
        await self.update_battery(100)

    async def stop(self):
        if self.connection:
            disconnect_future = self.connection.disconnect()
            disconnect_future.result()

    async def update_battery(self, level: int):
        # Update Shadow reported.battery
        shadow_topic = f"$aws/things/{self.thing_name}/shadow/update"
        payload = {
            "state": {
                "reported": {
                    "battery": level,
                    "connectivity": "connected" # Hint for indexing?
                }
            }
        }
        self.connection.publish(
            topic=shadow_topic,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE
        )

    def _on_command(self, topic, payload, dup, qos, retain, **kwargs):
        msg = json.loads(payload)
        cmd = msg.get("command")
        logger.info(f"{self.thing_name} received: {cmd}")
        
        # Auto-ACK
        # In real bridge, it publishes telemetry or ack. 
        # For MissionWorkflow 'send_command', it just publishes. 
        # Ideally we should publish an ACK back if the workflow waited for it.
        # But currently 'send_command' activity connects, publishes, and returns 'Sent'. 
        # It DOES NOT wait for ACK (unless we change it).
        # So we just log it.
