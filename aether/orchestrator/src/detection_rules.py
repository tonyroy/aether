from dataclasses import dataclass
import math
try:
    from aether_common.telemetry import DroneState
except ImportError:
    # Fallback/Mock if common not installed yet (or during initial dev setup)
    # But ideally strictly rely on it.
    pass

class SessionDetector:
    """
    Evaluates telemetry against configuration rules to detect
    Mission Start and Mission End conditions.
    """
    def __init__(self, config: dict = None):
        self.config = config or {
            "min_duration_seconds": 30.0,
            "min_distance_meters": 10.0,
            "timeout_after_disarm_sec": 600.0
        }

    def check_mission_start(self, start_sample: DroneState, current_sample: DroneState) -> bool:
        """
        Determines if a 'Candidate Session' (e.g. Armed) has matured into 
        a 'Confirmed Mission' based on duration and movement.
        """
        if not current_sample.armed:
            return False

        # 1. Check Duration
        duration = current_sample.timestamp - start_sample.timestamp
        if duration < self.config["min_duration_seconds"]:
            return False
            
        # 2. Check Distance (Haversine)
        dist = self._haversine_distance(
            start_sample.lat, start_sample.lon,
            current_sample.lat, current_sample.lon
        )
        if dist < self.config["min_distance_meters"]:
            return False
            
        return True

    def _haversine_distance(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000 # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
