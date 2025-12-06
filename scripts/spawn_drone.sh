#!/bin/bash
set -e

# Usage: ./spawn_drone.sh <INSTANCE_ID> [LAT] [LON]

INSTANCE_ID=${1:-1}
LAT=${2:--35.363261}
LON=${3:-149.165230}

# Calculate Ports based on Instance ID
# Base: 5760
# Per Instance Offset: 10
# Instance 1: 5770 (User), 5772 (Bridge)
# Instance 2: 5780 (User), 5782 (Bridge)
OFFSET=$((INSTANCE_ID * 10))
PORT_USER=$((5760 + OFFSET))
PORT_BRIDGE=$((5760 + OFFSET + 2))

# Container Names
SITL_NAME="sitl-drone-${INSTANCE_ID}"
BRIDGE_NAME="cloud-bridge-${INSTANCE_ID}"

echo "Starting Drone Instance ${INSTANCE_ID}..."
echo "  Location: ${LAT}, ${LON}"
echo "  User Port (MAVProxy): ${PORT_USER}"
echo "  Bridge Port: ${PORT_BRIDGE}"
echo "  Containers: ${SITL_NAME}, ${BRIDGE_NAME}"

# 1. Start SITL Drone
# We use the 'aether-network' (default is usually folder_default, but let's assume 'drones_default' from docker-compose)
# Using 'host' network on Mac for simplicity might be tricky for multiple instances binding ports.
# Better to use the bridge network created by docker-compose.
NETWORK="drones_default"

# Ensure network exists
if [ -z "$(docker network ls -q -f name=${NETWORK})" ]; then
    echo "Creating network ${NETWORK}..."
    docker network create ${NETWORK}
fi

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
docker run -d \
    --name ${BRIDGE_NAME} \
    --network ${NETWORK} \
    -e LOG_LEVEL="INFO" \
    -e MAVLINK_CONNECTION="tcp:${SITL_NAME}:${PORT_BRIDGE}" \
    -e IOT_CLIENT_ID="drone-${INSTANCE_ID}" \
    -e LOCAL_BROKER_HOST="mosquitto" \
    -e LOCAL_BROKER_PORT="1883" \
    aether-cloud-bridge

echo "Done! Drone ${INSTANCE_ID} is flying."
echo "Connect MAVProxy: mavproxy.py --master=tcp:127.0.0.1:${PORT_USER} --console"
echo "Watch Telemetry:  docker exec -it mosquitto mosquitto_sub -t 'mav/drone-${INSTANCE_ID}/#'"
