import argparse
import os
import sys
import threading
import time
import json
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
from dotenv import load_dotenv

load_dotenv()

# Configure logging
import logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    print(f"[{topic}] {payload.decode('utf-8')}")

def main():
    print(f"CWD: {os.getcwd()}")
    if os.path.exists(".env"):
        print("Found .env in CWD, loading...")
        load_dotenv(".env")
    else:
        print("Warning: .env not found in CWD. Relying on default load_dotenv search or system env vars.")
    
    endpoint = os.getenv("IOT_ENDPOINT")
    cert = os.getenv("IOT_CERT")
    key = os.getenv("IOT_KEY")
    root_ca = os.getenv("IOT_ROOT_CA")

    if not all([endpoint, cert, key, root_ca]):
        print("ERROR: Missing IOT_* environment variables. Check your .env file.")
        sys.exit(1)

    # Calculate absolute paths if they are relative to orchestrator/src
    # or just assume user runs from root or orchestrator
    # We'll just define them relative to CWD or absolute
    
    print(f"Connecting to {endpoint}...")
    
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath=cert,
        pri_key_filepath=key,
        client_bootstrap=client_bootstrap,
        ca_filepath=root_ca,
        # Use a random client ID to avoid kicking off other clients
        client_id=f"orchestrator",
        clean_session=True,
        keep_alive_secs=6
    )

    connected_future = mqtt_connection.connect()
    connected_future.result()
    print("Connected!")

    print("Subscribing to mav/# ...")
    subscribe_future, _ = mqtt_connection.subscribe(
        topic="mav/#",
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received
    )
    subscribe_future.result()

    print("Listening... (Ctrl+C to stop)")
    try:
        # Keep alive
        threading.Event().wait()
    except KeyboardInterrupt:
        print("Stopping...")
        mqtt_connection.disconnect().result()

if __name__ == "__main__":
    main()
