#!/bin/bash
# Builds the Cloud Bridge docker image from the project root
# Usage: ./scripts/build_bridge.sh

set -e

# Get the project root (one level up from scripts)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building aether-cloud-bridge from $PROJECT_ROOT..."

cd "$PROJECT_ROOT"

docker build \
  -f aether/cloud-bridge/Dockerfile \
  -t aether-cloud-bridge \
  .

echo "Build complete."
