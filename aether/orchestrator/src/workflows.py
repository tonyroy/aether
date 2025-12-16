import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from dataclasses import dataclass

# Import activity definitions for type hints if needed, or string names
# from activities import send_command, update_shadow_status

@workflow.defn
class MissionWorkflow:
    @workflow.run
    async def run(self, drone_id: str, mission_plan: Any):
        workflow.logger.info(f"Starting mission for {drone_id}")

        # 0. Pre-flight Checks
        constraints = mission_plan.get("constraints", {}) if isinstance(mission_plan, dict) else {}
        # Note: mission_plan argument type hints say 'list' but MissionRequestWorkflow sends 'dict' (the plan).
        # We need to handle both legacy list-of-waypoints and new dict-plan.

        waypoints = []
        if isinstance(mission_plan, list):
             waypoints = mission_plan
        elif isinstance(mission_plan, dict):
             waypoints = mission_plan.get("waypoints", [])
             constraints = mission_plan.get("constraints", {})

        if constraints:
            await workflow.execute_activity(
                "check_preflight",
                args=[drone_id, constraints],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1)
            )

        # 1. Arm Drone
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "ARM", {}],
            start_to_close_timeout=timedelta(seconds=20)
        )

        # 2. Takeoff
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "TAKEOFF", {"alt": 10}],
            start_to_close_timeout=timedelta(seconds=20)
        )

        # 3. Simulate Waypoints
        for wp in waypoints:
            workflow.logger.info(f"Going to waypoint {wp}")
            await workflow.sleep(timedelta(seconds=5))
        # 4. Land
        await workflow.execute_activity(
            "send_command",
            args=[drone_id, "LAND", {}],
            start_to_close_timeout=timedelta(seconds=20)
        )

        return "Mission Complete"

try:
    from detection_rules import DroneState, SessionDetector
except ImportError:
    # Fallback for when running from root (e.g. pytest) without src in path
    from src.detection_rules import DroneState, SessionDetector

@workflow.defn
class SessionRecordingWorkflow:
    """
    Child workflow that records a confirmed flight session.
    """
    @workflow.signal
    def end_custom_session(self):
        self._is_active = False

    @workflow.run
    async def run(self, drone_id: str, session_id: str):
        workflow.logger.info(f"RECORDING SESSION {session_id} for {drone_id}")
        self._is_active = True

        # In a real impl, this would buffer logs to S3/Timestream
        while self._is_active:
             await workflow.sleep(timedelta(seconds=5))
             workflow.logger.info(f"Session {session_id} active...")

        workflow.logger.info(f"Session {session_id} ENDED")
        return "Session Recorded"

