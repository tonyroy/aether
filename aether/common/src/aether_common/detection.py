import logging
import math
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from .telemetry import DroneState

logger = logging.getLogger(__name__)

# States matching AWS IoT Events concept
DetectorStateName = Literal["IDLE", "CANDIDATE", "IN_MISSION"]

@dataclass
class DetectorState:
    """
    Serializable state for the detector.
    This mimics the 'Variables' in AWS IoT Events.
    """
    state_name: DetectorStateName = "IDLE"
    start_sample: Optional[DroneState] = None
    home_position: Optional[DroneState] = None
    last_processed_timestamp: float = 0.0

class MissionDetector:
    """
    Pure Logic State Machine for Mission Detection.
    designed to be portable (run in Lambda, Local Script, or Orchestrator).
    """

    MIN_DURATION_SEC = 30
    MIN_DISTANCE_M = 10

    @staticmethod
    def evaluate(current_state: DetectorState, sample: DroneState) -> Tuple[DetectorState, Optional[str]]:
        """
        Transition function: (State, Input) -> (NewState, Event)
        Event can be: 'MISSION_STARTED', 'MISSION_ENDED', or None.
        """
        logger.info(f"Processing sample: {sample}")
        if not sample.timestamp:
            return current_state, None

        # 0. Always track Home Position if received
        # Ensure we handle Enum or String (depending on how sample was created)
        type_str = str(sample.type.value) if hasattr(sample.type, 'value') else str(sample.type)
        if type_str == "HOME_POSITION":
            current_state.home_position = sample
            return current_state, None

        # Logic Branching based on Current State
        if current_state.state_name == "IDLE":
            if sample.armed:
                # Transition: IDLE -> CANDIDATE
                # Preserve existing home_position
                return DetectorState(
                    state_name="CANDIDATE",
                    start_sample=sample,
                    home_position=current_state.home_position,
                    last_processed_timestamp=sample.timestamp
                ), None

        elif current_state.state_name == "CANDIDATE":
            # Only reset if explicitly False. (None == partial update -> ignore)
            if sample.armed is False:
                # Disarmed during checks -> Reset to IDLE
                # Preserve home_position
                return DetectorState(
                    state_name="IDLE",
                    home_position=current_state.home_position
                ), None

            # Check Criteria
            start = current_state.start_sample
            if not start: # Safety
                return DetectorState("IDLE"), None

            # 1. Backfill Position if missing (e.g. started by Heartbeat)
            # Strategy:
            # A) If start sample has no pos, and THIS sample has pos -> update start
            # B) If start sample has no pos, but we have HOME -> use Home as ref

            ref_sample = start

            if start.lat is None:
                if current_state.home_position:
                     # Fallback to Home Position as reference
                     ref_sample = current_state.home_position
                elif sample.lat is not None:
                    # Backfill 'start' with current fix
                    start.lat = sample.lat
                    start.lon = sample.lon
                    start.alt = sample.alt
                    ref_sample = start # Use backfilled start

            duration = sample.timestamp - start.timestamp
            dist = MissionDetector._calculate_distance(ref_sample, sample)

            if duration >= MissionDetector.MIN_DURATION_SEC:
                if dist >= MissionDetector.MIN_DISTANCE_M:
                    # Criteria Met! -> IN_MISSION
                    return DetectorState(
                        state_name="IN_MISSION",
                        start_sample=start,
                        home_position=current_state.home_position,
                        last_processed_timestamp=sample.timestamp
                    ), "MISSION_STARTED"
                else:
                    # Duration met but not distance? Stay Candidate?
                    # Or fail? AWS IoT Events typically keeps checking.
                    pass

        elif current_state.state_name == "IN_MISSION":
            if sample.armed is False:
                # Disarmed -> Mission End
                return DetectorState("IDLE"), "MISSION_ENDED"

            # Persist state (update timestamp if needed)
            current_state.last_processed_timestamp = sample.timestamp
            return current_state, None

        return current_state, None

    @staticmethod
    def _calculate_distance(s1: DroneState, s2: DroneState) -> float:
        if s1.lat is None or s1.lon is None or s2.lat is None or s2.lon is None:
            return 0.0
        # Euclidean approx for short distances (sufficient for 10m check)
        # 1 deg lat ~ 111km. 1 deg lon ~ 111km * cos(lat)
        # Simplified:
        return math.sqrt(
            (s2.lat - s1.lat)**2 +
            (s2.lon - s1.lon)**2
        ) * 111139
