import logging
import json
import asyncio
import paho.mqtt.client as mqtt_paho
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder

logger = logging.getLogger(__name__)

class AwsMqttConnection:
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
        message = json.dumps(payload)
        self.connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.debug(f"Published to {topic}: {payload}")
    
    def publish_status(self, status: dict):
        """Publish command status (success/failure)"""
        topic = f"mav/{self.client_id}/status"
        message = json.dumps(status)
        self.connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.info(f"Published status to {topic}: {status}")

    def subscribe_command(self, callback):
        topic = f"mav/{self.client_id}/cmd"
        logger.info(f"Subscribing to {topic}")
        
        def on_message_received(topic, payload, dup, qos, retain, **kwargs):
            try:
                decoded = json.loads(payload.decode('utf-8'))
                logger.info(f"Received command on {topic}: {decoded}")
                # Schedule async callback in event loop
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(decoded))
                else:
                    callback(decoded)
            except Exception as e:
                logger.error(f"Error processing command: {e}")

        subscribe_future, packet_id = self.connection.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_message_received
        )
        subscribe_future.result()

    def subscribe_mission(self, callback):
        topic = f"mav/{self.client_id}/mission"
        logger.info(f"Subscribing to {topic}")
        
        def on_message_received(topic, payload, dup, qos, retain, **kwargs):
            try:
                decoded = json.loads(payload.decode('utf-8'))
                logger.info(f"Received mission plan on {topic}")
                # Schedule async callback in event loop
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(decoded))
                else:
                    callback(decoded)
            except Exception as e:
                logger.error(f"Error processing mission plan: {e}")

        subscribe_future, packet_id = self.connection.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_message_received
        )
        subscribe_future.result()

class LocalMqttConnection:
    def __init__(self, host, port, client_id):
        self.host = host
        self.port = int(port)
        self.client_id = client_id
        self.client = mqtt_paho.Client(client_id=client_id)
        self.command_callback = None
        self.mission_callback = None

    def connect(self):
        logger.info(f"Connecting to Local MQTT Broker at {self.host}:{self.port}...")
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info("Connected to Local MQTT Broker!")
                # Re-subscribe on reconnect
                if self.command_callback:
                    self.subscribe_command(self.command_callback)
                if self.mission_callback:
                    self.subscribe_mission(self.mission_callback)
            else:
                logger.error(f"Failed to connect to Local MQTT, return code {rc}")

        self.client.on_connect = on_connect
        self.client.connect(self.host, self.port, 60)
        self.client.loop_start()

    def publish_telemetry(self, payload):
        topic = f"mav/{self.client_id}/telemetry"
        message = json.dumps(payload)
        self.client.publish(topic, message)
        logger.debug(f"Published to {topic}: {payload}")
    
    def publish_status(self, status: dict):
        """Publish command status (success/failure)"""
        topic = f"mav/{self.client_id}/status"
        message = json.dumps(status)
        self.client.publish(topic, message)
        logger.info(f"Published status to {topic}: {status}")

    def subscribe_command(self, callback):
        self.command_callback = callback
        topic = f"mav/{self.client_id}/cmd"
        logger.info(f"Subscribing to {topic}")

        def on_message(client, userdata, msg):
            try:
                decoded = json.loads(msg.payload.decode('utf-8'))
                logger.info(f"Received command on {msg.topic}: {decoded}")
                # Schedule async callback in event loop
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(decoded))
                else:
                    callback(decoded)
            except Exception as e:
                logger.error(f"Error processing command: {e}")

        self.client.message_callback_add(topic, on_message)
        self.client.subscribe(topic)

    def subscribe_mission(self, callback):
        self.mission_callback = callback
        topic = f"mav/{self.client_id}/mission"
        logger.info(f"Subscribing to {topic}")

        def on_message(client, userdata, msg):
            try:
                decoded = json.loads(msg.payload.decode('utf-8'))
                logger.info(f"Received mission on {msg.topic}: {decoded}")
                # Schedule async callback in event loop
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(decoded))
                else:
                    callback(decoded)
            except Exception as e:
                logger.error(f"Error processing mission: {e}")

        self.client.message_callback_add(topic, on_message)
        self.client.subscribe(topic)
