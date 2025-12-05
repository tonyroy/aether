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

Or simply ask me to "Run the drone simulation".

## Architecture Highlights

*   **Temporal.io**: Used for durable execution and managing the state of "Drone Entities".
*   **Model Context Protocol (MCP)**: Standardizes the interface between AI agents and drone capabilities.
*   **AWS IoT Core**: Handles secure MAVLink telemetry ingress and command egress.
*   **AWS Fargate**: Runs ephemeral simulation "sidecars" for scalable fleet testing.

## Development Standards

*   **Infrastructure**: AWS CDK (Python)
*   **Scripting**: Python 3
*   **CI/CD**: GitHub Actions

For a deep dive into the architecture, please read [aether/docs/overview.md](aether/docs/overview.md).
