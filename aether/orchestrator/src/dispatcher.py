class NoDroneAvailableError(Exception):
    pass

class FleetDispatcher:
    def __init__(self, temporal_client, iot_client):
        self.temporal = temporal_client
        self.iot = iot_client

    async def dispatch_mission(self, mission_plan: dict) -> str:
        """
        Dispatches a mission to an available drone.
        """
        raise NotImplementedError("TDD: Implement me")
