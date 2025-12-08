from temporalio.client import Client
import asyncio
import os

async def main():
    temporal_addr = os.getenv("TEMPORAL_SERVICE_ADDRESS", "localhost:7233")
    client = await Client.connect(temporal_addr)
    
    drone_id = "drone-1"
    workflow_id = f"entity-{drone_id}"
    
    print(f"Signaling {workflow_id} to start mission...")
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(
            "assign_mission",
            [{"lat": -35.363, "lon": 149.165, "alt": 10}]
        )
        print("✅ Signal 'assign_mission' sent successfully!")
    except Exception as e:
        print(f"❌ Failed to signal: {e}")

if __name__ == "__main__":
    asyncio.run(main())
