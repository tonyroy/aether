#!/usr/bin/env python3
import subprocess
import sys


def get_docker_containers(filter_name):
    """Get list of container names matching a filter."""
    try:
        cmd = f"docker ps -a -q -f name={filter_name}"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        if not output:
            return []

        # Get names for better logging
        ids = output.split()
        names = []
        for container_id in ids:
            name_cmd = f"docker inspect --format '{{{{.Name}}}}' {container_id}"
            name = subprocess.check_output(name_cmd, shell=True).decode('utf-8').strip().lstrip('/')
            names.append(name)
        return names
    except subprocess.CalledProcessError:
        return []

def main():
    print("🧹 Cleaning up drone environment...")

    # 1. Find containers
    sitl_containers = get_docker_containers("sitl-drone-*")
    bridge_containers = get_docker_containers("cloud-bridge-*")
    all_containers = sitl_containers + bridge_containers

    if not all_containers:
        print("✅ No drone containers found.")
    else:
        print(f"Found {len(all_containers)} containers:")
        for name in all_containers:
            print(f"  - {name}")

        # 2. Kill and remove
        print("\nStopping and removing containers...")
        cmd = f"docker rm -f {' '.join(all_containers)}"
        try:
            subprocess.check_call(cmd, shell=True)
            print("✅ Cleanup complete!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during cleanup: {e}")
            sys.exit(e.returncode)

    # 3. Optional: Prune networks (if empty)
    # subprocess.call("docker network prune -f", shell=True)

if __name__ == "__main__":
    main()