@workflow.defn
class DroneEntityWorkflow:
    """
    Passive Drone Entity (Digital Twin).
    Monitors telemetry to detect and record sessions.
    """
    def __init__(self):
        self._status = "OFFLINE"
        self._exit = False
        self._latest_telemetry: DroneState = None
        self._session_start_sample: DroneState = None
        self._active_session_handle = None

        # Configurable Rules
        self._detector = SessionDetector()

    @workflow.signal
    def signal_telemetry(self, sample_dict: dict):
        # Convert dict to dataclass safely
        incoming = DroneState.from_dict(sample_dict)

        if self._latest_telemetry is None:
            self._latest_telemetry = incoming
        else:
            # Merge fields: update if incoming has value
            # We can use asdict to iterate, or manual checking
            # Since dataclass fields are optional, we only overwrite if not None
            for field in incoming.__dataclass_fields__:
                val = getattr(incoming, field)
                if val is not None:
                    setattr(self._latest_telemetry, field, val)

        # Update status based on merged state
        is_armed = self._latest_telemetry.armed if self._latest_telemetry.armed is not None else False
        self._status = "ONLINE_IDLE" if not is_armed else "ONLINE_ARMED"

    @workflow.signal
    def exit_entity(self):
        self._exit = True

    @workflow.signal
    def assign_mission(self, mission_plan: dict):
        """
        Receives a mission plan (Active Command).
        For valid hybrid operation, this should start a MissionWorkflow child.
        For now, we just log it to satisfy the interface.
        """
        workflow.logger.info(f"Received Mission Assigment: {mission_plan.get('id', 'unknown')}")
        # In future: self._active_mission_future = await workflow.start_child_workflow(MissionWorkflow...)

    @workflow.run
    async def run(self, drone_id: str):
        workflow.logger.info(f"Passive Entity started for {drone_id}")

        while not self._exit:
            await workflow.wait_condition(lambda: self._latest_telemetry is not None or self._exit)
            if self._exit:
                break

            current = self._latest_telemetry
            self._latest_telemetry = None # Consume event logic

            # State Machine Logic
            is_in_mission = (self._active_session_handle is not None)

            if not is_in_mission:
                # Try to Detect Start
                if current.armed:
                    if self._session_start_sample is None:
                        self._session_start_sample = current # Candidate Start

                    # Check confirmation
                    confirmed = self._detector.check_mission_start(self._session_start_sample, current)
                    if confirmed:
                        workflow.logger.info(f"Mission CONFIRMED for {drone_id}")
                        session_id = f"sess-{workflow.uuid()}"

                        # Start Recording Child
                        self._active_session_handle = await workflow.start_child_workflow(
                            SessionRecordingWorkflow.run,
                            args=[drone_id, session_id],
                            id=session_id,
                            task_queue="mission-queue"
                        )
                else:
                    # Reset candidate if disarmed before confirmation
                    self._session_start_sample = None

            else:
                # We are IN_MISSION
                if not current.armed:
                    workflow.logger.info(f"Drone DISARMED. Starting Session Timeout ({self._detector.config['timeout_after_disarm_sec']}s)...")

                    # Wait for Re-Arm OR Timeout
                    # We need a condition that matches: "New Telemetry with Armed=True" OR "Time has passed"

                    try:
                        await workflow.wait_condition(
                            lambda: (self._latest_telemetry is not None and self._latest_telemetry.armed) or self._exit,
                            timeout=timedelta(seconds=self._detector.config["timeout_after_disarm_sec"])
                        )
                    except asyncio.TimeoutError:
                        # Real Timeout -> End Session
                        workflow.logger.info("Session Timeout Reached. Ending Session.")
                        await self._active_session_handle.signal(SessionRecordingWorkflow.end_custom_session)
                        self._active_session_handle = None
                        self._session_start_sample = None
                    else:
                        if self._exit:
                            break
                        # If we woke up because of Re-Arm (latest_telemetry.armed is True)
                        # We just continue the loop, creating a "Continuous Session"
                        workflow.logger.info("Drone RE-ARMED. Session Continuing.")
                        # We let the main loop handle the new telemetry sample in next iteration (if wait_condition doesn't consume it?)
                        # Actually wait_condition doesn't consume. self._latest_telemetry is still set.
                        # The Main Loop 'latest_telemetry = None' happens at TOP.
                        # So we need to be careful not to lose this sample?
                        # Since we are inside the 'else' block which processes 'current', the 'latest_telemetry'
                        # that woke us up is NEW and hasn't been processed by the top of loop yet.
                        # Correct.
                        pass

        workflow.logger.info(f"Entity exiting {drone_id}")




@dataclass
@dataclass
class MissionRequest:
    description: str
    priority: int = 1

@workflow.defn
class MissionRequestWorkflow:
    @workflow.run
    async def run(self, request: MissionRequest) -> str:
        # 1. Plan Mission (Stub - Future: LLM)
        mission_plan = await workflow.execute_activity(
            "plan_mission",
            args=[request],
            start_to_close_timeout=timedelta(minutes=1)
        )

        # 2. Dispatch to Fleet
        # Uses FleetDispatcher to find and signal a drone in one atomic operation
        retry_policy = RetryPolicy(
             initial_interval=timedelta(seconds=2),
             maximum_interval=timedelta(seconds=30),
             # indefinite retry by default if maximum_attempts not set
        )

        assigned_drone_id = await workflow.execute_activity(
            "find_available_drone",
            args=[mission_plan.get("constraints", {})],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy
        )

        # 3. Dispatch to Drone
        await workflow.execute_activity(
            "assign_mission_to_drone",
            args=[assigned_drone_id, mission_plan],
            start_to_close_timeout=timedelta(minutes=1), # No retry on assignment usually, or different policy
        )

        return "mission_started"
