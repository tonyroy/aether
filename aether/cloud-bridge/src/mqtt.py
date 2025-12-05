import logging
import json
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder

logger = logging.getLogger(__name__)

class MqttConnection:
    def __init__(self, endpoint, cert_path, key_path, root_ca_path, client_id):
        self.endpoint = endpoint
        self.cert_path = cert_path
        self.key_path = key_path
        self.root_ca_path = root_ca_path
        self.client_id = client_id
        self.connection = None

    def connect(self):
        logger.info(f"Connecting to AWS IoT at {self.endpoint} with client ID {self.client_id}...")
        
        event_loop_group = io.EventLoopGroup(1)
        host_resolver = io.DefaultHostResolver(event_loop_group)
        client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

        self.connection = mqtt_connection_builder.mtls_from_path(
            endpoint=self.endpoint,
            cert_filepath=self.cert_path,
            pri_key_filepath=self.key_path,
            ca_filepath=self.root_ca_path,
            client_id=str(self.client_id),
            client_bootstrap=client_bootstrap,
            clean_session=False,
            keep_alive_secs=30
        )

        connect_future = self.connection.connect()
        connect_future.result()
        logger.info("Connected to AWS IoT!")

    def publish_telemetry(self, payload):
        topic = f"mav/{self.client_id}/telemetry"
        self.connection.publish(
            topic=topic,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.debug(f"Published to {topic}: {payload}")

    def subscribe_command(self, callback):
        topic = f"mav/{self.client_id}/cmd"
        logger.info(f"Subscribing to {topic}")
        
        def on_message_received(topic, payload, dup, qos, retain, **kwargs):
            try:
                decoded = json.loads(payload.decode('utf-8'))
                logger.info(f"Received command on {topic}: {decoded}")
                callback(decoded)
            except Exception as e:
                logger.error(f"Error processing command: {e}")

        subscribe_future, packet_id = self.connection.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_message_received
        )
        subscribe_future.result()
