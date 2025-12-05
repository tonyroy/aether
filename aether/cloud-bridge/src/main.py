import os
import logging
import argparse
from src.mavlink import MavlinkConnection
from src.mqtt import MqttConnection
from src.bridge import CloudBridge

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description='Aether Cloud Bridge')
    parser.add_argument('--mavlink', default='udp:127.0.0.1:14550', help='MAVLink connection string')
    parser.add_argument('--client_id', default=os.environ.get('IOT_CLIENT_ID', 'test-drone'), help='AWS IoT Thing Name')
    parser.add_argument('--endpoint', default=os.environ.get('IOT_ENDPOINT', ''), help='AWS IoT Endpoint URL')
    parser.add_argument('--cert', default=os.environ.get('IOT_CERT', 'certs/certificate.pem.crt'), help='Path to device certificate')
    parser.add_argument('--key', default=os.environ.get('IOT_KEY', 'certs/private.pem.key'), help='Path to private key')
    parser.add_argument('--root_ca', default=os.environ.get('IOT_ROOT_CA', 'certs/root.pem'), help='Path to root CA')

    args = parser.parse_args()

    # MAVLink Connection
    mav = MavlinkConnection(args.mavlink)

    # MQTT Connection
    # If endpoint isn't provided, we can't connect to AWS
    if not args.endpoint:
        logging.warning("No AWS IoT Endpoint provided. MQTT will be disabled.")
    
    mqtt = MqttConnection(
        endpoint=args.endpoint,
        cert_path=args.cert,
        key_path=args.key,
        root_ca_path=args.root_ca,
        client_id=args.client_id
    )

    # Initialize and START
    bridge = CloudBridge(mav, mqtt)
    bridge.start()

if __name__ == '__main__':
    main()
