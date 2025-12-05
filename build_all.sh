#!/bin/bash
set -e

echo "Building SITL..."
cd aether/docker-sitl
./build.sh
cd ../..

echo "Building Cloud Bridge..."
cd aether/cloud-bridge
docker build -t aether-cloud-bridge .
cd ../..

echo "Build complete!"
