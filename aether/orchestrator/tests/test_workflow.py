
import pytest
from temporalio import activity
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

from src.workflows import MissionWorkflow


# Mock Activity
@activity.defn(name="send_command")
async def mock_send_command(drone_id: str, command: str, params: dict = None) -> str:
    return f"Mock sent {command}"




@pytest.mark.asyncio
async def test_mission_workflow_success():
    """
    Test that the workflow executes the correct sequence of commands:
    ARM -> TAKEOFF -> LAND
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[MissionWorkflow],
            activities=[mock_send_command],
        ):

            result = await env.client.execute_workflow(
                MissionWorkflow.run,
                args=["drone-test", []],
                id="test-mission-1",
                task_queue="test-queue",
            )

            assert result == "Mission Complete"
