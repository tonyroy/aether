import logging
import json
from temporalio import activity
from awscrt import mqtt

# Global MQTT connection (initialized in main.py)
mqtt_connection = None
IOT_CLIENT_ID = "orchestrator"

logger = logging.getLogger(__name__)


@activity.defn
async def send_command(drone_id: str, command: str, params: dict = None) -> str:
    """
    Sends a command to a drone via MQTT.
    """
    if not mqtt_connection:
        raise RuntimeError("MQTT connection not initialized")

    if params is None:
        params = {}

    topic = f"mav/{drone_id}/cmd"
    payload = {
        "command": command,
        **params
    }

    logger.info(f"Sending command {command} to {topic}: {payload}")

    # Publish to MQTT
    future, _ = mqtt_connection.publish(
        topic=topic,
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

    future.result()  # Wait for publish to complete
    return f"Command {command} sent to {drone_id}"


@activity.defn
async def wait_for_telemetry(drone_id: str):
    """
    Placeholder for checking telemetry.
    """
    return "Telemetry OK"

@activity.defn
async def update_shadow_status(drone_id: str, status: str) -> str:
    """
    Updates the device shadow 'reported.orchestrator.status' to reflect mission state.
    Used for Fleet Indexing.
    """
    if not mqtt_connection:
        raise RuntimeError("MQTT connection not initialized")
        
    topic = f"$aws/things/{drone_id}/shadow/update"
    payload = {
        "state": {
            "reported": {
                "orchestrator": {
                    "status": status
                }
            }
        }
    }
    
    logger.info(f"Updating shadow status for {drone_id} to {status}")
    
    from awscrt import mqtt
    
    future, _ = mqtt_connection.publish(
        topic=topic,
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    
    future.result()
    return f"Shadow status updated to {status}"


@activity.defn
async def plan_mission(request: object) -> dict:
    """
    STUB: Planning Service.
    Converts a high-level request into a Mission Plan.
    Future: Call LLM or Path Planner.
    """
    # For now, return a static plan
    return {
        "mission_id": "plan-" + str(activity.info().activity_id),
        "waypoints": [
            {"type": "TAKEOFF", "alt": 10},
            {"type": "WAYPOINT", "lat": -35.363, "lon": 149.165, "alt": 20},
            {"type": "LAND"}
        ]
    }

@activity.defn
async def find_available_drone() -> str:
    """
    Queries AWS IoT Fleet Index via FleetDispatcher.
    Returns drone_id or raises ApplicationError if none found.
    """
    import boto3

    # For MVP, we instantiate here.
    iot = boto3.client('iot', region_name='ap-southeast-2')

    # Query: connected AND idle AND type=drone
    query = "connectivity.connected:true AND shadow.reported.orchestrator.status:IDLE AND attributes.type:aether-drone"

    try:
        response = iot.search_index(queryString=query)
        things = response.get('things', [])
        if not things:
            raise RuntimeError("No available drones")

        return things[0]['thingName']
    except Exception as e:
        # Rethrow as RuntimeError to trigger retry?
        raise RuntimeError(f"Failed to find drone: {e}")

@activity.defn
async def assign_mission_to_drone(drone_id: str, mission_plan: dict) -> str:
    """
    Signals the DroneEntityWorkflow.
    """
    from temporalio.client import Client
    import os
    
    temporal_addr = os.getenv("TEMPORAL_SERVICE_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_addr)
    
    from workflows import DroneEntityWorkflow
    
    handle = client.get_workflow_handle(
        f"entity-{drone_id}"
    )
    
    await handle.signal(DroneEntityWorkflow.assign_mission, mission_plan)
    return f"Assigned to {drone_id}"

@activity.defn
async def check_preflight(drone_id: str, constraints: dict) -> bool:
    """
    Verifies that the drone meets mission constraints (Battery, etc).
    Queries the Device Shadow.
    """
    import boto3
    import json
    
    if not constraints:
        return True
        
    min_battery = constraints.get("min_battery_start", 0)
    if min_battery == 0:
        return True
        
    iot = boto3.client('iot-data', region_name='ap-southeast-2')
    
    try:
        # Get Shadow
        response = iot.get_thing_shadow(thingName=drone_id)
        payload = json.loads(response['payload'].read())
        
        reported = payload.get("state", {}).get("reported", {})
        battery = reported.get("battery", 0)
        
        logger.info(f"Preflight Check {drone_id}: Battery {battery}% (Min {min_battery}%)")
        
        if battery < min_battery:
            raise RuntimeError(f"Battery too low: {battery}% < {min_battery}%")
            
        return True
        
    except Exception as e:
        logger.error(f"Preflight failed: {e}")
        raise RuntimeError(f"Preflight Check Failed: {e}")
