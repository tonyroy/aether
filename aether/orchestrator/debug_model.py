from aether_common.telemetry import TelemetrySample, TelemetryType
import json
from dataclasses import asdict

print("Import successful")

data = {"timestamp": 1000.0, "armed": True, "lat": 0.0, "lon": 0.0, "alt": 0.0}
print(f"Input: {data}")

try:
    sample = TelemetrySample.from_dict(data)
    print(f"Output: {sample}")
    print(f"Type: {sample.type}")
    
    assert sample.type == TelemetryType.HEARTBEAT
    assert sample.armed == True
    print("Assertion passed")
except Exception as e:
    print(f"FAILED: {e}")
