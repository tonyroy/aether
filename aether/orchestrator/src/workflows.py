from temporalio import workflow
from datetime import timedelta

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
        
        # 3. Dummy Wait (simulate flight)
        await workflow.sleep(timedelta(seconds=5))
        
        # 4. Land
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "LAND", {}],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return "Mission Complete"
