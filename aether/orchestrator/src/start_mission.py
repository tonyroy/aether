import asyncio
import os

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from workflows import MissionWorkflow


async def main():
    # Connect to client
    temporal_addr = os.getenv("TEMPORAL_SERVICE_ADDRESS", "localhost:7233")
    print(f"Connecting to Temporal at {temporal_addr}...")
    client = await Client.connect(temporal_addr)

    # Start workflow
    drone_id = "drone-1"

    print(f"Starting MissionWorkflow for {drone_id}...")

    handle = await client.start_workflow(
        MissionWorkflow.run,
        args=[drone_id, [{"lat": -35.363, "lon": 149.165, "alt": 10}]],
        id=f"mission-{drone_id}-1",
        task_queue="mission-queue",
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )

    print(f"Started workflow {handle.id}")
    print(f"View at: http://localhost:8080/namespaces/default/workflows/{handle.id}")

    # Wait for result
    result = await handle.result()
    print(f"Workflow result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
