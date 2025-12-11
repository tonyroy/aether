#!/bin/bash
# Builds all Aether components
# Usage: ./scripts/build_all.sh

set -e

# Get the project root (one level up from scripts)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Building All Aether Components ==="

# 1. Build SITL Drone Node
echo "[1/2] Building SITL Drone Node..."
cd "$PROJECT_ROOT/aether/docker-sitl"
docker build -t aether-drone-node .

# 2. Build Cloud Bridge
echo "[2/2] Building Cloud Bridge..."
# Reuse the logic in build_bridge.sh (which handles root context)
"$SCRIPT_DIR/build_bridge.sh"

echo "=== All Builds Complete ==="
