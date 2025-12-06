#!/bin/bash
set -e

# Default values
INSTANCE_ID=1
LAT=-35.363261
LON=149.165230
USE_AWS=false

# Usage function
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -i, --instance <id>   Drone Instance ID (default: 1)"
    echo "  -l, --lat <val>       Latitude (default: -35.363261)"
    echo "  -L, --lon <val>       Longitude (default: 149.165230)"
    echo "  -a, --aws             Enable AWS IoT Core mode"
    echo "  -h, --help            Show this help message"
    echo ""
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--instance)
            INSTANCE_ID="$2"
            shift # past argument
            shift # past value
            ;;
        -l|--lat)
            LAT="$2"
            shift
            shift
            ;;
        -L|--lon)
            LON="$2"
            shift
            shift
            ;;
        -a|--aws)
            USE_AWS=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            # Allow positional argument for instance ID for backward compatibility
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                INSTANCE_ID="$1"
                shift
            else
                echo "Unknown option: $1"
                usage
            fi
            ;;
    esac
done

# Calculate Ports based on Instance ID
OFFSET=$((INSTANCE_ID * 10))
PORT_USER=$((5760 + OFFSET))
PORT_BRIDGE=$((5760 + OFFSET + 2))

# Container Names
SITL_NAME="sitl-drone-${INSTANCE_ID}"
BRIDGE_NAME="cloud-bridge-${INSTANCE_ID}"
DRONE_ID="drone-${INSTANCE_ID}"

echo "Starting Drone Instance ${INSTANCE_ID}..."
echo "  Location: ${LAT}, ${LON}"
echo "  User Port (MAVProxy): ${PORT_USER}"
echo "  Bridge Port: ${PORT_BRIDGE}"
echo "  Containers: ${SITL_NAME}, ${BRIDGE_NAME}"

# Network setup
NETWORK="drones_default"
if [ -z "$(docker network ls -q -f name=${NETWORK})" ]; then
    echo "Creating network ${NETWORK}..."
    docker network create ${NETWORK}
fi

# 1. Start SITL Drone
echo "Launching SITL..."
docker run -d \
    --name ${SITL_NAME} \
    --network ${NETWORK} \
    -p ${PORT_USER}:${PORT_USER} \
    -p ${PORT_BRIDGE}:${PORT_BRIDGE} \
    -e INSTANCE=${INSTANCE_ID} \
    -e SYSID=${INSTANCE_ID} \
    -e LAT=${LAT} \
    -e LON=${LON} \
    -e SERIAL0="tcp:${PORT_USER}" \
    -e SERIAL1="tcp:${PORT_BRIDGE}" \
    aether-drone-node

# 2. Start Cloud Bridge
echo "Launching Cloud Bridge..."

# Check if using AWS IoT
if [ "$USE_AWS" = true ]; then
    echo "  Mode: AWS IoT Core"
    
    # Check if certificates exist
    if [ ! -d "certs/${DRONE_ID}" ]; then
        echo "ERROR: Certificates not found for ${DRONE_ID}"
        echo "Run: cd aether/infra && python scripts/provision_drone.py ${DRONE_ID}"
        exit 1
    fi
    
    # AWS IoT endpoint (replace with your endpoint if needed)
    IOT_ENDPOINT="${IOT_ENDPOINT:-alddhtwebpu3w-ats.iot.ap-southeast-2.amazonaws.com}"
    
    docker run -d \
        --name ${BRIDGE_NAME} \
        --network ${NETWORK} \
        -v "$(pwd)/certs:/app/certs:ro" \
        -e LOG_LEVEL="INFO" \
        -e MAVLINK_CONNECTION="tcp:${SITL_NAME}:${PORT_BRIDGE}" \
        -e IOT_CLIENT_ID="${DRONE_ID}" \
        -e IOT_ENDPOINT="${IOT_ENDPOINT}" \
        -e IOT_CERT="/app/certs/${DRONE_ID}/certificate.pem" \
        -e IOT_KEY="/app/certs/${DRONE_ID}/private.key" \
        -e IOT_ROOT_CA="/app/certs/AmazonRootCA1.pem" \
        aether-cloud-bridge
else
    echo "  Mode: Local MQTT (mosquitto)"
    
    docker run -d \
        --name ${BRIDGE_NAME} \
        --network ${NETWORK} \
        -e LOG_LEVEL="INFO" \
        -e MAVLINK_CONNECTION="tcp:${SITL_NAME}:${PORT_BRIDGE}" \
        -e IOT_CLIENT_ID="${DRONE_ID}" \
        -e LOCAL_BROKER_HOST="mosquitto" \
        -e LOCAL_BROKER_PORT="1883" \
        aether-cloud-bridge
fi

echo "Done! Drone ${INSTANCE_ID} is flying."
echo "Connect MAVProxy: mavproxy.py --master=tcp:127.0.0.1:${PORT_USER} --console"

if [ "$USE_AWS" = true ]; then
    echo "AWS IoT Topics:"
    echo "  Telemetry: mav/${DRONE_ID}/telemetry"
    echo "  Commands:  mav/${DRONE_ID}/cmd"
    echo "  Status:    mav/${DRONE_ID}/status"
else
    echo "Watch Telemetry: docker exec -it mosquitto mosquitto_sub -t 'mav/${DRONE_ID}/#'"
fi
