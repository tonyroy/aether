import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.workflows import MissionWorkflow

# TDD Spec for Pre-flight Safety Checks

@pytest.mark.asyncio
async def test_mission_safety_battery_failure():
    """
    Scenario: Drone battery is 20%, but Mission requires 30%.
    Expectation: Workflow fails (or raises ApplicationError) BEFORE Arming.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:

        # Mocks
        @activity.defn(name="check_preflight")
        async def mock_check(drone_id: str, constraints: dict) -> bool:
            # Simulate check failure
            # In real life, this activity would query telemetry
            if constraints.get("min_battery_start", 0) > 20: # Drone has 20
                raise ApplicationError("Preflight Check Failed: Battery 20% < Required 30%", non_retryable=True)
            return True

        @activity.defn(name="send_command")
        async def mock_cmd(drone_id: str, cmd: str, params: dict):
            if cmd == "ARM":
                pytest.fail("Should not attempt to ARM if preflight failed")
            return "ok"

        async with Worker(
            env.client,
            task_queue="mission-queue",
            workflows=[MissionWorkflow],
            activities=[mock_check, mock_cmd],
        ):
            # Mission with constraints
            mission_plan = {
                "mission_id": "unsafe-1",
                "constraints": {"min_battery_start": 30},
                "waypoints": []
            }

            with pytest.raises(Exception) as excinfo:
                await env.client.execute_workflow(
                    MissionWorkflow.run,
                    args=["drone-1", mission_plan],
                    id="safety-test",
                    task_queue="mission-queue",
                )

            # Check cause
            assert excinfo.value.cause is not None
            assert excinfo.value.cause.cause is not None
            assert "Preflight Check Failed" in str(excinfo.value.cause.cause)
