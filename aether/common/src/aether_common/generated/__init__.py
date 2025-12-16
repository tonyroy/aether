from .events import Context, Firmware, GeofenceItem, MissionStartedEvent, StartLocation, Trigger
from .mission_plan import MissionPlan, Waypoint
from .telemetry import DroneTelemetry, Type

# Aliases for backward compatibility with handcrafted code
DroneState = DroneTelemetry
TelemetryType = Type
