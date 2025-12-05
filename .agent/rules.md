# Agent Development Rules

When writing code or generating plans for this project, you MUST adhere to the following technology stack requirements:

## 1. Infrastructure as Code (IaC)
*   **Tool**: **AWS CDK**
*   **Language**: Python (unless explicitly requested otherwise).
*   **Do not use**: Terraform, CloudFormation (raw), or Pulumi.

## 2. Scripting & Automation
*   **Language**: **Python 3**
*   **Usage**: All utility scripts, build scripts, and glue code should be written in Python 3.
*   **Exceptions**: Simple shell scripts (`.sh`) are acceptable for entrypoints or simple wrapping, but complex logic must be in Python.

## 3. CI/CD
*   **Platform**: **GitHub Actions**
*   **Config Location**: `.github/workflows/`
*   **Do not use**: Jenkins, GitLab CI, or CircleCI.
