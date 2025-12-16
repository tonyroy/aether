import asyncio

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment

from src.workflows import DroneEntityWorkflow


@pytest.mark.asyncio
async def test_drone_entity_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:

        # Mock activities
        @activity.defn(name="update_shadow_status")
        async def mock_update_shadow(drone_id: str, status: str) -> str:
            return f"Shadow status updated to {status}"

        @activity.defn(name="send_command")
        async def mock_send_command(drone_id: str, command: str, params: dict) -> str:
            return "Command sent"

        from temporalio.worker import Worker

        from src.workflows import MissionWorkflow

        async with Worker(
            env.client,
            task_queue="mission-queue",
            workflows=[DroneEntityWorkflow, MissionWorkflow],
            activities=[mock_update_shadow, mock_send_command],
        ):
            # Start workflow
            handle = await env.client.start_workflow(
                DroneEntityWorkflow.run,
                args=["drone-test"],
                id="entity-drone-test",
                task_queue="mission-queue",
            )

            # Signal Assignment
            mission_plan = [{"lat": 0, "lon": 0}]
            await handle.signal(DroneEntityWorkflow.assign_mission, mission_plan)

            # Allow some time for processing (in time-skipping mode)
            await asyncio.sleep(1) # Unblocks the workflow to process signal

            # Signal Exit
            await handle.signal(DroneEntityWorkflow.exit_entity)

            # Verify result
            await handle.result()
