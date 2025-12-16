from .telemetry import DroneTelemetry, Type
from .mission_plan import MissionPlan, Waypoint
from .events import MissionStartedEvent, Context, Trigger, StartLocation, Firmware, GeofenceItem

# Aliases for backward compatibility with handcrafted code
DroneState = DroneTelemetry
TelemetryType = Type
