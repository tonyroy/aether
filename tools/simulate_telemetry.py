import asyncio
import json
import time
import random

# Simulates a drone sending telemetry patterns
class TelemetrySimulator:
    def __init__(self, callback):
        self.callback = callback
        self.state = {
            "armed": False,
            "alt": 0.0,
            "lat": -35.0,
            "lon": 149.0,
            "battery": 100.0,
            "gps_fix": 3
        }

    async def emit(self):
        """Emits current state"""
        if self.callback:
            await self.callback(self.state)

    async def run_pattern(self, pattern_name: str):
        print(f"--- Running Pattern: {pattern_name} ---")
        
        if pattern_name == "false_start":
            # Arm -> Wait 10s -> Disarm
            self.state["armed"] = True
            await self.emit()
            for _ in range(10):
                await asyncio.sleep(1)
                self.state["battery"] -= 0.01
                await self.emit()
            self.state["armed"] = False
            await self.emit()
            
        elif pattern_name == "mission_success":
            # Arm -> Takeoff -> Fly (Move) -> Land -> Disarm
            self.state["armed"] = True
            await self.emit()
            
            # Takeoff
            for i in range(5):
                self.state["alt"] += 2.0
                await asyncio.sleep(1)
                await self.emit()
                
            # Fly
            for i in range(35): # > 30s threshold
                self.state["lat"] += 0.0001
                self.state["lon"] += 0.0001
                self.state["battery"] -= 0.1
                await asyncio.sleep(1)
                await self.emit()
                
            # Land
            while self.state["alt"] > 0:
                self.state["alt"] -= 1.0
                await asyncio.sleep(1)
                await self.emit()
                
            self.state["armed"] = False
            await self.emit()

async def mock_mqtt_publish(payload):
    # In real life, this publishes to AWS IoT
    # For now, just print or could pipe to a local logic handler
    print(f"[MQTT] Payload: {json.dumps(payload)}")

if __name__ == "__main__":
    sim = TelemetrySimulator(mock_mqtt_publish)
    asyncio.run(sim.run_pattern("false_start"))
    # asyncio.run(sim.run_pattern("mission_success"))
