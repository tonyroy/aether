from dataclasses import dataclass, asdict
from typing import Optional, Literal
from .generated import DroneTelemetry, Type

# Re-export Type for convenience if needed, or map it
TelemetryType = Type

@dataclass
class TelemetrySample(DroneTelemetry):
    """
    Unified telemetry model matching schemas/telemetry.json.
    Inherits from auto-generated DroneTelemetry class.
    Adds helper methods for dict conversion and safety.
    """
    
    @classmethod
    def from_dict(cls, data: dict):
        """
        Safe factory method that ignores unknown fields provided in the dict.
        """
        # Filter dict to only known fields
        # Use __annotations__ from both self and parent
        # Actually dataclasses.fields(cls) is safer for inheritance
        from dataclasses import fields
        known_fields = {f.name for f in fields(cls)}
        
        # Convert string enum 'type' to Enum object if necessary
        # The generated code expects an Enum for 'type'.
        # Incoming JSON usually has string 'HEARTBEAT'.
        if 'type' in data and isinstance(data['type'], str):
            try:
                data['type'] = TelemetryType(data['type'])
            except ValueError:
                data['type'] = TelemetryType.HEARTBEAT
        elif 'type' not in data:
            data['type'] = TelemetryType.HEARTBEAT
                
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def to_dict(self, exclude_none=True) -> dict:
        """
        Convert to dictionary, optionally excluding None values (for compact MQTT payloads)
        """
        d = asdict(self)
        
        # Convert Enum back to value (string) for serialization
        if isinstance(d.get('type'), TelemetryType):
             d['type'] = d['type'].value
             
        if exclude_none:
            return {k: v for k, v in d.items() if v is not None}
        return d
