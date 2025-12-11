import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from src.workflows import MissionRequestWorkflow, MissionRequest

@pytest.mark.asyncio
async def test_mission_request_flow_success():
    """
    Scenario: User submits a request, it is planned, a drone is found immediately, and dispatched.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        
        # --- Mocks ---
        @activity.defn(name="plan_mission")
        async def mock_plan(request: MissionRequest) -> dict:
            return {"mission_id": "plan-123", "waypoints": []}

        @activity.defn(name="find_available_drone")
        async def mock_find(constraints: dict = None) -> str:
            return "drone-1"

        @activity.defn(name="assign_mission_to_drone")
        async def mock_assign(drone_id: str, plan: dict) -> str:
            assert drone_id == "drone-1"
            assert plan["mission_id"] == "plan-123"
            return "assigned"

        async with Worker(
            env.client,
            task_queue="mission-queue",
            workflows=[MissionRequestWorkflow],
            activities=[mock_plan, mock_find, mock_assign],
        ):
            handle = await env.client.start_workflow(
                MissionRequestWorkflow.run,
                args=[MissionRequest("Scan the perimeter")],
                id="req-123",
                task_queue="mission-queue",
            )
            
            result = await handle.result()
            assert result == "mission_started"


@pytest.mark.asyncio
async def test_mission_request_queuing():
    """
    Scenario: Fleet is effectively full initially.
    The workflow should RETRY finding a drone until one becomes available.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        
        # --- Mocks ---
        find_attempts = 0
        
        @activity.defn(name="plan_mission")
        async def mock_plan(request: MissionRequest) -> dict:
            return {"mission_id": "queue-123"}

        @activity.defn(name="find_available_drone")
        async def mock_find_with_retry(constraints: dict = None) -> str:
            nonlocal find_attempts
            find_attempts += 1
            if find_attempts < 3:
                # Simulate "No Drone Available" by raising an error that triggers retry
                raise RuntimeError("No capacity")
            return "drone-delayed"

        @activity.defn(name="assign_mission_to_drone")
        async def mock_assign(drone_id: str, plan: dict) -> str:
            assert drone_id == "drone-delayed"
            return "assigned"

        async with Worker(
            env.client,
            task_queue="mission-queue",
            workflows=[MissionRequestWorkflow],
            activities=[mock_plan, mock_find_with_retry, mock_assign],
        ):
            handle = await env.client.start_workflow(
                MissionRequestWorkflow.run,
                args=[MissionRequest("Wait for me")],
                id="req-queue",
                task_queue="mission-queue",
            )
            
            await handle.result()
            
            # Implementation detail: Workflow should set RetryPolicy on this activity
            assert find_attempts == 3
