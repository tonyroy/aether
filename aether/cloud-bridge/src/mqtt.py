import asyncio
import json
import logging

import paho.mqtt.client as mqtt_paho
from awscrt import io, mqtt
from awsiot import iotshadow, mqtt_connection_builder

logger = logging.getLogger(__name__)

class AwsMqttConnection:
    def __init__(self, endpoint, cert_path, key_path, root_ca_path, client_id):
        self.endpoint = endpoint
        self.cert_path = cert_path
        self.key_path = key_path
        self.root_ca_path = root_ca_path
        self.client_id = client_id
        self.connection = None
        self.shadow_client = None
        self.loop = None  # Store event loop reference

    def connect(self):
        # Get the event loop - use get_event_loop() which works from any context
        self.loop = asyncio.get_event_loop()

        logger.info(f"Connecting to AWS IoT at {self.endpoint} with client ID {self.client_id}...")
        event_loop_group = io.EventLoopGroup(1)
        host_resolver = io.DefaultHostResolver(event_loop_group)
        client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

        self.connection = mqtt_connection_builder.mtls_from_path(
            endpoint=self.endpoint,
            cert_filepath=self.cert_path,
            pri_key_filepath=self.key_path,
            client_bootstrap=client_bootstrap,
            ca_filepath=self.root_ca_path,
            client_id=self.client_id,
            clean_session=False,
            keep_alive_secs=6
        )

        connect_future = self.connection.connect()
        connect_future.result()
        logger.info(f"Connected to AWS IoT at {self.endpoint}")

        # Initialize Shadow client
        self.shadow_client = iotshadow.IotShadowClient(self.connection)
        logger.info("Shadow client initialized")

    def publish_telemetry(self, payload):
        topic = f"mav/{self.client_id}/telemetry"
        message = json.dumps(payload)
        self.connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.debug(f"Published to {topic}: {payload}")

    def publish_topic(self, topic: str, payload: dict):
        """Generic publish"""
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

    def publish_mission_plan(self, plan: dict):
        topic = f"mav/{self.client_id}/mission/detected"
        message = json.dumps(plan)
        self.connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.info(f"Published detected mission to {topic}")

    def publish_context_firmware(self, context: dict):
        topic = f"mav/{self.client_id}/context/firmware"
        message = json.dumps(context)
        self.connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.info(f"Published firmware context to {topic}")

    def publish_context_param(self, context: dict):
        topic = f"mav/{self.client_id}/context/param"
        message = json.dumps(context)
        self.connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        logger.debug(f"Published param context to {topic}")

    def sync_shadow(self, state: dict):
        """Update Device Shadow with current drone state (reported)"""
        if not self.shadow_client:
            logger.warning("Shadow client not initialized")
            return

        try:
            request = iotshadow.UpdateShadowRequest(
                thing_name=self.client_id,
                state=iotshadow.ShadowState(
                    reported=state
                )
            )

            future = self.shadow_client.publish_update_shadow(
                request=request,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            future.result(timeout=2.0)
            logger.debug(f"Updated shadow for {self.client_id}")
        except Exception as e:
            logger.error(f"Failed to update shadow: {e}")

    def subscribe_shadow_delta(self, callback):
        """Subscribe to Shadow delta (desired state changes for commands)"""
        if not self.shadow_client:
            logger.warning("Shadow client not initialized")
            return

        def on_shadow_delta_updated(delta):
            try:
                if delta.state:
                    logger.info(f"Shadow delta received: {delta.state}")
                    # Schedule async callback in event loop
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.run_coroutine_threadsafe(callback(delta.state), self.loop)
                    else:
                        callback(delta.state)
            except Exception as e:
                logger.error(f"Error processing shadow delta: {e}")

        try:
            request = iotshadow.ShadowDeltaUpdatedSubscriptionRequest(
                thing_name=self.client_id
            )

            future, _ = self.shadow_client.subscribe_to_shadow_delta_updated_events(
                request=request,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=on_shadow_delta_updated
            )
            future.result(timeout=5.0)
            logger.info(f"Subscribed to shadow delta for {self.client_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe to shadow delta: {e}")

    def subscribe_command(self, callback):
        topic = f"mav/{self.client_id}/cmd"
        logger.info(f"Subscribing to {topic}")

        def on_message_received(topic, payload, dup, qos, retain, **kwargs):
            try:
                decoded = json.loads(payload.decode('utf-8'))
                logger.info(f"Received command on {topic}: {decoded}")
                # Schedule async callback in event loop from different thread
                if asyncio.iscoroutinefunction(callback):
                    asyncio.run_coroutine_threadsafe(callback(decoded), self.loop)
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
                # Schedule async callback in event loop from different thread
                if asyncio.iscoroutinefunction(callback):
                    asyncio.run_coroutine_threadsafe(callback(decoded), self.loop)
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
        self.client = None
        self.command_callback = None
        self.mission_callback = None
        self.loop = None  # Store event loop reference

    def connect(self):
        # Get the event loop - use get_event_loop() which works from any context
        self.loop = asyncio.get_event_loop()

        logger.info(f"Connecting to Local MQTT Broker at {self.host}:{self.port}...")
        self.client = mqtt_paho.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.connect(self.host, self.port, 60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        logger.info("Connected to Local MQTT Broker!")
        # Re-subscribe on reconnect
        if self.command_callback:
            self.subscribe_command(self.command_callback)
        if self.mission_callback:
            self.subscribe_mission(self.mission_callback)

    def publish_telemetry(self, payload):
        topic = f"mav/{self.client_id}/telemetry"
        message = json.dumps(payload)
        self.client.publish(topic, message)
        logger.debug(f"Published to {topic}: {payload}")

    def publish_topic(self, topic: str, payload: dict):
        """Generic publish"""
        message = json.dumps(payload)
        self.client.publish(topic, message)
        logger.debug(f"Published to {topic}: {payload}")

    def publish_status(self, status: dict):
        """Publish command status (success/failure)"""
        topic = f"mav/{self.client_id}/status"
        message = json.dumps(status)
        self.client.publish(topic, message)
        logger.info(f"Published status to {topic}: {status}")

    def publish_mission_plan(self, plan: dict):
        topic = f"mav/{self.client_id}/mission/detected"
        message = json.dumps(plan)
        self.client.publish(topic, message)
        logger.info(f"Published detected mission to {topic}")

    def publish_context_firmware(self, context: dict):
        topic = f"mav/{self.client_id}/context/firmware"
        message = json.dumps(context)
        self.client.publish(topic, message)
        logger.info(f"Published firmware context to {topic}")

    def publish_context_param(self, context: dict):
        topic = f"mav/{self.client_id}/context/param"
        message = json.dumps(context)
        self.client.publish(topic, message)
        logger.debug(f"Published param context to {topic}")

    def subscribe_command(self, callback):
        self.command_callback = callback
        topic = f"mav/{self.client_id}/cmd"
        logger.info(f"Subscribing to {topic}")

        def on_message(client, userdata, msg):
            try:
                decoded = json.loads(msg.payload.decode('utf-8'))
                logger.info(f"Received command on {msg.topic}: {decoded}")
                # Schedule async callback in event loop from MQTT thread
                if asyncio.iscoroutinefunction(callback):
                    asyncio.run_coroutine_threadsafe(callback(decoded), self.loop)
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
                # Schedule async callback in event loop from MQTT thread
                if asyncio.iscoroutinefunction(callback):
                    asyncio.run_coroutine_threadsafe(callback(decoded), self.loop)
                else:
                    callback(decoded)
            except Exception as e:
                logger.error(f"Error processing mission: {e}")

        self.client.message_callback_add(topic, on_message)
        self.client.subscribe(topic)
