from awscrt import mqtt
from src.workflows import DroneEntityWorkflow

class NoDroneAvailableError(Exception):
    pass

class FleetDispatcher:
    def __init__(self, temporal_client, iot_client):
        self.temporal = temporal_client
        self.iot = iot_client

    async def dispatch_mission(self, mission_plan: dict) -> str:
        """
        Dispatches a mission to an available drone.
        1. Query AWS IoT Index for IDLE & ONLINE drones.
        2. Select the best drone (currently first available).
        3. Signal the DroneEntityWorkflow to accept the mission.
        """
        # Query: connected AND idle AND type=drone
        # Note: 'attributes.type' is a custom attribute we assume exists on the Thing
        query = "connectivity.connected:true AND shadow.reported.orchestrator.status:IDLE AND attributes.type:aether-drone"

        # Execute Search
        try:
            response = self.iot.search_index(queryString=query)
            things = response.get('things', [])
        except Exception as e:
            # If search fails, we can't dispatch
            raise RuntimeError(f"Failed to query fleet index: {e}")

        if not things:
            raise NoDroneAvailableError("No drones available matching criteria")

        # Select first one (Naïve dispatch)
        # Future: Sort by battery level or proximity
        selected_drone = things[0]['thingName']

        # Get Temporal Workflow Handle
        handle = self.temporal.get_workflow_handle(f"entity-{selected_drone}")

        # Signal the Workflow
        await handle.signal(DroneEntityWorkflow.assign_mission, mission_plan)

        return selected_drone
