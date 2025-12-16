from src.workflows import DroneEntityWorkflow


class NoDroneAvailableError(Exception):
    pass

class FleetDispatcher:
    def __init__(self, temporal_client, iot_client):
        self.temporal = temporal_client
        self.iot = iot_client

    async def find_drone(self, constraints: dict = None) -> str:
        """
        Finds an available drone matching the criteria.
        Returns the drone_id (thingName) or raises NoDroneAvailableError.
        """
        # Base Query: connected AND idle AND type=drone
        # Future: Append constraint filters from 'constraints' dict
        query = (
            "connectivity.connected:true AND "
            "shadow.reported.orchestrator.status:IDLE AND "
            "attributes.type:aether-drone"
        )

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
        selected_drone = things[0]['thingName']
        return selected_drone

    async def assign_mission(self, drone_id: str, mission_plan: dict) -> str:
        """
        Signals the specific DroneEntityWorkflow to accept the mission.
        """
        # Get Temporal Workflow Handle
        handle = self.temporal.get_workflow_handle(f"entity-{drone_id}")

        # Signal the Workflow
        await handle.signal(DroneEntityWorkflow.assign_mission, mission_plan)

        return drone_id

    async def dispatch_mission(self, mission_plan: dict) -> str:
        """
        Legacy/Convenience method: Finds AND Assigns in one go.
        """
        drone_id = await self.find_drone(mission_plan.get("constraints"))
        return await self.assign_mission(drone_id, mission_plan)
