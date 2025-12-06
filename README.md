# Aether: Cloud-Native Drone Orchestration

Aether is a comprehensive architecture for orchestrating autonomous aerial systems using AWS, Temporal, and the Model Context Protocol (MCP). It transforms drones into persistent "Digital Twins" and enables generic, cloud-native control.

## Project Structure

*   **/aether**: Core project files.
    *   **docker-sitl/**: Dockerized Software-In-The-Loop (SITL) simulation for ArduPilot.
    *   **docs/**: Detailed architectural documentation and overview.
*   **/.agent/workflows**: Helper workflows for AI agents (like me!) to interact with the project.

## Getting Started

### 1. Run the Simulation

You can use the provided helper scripts to build and run the drone simulation.

```bash
cd aether/docker-sitl
./build.sh
./run-drone.sh
```

### Key Components
1.  **Simulation**: ArduCopter SITL running in Docker.
2.  **Cloud Bridge**: Python service that translates MAVLink <-> JSON.
    -   **Telemetry**: Publishes state to AWS Device Shadow.
    -   **Missions**: Uploads complex paths (Waypoints, Geofences) from `schemas/mission_plan.json`.
3.  **Orchestration**: Temporal.io workflows manage long-running tasks ("Scan Perimeter").

## Protocols & Schemas
We use a **Schema-First** design. The contract between the Drone and the Cloud is defined in `schemas/`:
-   `schemas/telemetry.json`: High-frequency state updates.
-   `schemas/command.json`: Atomic commands (ARM, LAND).
-   `schemas/mission_plan.json`: Complex safety & flight plans.

## Development Standards
-   **Infrastructure**: AWS CDK (Python).
-   **Language**: Python 3.9+ (managed via `uv`), with strict type hinting.
-   **Methodology**: Test-Driven Development (TDD).
-   **CI/CD**: GitHub Actions.

For a deep dive into the architecture, please read [aether/docs/overview.md](aether/docs/overview.md).
