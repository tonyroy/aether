import asyncio
import boto3
import os
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from workflows import DroneEntityWorkflow
from dotenv import load_dotenv

load_dotenv()


async def main():
    print("search for Fleet of Drones...")

    # 1. List Things from AWS IoT
    iot = boto3.client('iot', region_name='ap-southeast-2')

    # List (simplified, assuming small fleet)
    response = iot.list_things(maxResults=100)
    things = response.get('things', [])

    print(f"Found {len(things)} drones in registry.")

    # 2. Connect to Temporal
    temporal_addr = os.getenv("TEMPORAL_SERVICE_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_addr)

    # 3. Ensure Entity Workflow for each
    for t in things:
        attributes = t.get('attributes', {})
        if attributes.get('type') != 'aether-drone':
            # Skip non-project things
            continue

        drone_id = t['thingName']
        workflow_id = f"entity-{drone_id}"

        print(f"Checking entity workflow for {drone_id}...")

        try:
            handle = await client.start_workflow(
                DroneEntityWorkflow.run,
                args=[drone_id],
                id=workflow_id,
                task_queue="mission-queue",
                # If running, do nothing. If failed/completed, restart.
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
            )
            print(f"✅ Started Entity Workflow for {drone_id} ({handle.run_id})")
        except Exception as e:
            # WorkflowAlreadyStartedError is raised if running
            if "Workflow execution is already running" in str(e):
                print(f"⏩ Entity for {drone_id} is already running.")
            else:
                print(f"❌ Failed to start entity for {drone_id}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
