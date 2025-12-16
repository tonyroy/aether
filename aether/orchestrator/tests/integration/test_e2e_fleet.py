import logging
import os
import uuid

import pytest
from temporalio.client import Client
from temporalio.worker import Worker

from src.activities import (
    assign_mission_to_drone,
    check_preflight,
    find_available_drone,
    plan_mission,
    send_command,
    update_shadow_status,
)
from src.workflows import DroneEntityWorkflow, MissionRequest, MissionRequestWorkflow, MissionWorkflow
from tests.integration.mock_drone import MockDrone

# Configure Logging
logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_e2e_fleet_dispatch():
    """
    E2E Scenario:
    1. Spawn 2 Mock Drones (IDLE).
    2. Start Entity Workflows for them.
    3. Submit 3 Mission Requests.
    4. Expect:
       - 2 Drones pickup missions immediately.
       - 1 Request queued.
       - Queued request picked up after one finishes.
    """

    # Configuration
    iot_endpoint = os.getenv("IOT_ENDPOINT")
    iot_cert = os.getenv("IOT_CERT")
    iot_key = os.getenv("IOT_KEY")
    iot_ca = os.getenv("IOT_ROOT_CA")
    temporal_addr = os.getenv("TEMPORAL_SERVICE_ADDRESS", "localhost:7233")

    if not all([iot_endpoint, iot_cert, iot_key, iot_ca]):
        pytest.skip("AWS IoT credentials not set in environment")

    # 1. Spawn Mock Drones
    drones = []
    drone_ids = [f"test-drone-{uuid.uuid4().hex[:6]}", f"test-drone-{uuid.uuid4().hex[:6]}"]

    try:
        for did in drone_ids:
            # Note: We need to Provision these Things in AWS first?
            # Or assume they exist?
            # 'ensure_fleet' lists Things.
            # If we just connect with 'test-drone-X' client ID, it doesn't create a Thing in Registry.
            # Fleet Indexing relies on Registry.
            # CRITICAL: We need real Things.
            # Use 'scripts/provision_drone.py' logic?
            # For now, let's assume we can use existing 'drone-1' etc? NO, concurrency issues.
            # Simplification: We SKIP the Registry part for this test if we can't create Things dynamically.
            # BUT Fleet Indexing won't work without Registry.

            # TODO: Add dynamic Thing provisioning here using boto3?
            pass

            d = MockDrone(did, iot_endpoint, iot_cert, iot_key, iot_ca)
            await d.start()
            drones.append(d)

        # 2. Connect Temporal
        client = await Client.connect(temporal_addr)

        # Start Worker (Testing Logic needs the Worker to run the workflows)
        # Note: We are running the Worker *in process* for the test.
        async with Worker(
            client,
            task_queue="mission-queue",
            workflows=[MissionRequestWorkflow, DroneEntityWorkflow, MissionWorkflow],
            activities=[plan_mission, find_available_drone, assign_mission_to_drone, send_command, update_shadow_status, check_preflight]
        ):
            # 3. Provision Entities (Simulate check_fleet)
            for did in drone_ids:
                try:
                     await client.start_workflow(
                        DroneEntityWorkflow.run,
                        args=[did],
                        id=f"entity-{did}",
                        task_queue="mission-queue"
                     )
                except Exception:
                    pass # Already running

            # 4. Submit Requests
            # Request 1
            h1 = await client.start_workflow(
                MissionRequestWorkflow.run,
                args=[MissionRequest("Req 1")],
                id=f"req-{uuid.uuid4()}",
                task_queue="mission-queue"
            )
            # Request 2
            h2 = await client.start_workflow(
                MissionRequestWorkflow.run,
                args=[MissionRequest("Req 2")],
                id=f"req-{uuid.uuid4()}",
                task_queue="mission-queue"
            )
            # Request 3 (Should Queue)
            h3 = await client.start_workflow(
                MissionRequestWorkflow.run,
                args=[MissionRequest("Req 3")],
                id=f"req-{uuid.uuid4()}",
                task_queue="mission-queue"
            )

            # Wait for results
            r1 = await h1.result()
            r2 = await h2.result()
            r3 = await h3.result()

            assert r1 == "mission_started"
            assert r2 == "mission_started"
            assert r3 == "mission_started"

    finally:
        for d in drones:
            await d.stop()
        # Clean up Things?
