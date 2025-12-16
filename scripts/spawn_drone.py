#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import time

def run_command(cmd, shell=False):
    """Run a shell command and print output/error if it fails."""
    try:
        subprocess.check_call(cmd, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        sys.exit(e.returncode)

def get_docker_output(cmd):
    """Run a docker command and return output."""
    try:
        return subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
    except subprocess.CalledProcessError:
        return ""

def main():
    parser = argparse.ArgumentParser(description="Spawn a drone instance with optional AWS IoT connection.")
    parser.add_argument("-i", "--instance", type=int, default=1, help="Drone Instance ID (default: 1)")
    parser.add_argument("-l", "--lat", type=float, default=-35.363261, help="Latitude (default: -35.363261)")
    parser.add_argument("-L", "--lon", type=float, default=149.165230, help="Longitude (default: 149.165230)")
    parser.add_argument("-a", "--aws", action="store_true", help="Enable AWS IoT Core mode")
    parser.add_argument("--endpoint", type=str, default="alddhtwebpu3w-ats.iot.ap-southeast-2.amazonaws.com", help="AWS IoT Endpoint")
    parser.add_argument("--limit-logs", action="store_true", help="Limit SITL logs to ~10MB and auto-rotate")
    
    args = parser.parse_args()

    # Configuration
    instance_id = args.instance
    lat = args.lat
    lon = args.lon
    use_aws = args.aws
    iot_endpoint = args.endpoint
    limit_logs = args.limit_logs

    # Calculate Ports
    offset = instance_id * 10
    port_user = 5760 + offset
    port_bridge = 5760 + offset + 2

    # Container Names
    sitl_name = f"sitl-drone-{instance_id}"
    bridge_name = f"cloud-bridge-{instance_id}"
    drone_id = f"drone-{instance_id}"
    network = "drones_default"

    print(f"Starting Drone Instance {instance_id}...")
    print(f"  Location: {lat}, {lon}")
    print(f"  User Port (MAVProxy): {port_user}")
    print(f"  Bridge Port: {port_bridge}")
    print(f"  Containers: {sitl_name}, {bridge_name}")

    # Ensure network exists
    if not get_docker_output(f"docker network ls -q -f name={network}"):
        print(f"Creating network {network}...")
        run_command(f"docker network create {network}", shell=True)

    # 1. Start SITL Drone
    print("Launching SITL...")
    # Remove existing container if it exists
    run_command(f"docker rm -f {sitl_name} 2>/dev/null || true", shell=True)
    
    sitl_cmd = [
        "docker", "run", "-d",
        "--name", sitl_name,
        "--network", network,
        "-p", f"{port_user}:{port_user}",
        "-p", f"{port_bridge}:{port_bridge}",
        "-e", f"INSTANCE={instance_id}",
        "-e", f"SYSID={instance_id}",
        "-e", f"LAT={lat}",
        "-e", f"LON={lon}",
        "-e", f"SERIAL0=tcp:{port_user}",
        "-e", f"SERIAL1=tcp:{port_bridge}",
        "aether-drone-node"
    ]

    if limit_logs:
        # Use tmpfs limited to 20MB for logs
        # And set ArduPilot params to respect small space (LOG_FILE_MB_FREE=5 -> leave 5MB free)
        # So we use ~15MB of logs.
        sitl_cmd.insert(3, "--tmpfs")
        sitl_cmd.insert(4, "/home/ardupilot/ardupilot/logs:size=20M")
        
        # Inject params via CUSTOM_PARAMS
        # LOG_FILE_MB_FREE=5 (Leave 5MB free)
        # LOG_DISARMED=0 (Don't log when disarmed)
        # LOG_BACKEND_TYPE=1 (File only)
        sitl_cmd.append("-e")
        sitl_cmd.append("CUSTOM_PARAMS=LOG_FILE_MB_FREE=5,LOG_DISARMED=0,LOG_BACKEND_TYPE=1")
    
    run_command(sitl_cmd)

    # 2. Start Cloud Bridge
    print("Launching Cloud Bridge...")
    # Remove existing container if it exists
    run_command(f"docker rm -f {bridge_name} 2>/dev/null || true", shell=True)

    bridge_cmd = [
        "docker", "run", "-d",
        "--name", bridge_name,
        "--network", network,
        "-e", "LOG_LEVEL=INFO",
        "-e", f"MAVLINK_CONNECTION=tcp:{sitl_name}:{port_bridge}",
        "-e", f"IOT_CLIENT_ID={drone_id}"
    ]

    if use_aws:
        print("  Mode: AWS IoT Core")
        
        # Check certificates
        cert_path = os.path.join(os.getcwd(), "certs", drone_id)
        if not os.path.exists(cert_path):
            print(f"ERROR: Certificates not found for {drone_id}")
            print(f"Run: cd aether/infra && python scripts/provision_drone.py {drone_id}")
            sys.exit(1)

        bridge_cmd.extend([
            "-v", f"{os.getcwd()}/certs:/app/certs:ro",
            "-v", f"{os.getcwd()}/aether/cloud-bridge/src:/app/bridge/src:ro",
            "-e", f"IOT_ENDPOINT={iot_endpoint}",
            "-e", f"IOT_CERT=/app/certs/{drone_id}/certificate.pem",
            "-e", f"IOT_KEY=/app/certs/{drone_id}/private.key",
            "-e", f"IOT_ROOT_CA=/app/certs/AmazonRootCA1.pem"
        ])
    else:
        print("  Mode: Local MQTT (mosquitto)")
        bridge_cmd.extend([
            "-e", "LOCAL_BROKER_HOST=mosquitto",
            "-e", "LOCAL_BROKER_PORT=1883"
        ])

    bridge_cmd.append("aether-cloud-bridge")
    run_command(bridge_cmd)

    print(f"Done! Drone {instance_id} is flying.")
    print(f"Connect MAVProxy: mavproxy.py --master=tcp:127.0.0.1:{port_user} --console")

    if args.limit_logs:
        print("  Logs: Limited to ~10MB (Rotation Enabled)")

    if use_aws:
        print("AWS IoT Topics:")
        print(f"  Telemetry: mav/{drone_id}/telemetry")
        print(f"  Commands:  mav/{drone_id}/cmd")
        print(f"  Status:    mav/{drone_id}/status")
    else:
        print(f"Watch Telemetry: docker exec -it mosquitto mosquitto_sub -t 'mav/{drone_id}/#'")

if __name__ == "__main__":
    main()
