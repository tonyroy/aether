import os
import logging
import argparse
from src.mavlink import MavlinkConnection
from src.mqtt import AwsMqttConnection, LocalMqttConnection
from src.bridge import CloudBridge
from src.mission import MissionManager

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description='Aether Cloud Bridge')
    parser.add_argument('--mavlink', default=os.environ.get('MAVLINK_CONNECTION', 'udp:127.0.0.1:14550'), help='MAVLink connection string')
    parser.add_argument('--client_id', default=os.environ.get('IOT_CLIENT_ID', 'test-drone'), help='AWS IoT Thing Name')
    
    # AWS configuration
    parser.add_argument('--endpoint', default=os.environ.get('IOT_ENDPOINT', ''), help='AWS IoT Endpoint URL')
    parser.add_argument('--cert', default=os.environ.get('IOT_CERT', 'certs/certificate.pem.crt'), help='Path to device certificate')
    parser.add_argument('--key', default=os.environ.get('IOT_KEY', 'certs/private.pem.key'), help='Path to private key')
    parser.add_argument('--root_ca', default=os.environ.get('IOT_ROOT_CA', 'certs/root.pem'), help='Path to root CA')

    # Local configuration
    parser.add_argument('--local_host', default=os.environ.get('LOCAL_BROKER_HOST', ''), help='Local MQTT Broker Host')
    parser.add_argument('--local_port', default=os.environ.get('LOCAL_BROKER_PORT', '1883'), help='Local MQTT Broker Port')

    args = parser.parse_args()

    # MAVLink Connection
    mav = MavlinkConnection(args.mavlink)
    
    # Mission Manager
    mission_manager = MissionManager(mav)

    # MQTT Connection
    mqtt = None
    if args.endpoint:
        mqtt = AwsMqttConnection(
            endpoint=args.endpoint,
            cert_path=args.cert,
            key_path=args.key,
            root_ca_path=args.root_ca,
            client_id=args.client_id
        )
    elif args.local_host:
        mqtt = LocalMqttConnection(
            host=args.local_host,
            port=args.local_port,
            client_id=args.client_id
        )
    else:
        logging.warning("No AWS Endpoint or Local Broker provided. Running in standalone mode.")

    # Initialize and START
    bridge = CloudBridge(mav, mqtt, mission_manager)
    bridge.start()


if __name__ == '__main__':
    main()
