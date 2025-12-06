# Agent## 1. Development Standards
- **Infrastructure as Code**: All AWS infrastructure MUST be defined using AWS CDK (TypeScript or Python).
- **Python**: Use Python 3.9+ for all scripts and backend services.
- **Python Tooling**: Use `uv` for Python package management and virtual environments.
- **CI/CD**: Use GitHub Actions for all build and deployment pipelines.

## 2. Scripting & Automation
*   **Language**: **Python 3**
*   **Usage**: All utility scripts, build scripts, and glue code should be written in Python 3.
*   **Exceptions**: Simple shell scripts (`.sh`) are acceptable for entrypoints or simple wrapping, but complex logic must be in Python.

## 3. CI/CD
*   **Platform**: **GitHub Actions**
*   **Config Location**: `.github/workflows/`
*   **Do not use**: Jenkins, GitLab CI, or CircleCI.
