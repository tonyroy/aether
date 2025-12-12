#!/bin/bash
set -e

# Handle signals properly for clean shutdown
_term() {
  echo "Caught signal, shutting down..."
  kill -TERM "$child" 2>/dev/null
  exit 0
}

trap _term SIGTERM SIGINT

# Base Installation Directory
ARDUPILOT_HOME=${ARDUPILOT_HOME:-"/home/ardupilot/ardupilot"}

# Default values for environment variables
LAT=${LAT:-"-35.363261"}
LON=${LON:-"149.165230"}
ALT=${ALT:-"584"}
DIR=${DIR:-"353"}
SPEEDUP=${SPEEDUP:-"1"}
INSTANCE=${INSTANCE:-"0"}
MODEL=${MODEL:-"+"}
SLAVE=${SLAVE:-"0"}
SERIAL0=${SERIAL0:-"tcp:5760:wait"}
SERIAL1=${SERIAL1:-"udpclient:0.0.0.0:14550"}
DEFAULTS=${DEFAULTS:-"$ARDUPILOT_HOME/Tools/autotest/default_params/copter.parm"}
SIM_ADDRESS=${SIM_ADDRESS:-"0.0.0.0"}
SYSID=${SYSID:-"1"}

# Construct home location string
HOME_LOCATION="${LAT},${LON},${ALT},${DIR}"

echo "========================================"
echo "ArduCopter SITL Configuration"
echo "========================================"
echo "Installation Root: ${ARDUPILOT_HOME}"
echo "Home Location: ${HOME_LOCATION}"
echo "Speedup: ${SPEEDUP}x"
echo "Instance: ${INSTANCE}"
echo "System ID: ${SYSID}"
echo "Model: ${MODEL}"
echo "Serial0: ${SERIAL0}"
echo "Serial1: ${SERIAL1}"
echo "Sim Address: ${SIM_ADDRESS}"
echo "========================================"

# Change to ardupilot directory
cd "${ARDUPILOT_HOME}"

# Build the command
# Handle Custom Parameters (passed via env var)
# Format: "PARAM1=VAL1,PARAM2=VAL2" or newlines
if [ -n "${CUSTOM_PARAMS}" ]; then
    echo "Applying Custom Params: ${CUSTOM_PARAMS}"
    echo "${CUSTOM_PARAMS}" | tr ',' '\n' > /home/ardupilot/custom_defaults.parm
    
    if [ -n "${DEFAULTS}" ]; then
        DEFAULTS="${DEFAULTS},/home/ardupilot/custom_defaults.parm"
    else
        DEFAULTS="/home/ardupilot/custom_defaults.parm"
    fi
fi

# Helper for disabling logs explicitly (legacy support)
if [ "${DISABLE_LOGS}" = "true" ] || [ "${DISABLE_LOGS}" = "1" ]; then
   echo "LOG_BACKEND_TYPE 0" >> /home/ardupilot/custom_defaults.parm
fi

CMD="${ARDUPILOT_HOME}/build/sitl/bin/arducopter"
CMD="$CMD --model ${MODEL}"
CMD="$CMD --speedup ${SPEEDUP}"
CMD="$CMD --slave ${SLAVE}"
CMD="$CMD --defaults ${DEFAULTS}"
CMD="$CMD --sim-address=${SIM_ADDRESS}"
CMD="$CMD -I${INSTANCE}"
CMD="$CMD --home ${HOME_LOCATION}"
CMD="$CMD --sysid ${SYSID}"

# Add serial ports
CMD="$CMD --serial0 ${SERIAL0}"
if [ -n "${SERIAL1}" ]; then
    CMD="$CMD --serial1 ${SERIAL1}"
fi
if [ -n "${SERIAL2}" ]; then
    CMD="$CMD --serial2 ${SERIAL2}"
fi
if [ -n "${SERIAL3}" ]; then
    CMD="$CMD --serial3 ${SERIAL3}"
fi
if [ -n "${SERIAL4}" ]; then
    CMD="$CMD --serial4 ${SERIAL4}"
fi

# Add optional FlightGear support
if [ "${ENABLE_FGVIEW}" = "true" ] || [ "${ENABLE_FGVIEW}" = "1" ]; then
    CMD="$CMD --enable-fgview"
fi

# Add any additional arguments passed to the container
if [ $# -gt 0 ]; then
    CMD="$CMD $@"
fi

echo "Executing: $CMD"
echo "========================================"

# Execute the command in background so we can trap signals
$CMD &
child=$!

# Wait for the process and forward exit code
wait "$child"
