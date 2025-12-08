import logging
from temporalio import activity
import json
import asyncio

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
    # mqtt_connection.publish(...) logic depends on SDK used (awsiotsdk v2)
    # We assume mqtt_connection is an awscrt.mqtt.Connection
    
    from awscrt import mqtt
    
    future, _ = mqtt_connection.publish(
        topic=topic,
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    
    future.result() # Wait for publish to complete
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
