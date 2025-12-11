# Build from Project Root
# docker build -f aether/cloud-bridge/Dockerfile -t aether-cloud-bridge .

FROM python:3.9-slim

WORKDIR /app

# Copy Common Library (needed for dependency)
COPY aether/common /app/common

# Setup Bridge
WORKDIR /app/bridge
COPY aether/cloud-bridge/requirements.txt .

# Install dependencies (requirements.txt points to ../common which maps to /common)
RUN pip install --no-cache-dir -r requirements.txt

COPY aether/cloud-bridge/src src

# Default connection string
ENV MAVLINK_CONNECTION="udp:0.0.0.0:14550"

CMD ["python", "-m", "src.main"]
