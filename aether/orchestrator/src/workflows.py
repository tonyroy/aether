from temporalio import workflow
from datetime import timedelta

# Import activity definitions for type hints if needed, or string names
# from activities import send_command, update_shadow_status

@workflow.defn
class MissionWorkflow:
    @workflow.run
    async def run(self, drone_id: str, mission_plan: list):
        workflow.logger.info(f"Starting mission for {drone_id}")
        
        # 1. Arm Drone
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "ARM", {}],
            start_to_close_timeout=timedelta(seconds=20)
        )
        
        # 2. Takeoff
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "TAKEOFF", {"alt": 10}],
            start_to_close_timeout=timedelta(seconds=20)
        )
        
        # 3. Simulate Waypoints
        for wp in mission_plan:
            workflow.logger.info(f"Going to waypoint {wp}")
            await workflow.sleep(timedelta(seconds=5))
        # 4. Land
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "LAND", {}],
            start_to_close_timeout=timedelta(seconds=20)
        )
        
        return "Mission Complete"

@workflow.defn
class DroneEntityWorkflow:
    """
    Persistent Entity Workflow representing a single Drone.
    Maintains state lock and ensures serial execution of missions.
    """
    
    def __init__(self):
        self._status = "IDLE"
        self._pending_mission = None
        self._exit = False

    @workflow.signal
    def assign_mission(self, mission_plan: list):
        if self._status != "IDLE":
             workflow.logger.warn("Drone is busy, rejecting mission signal (in real implementation, send rejection)")
             return
        self._pending_mission = mission_plan

    @workflow.signal
    def exit_entity(self):
        self._exit = True

    @workflow.run
    async def run(self, drone_id: str):
        workflow.logger.info(f"Entity Workflow started for {drone_id}")
        
        # Ensure 'reported.orchestrator.status' is IDLE on startup
        await workflow.execute_activity(
            "update_shadow_status",
            args=[drone_id, "IDLE"],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        while not self._exit:
            # Wait for a mission or exit
            await workflow.wait_condition(lambda: self._pending_mission is not None or self._exit)
            
            if self._exit:
                break
                
            if self._pending_mission:
                mission = self._pending_mission
                self._pending_mission = None # Clear pending
                
                # Lock
                self._status = "ON_MISSION"
                
                # Update Shadow -> BUSY
                await workflow.execute_activity(
                    "update_shadow_status",
                    args=[drone_id, "BUSY"],
                    start_to_close_timeout=timedelta(seconds=10)
                )
                
                try:
                    # Execute Child Workflow
                    workflow.logger.info(f"Dispatching MissionWorkflow for {drone_id}")
                    await workflow.execute_child_workflow(
                        MissionWorkflow.run,
                        args=[drone_id, mission],
                        id=f"mission-{drone_id}-{workflow.uuid()}", # Unique ID for child
                        task_queue="mission-queue", # Keep on same queue
                    )
                except Exception as e:
                    workflow.logger.error(f"Mission failed: {e}")
                finally:
                    # Unlock
                    self._status = "IDLE"
                    
                    # Update Shadow -> IDLE
                    await workflow.execute_activity(
                        "update_shadow_status",
                        args=[drone_id, "IDLE"],
                        start_to_close_timeout=timedelta(seconds=10)
                    )
        
        workflow.logger.info(f"Entity Workflow exiting for {drone_id}")
