# Agent## 1. Development Standards

- **AWS CDK**: Infrastructure as Code for AWS resources
- **Python 3.12+**: Primary language for backend services
- **GitHub Actions**: CI/CD pipeline automation
- **TDD (Test-Driven Development)**: Write failing tests before implementation
- **Type Hints**: Use type annotations for all function signatures
- **Incremental Changes**: Small, testable commits
- **Schema-First**: Define JSON schemas before implementation
- **Asyncio**: Use Python asyncio for concurrent operations
  - Command acknowledgment via Futures (non-blocking)
  - Event-driven message processing
  - Compatible with Temporal workflows
- **Command Reliability**: All MAVLink commands must wait for COMMAND_ACK
  - Use asyncio Futures to track pending commands
  - Publish command status to MQTT for observability
  - Timeout after 5 seconds with error logging

## 2. Scripting & Automation
*   **Language**: **Python 3**
*   **Usage**: All utility scripts, build scripts, and glue code should be written in Python 3.
*   **Exceptions**: Simple shell scripts (`.sh`) are acceptable for entrypoints or simple wrapping, but complex logic must be in Python.

## 3. CI/CD
*   **Platform**: **GitHub Actions**
*   **Config Location**: `.github/workflows/`
*   **Do not use**: Jenkins, GitLab CI, or CircleCI.
