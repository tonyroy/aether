# Use Ubuntu 22.04 as base (Standard for ArduPilot toolchains)
FROM ubuntu:22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install Dependencies
# We include procps (for ps), net-tools, and the build chain
RUN apt-get update && apt-get install -y \
    git \
    python-is-python3 \
    python3 \
    python3-dev \
    python3-pip \
    python3-opencv \
    python3-wxgtk4.0 \
    python3-matplotlib \
    python3-lxml \
    python3-numpy \
    g++ \
    gcc \
    cmake \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Create non-root user 'ardupilot'
# Security best practice for cloud deployments
RUN useradd -m -s /bin/bash ardupilot
USER ardupilot
WORKDIR /home/ardupilot

# 3. Clone ArduPilot & Install Python Requirements
# We lock to a specific tag for reproducibility
RUN git clone --recursive --depth 1 --branch Copter-4.5 https://github.com/ArduPilot/ardupilot.git

WORKDIR /home/ardupilot/ardupilot

# Install MAVProxy and pymavlink (needed for sim_vehicle.py)
RUN pip3 install MAVProxy pymavlink empy==3.3.4 pexpect future

# 4. Pre-Configure and Build
# We build the 'sitl' board for 'copter' here. 
# This ensures the container starts instantly, rather than compiling on `docker run`.
RUN ./waf configure --board sitl
RUN ./waf copter

# 5. Environment Setup
ENV PATH=$PATH:/home/ardupilot/ardupilot/Tools/autotest
ENV PATH=$PATH:/home/ardupilot/.local/bin

# 6. Entrypoint
COPY --chown=ardupilot:ardupilot entrypoint.sh /home/ardupilot/entrypoint.sh
RUN chmod +x /home/ardupilot/entrypoint.sh

# Expose Ports
# 5760: TCP MAVLink (Connection A - for our Temporal Agent)
# 14550: UDP MAVLink (Connection B - for QGroundControl/Mission Planner)
EXPOSE 5760/tcp 14550/udp

ENTRYPOINT ["/home/ardupilot/entrypoint.sh"]