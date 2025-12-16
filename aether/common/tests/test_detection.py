import pytest
from aether_common.detection import MissionDetector, DetectorState
from aether_common.telemetry import DroneState, TelemetryType

def create_sample(timestamp: float, armed: bool, lat: float, lon: float):
    return DroneState(
        type=TelemetryType.HEARTBEAT,
        timestamp=timestamp,
        armed=armed,
        lat=lat,
        lon=lon,
        alt=10.0
    )

def test_idle_to_candidate():
    # GIVEN
    state = DetectorState("IDLE")
    sample = create_sample(100.0, True, 0.0, 0.0)
    
    # WHEN
    new_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN
    assert new_state.state_name == "CANDIDATE"
    assert new_state.start_sample == sample
    assert event is None

def test_candidate_disarm_resets():
    # GIVEN
    start = create_sample(100.0, True, 0.0, 0.0)
    state = DetectorState("CANDIDATE", start_sample=start)
    
    # WHEN: Drone disarms at t=105
    sample = create_sample(105.0, False, 0.0, 0.0)
    new_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN
    assert new_state.state_name == "IDLE"
    assert event is None

def test_candidate_insufficient_time_stays_candidate():
    # GIVEN
    start = create_sample(100.0, True, 0.0, 0.0)
    state = DetectorState("CANDIDATE", start_sample=start)
    
    # WHEN: t=120 (20s elapsed < 30s)
    sample = create_sample(120.0, True, 0.0001, 0.0) # moved slightly
    new_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN
    assert new_state.state_name == "CANDIDATE"
    assert event is None

def test_candidate_success_trigger():
    # GIVEN
    start = create_sample(100.0, True, 0.0, 0.0)
    state = DetectorState("CANDIDATE", start_sample=start)
    
    # WHEN: t=135 (35s elapsed > 30s) AND moved > 10m
    # 0.0002 deg lat is approx 22m
    sample = create_sample(135.0, True, 0.0002, 0.0)
    new_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN
    assert new_state.state_name == "IN_MISSION"
    assert event == "MISSION_STARTED"
    assert new_state.start_sample == start

def test_in_mission_ends_on_disarm():
    # GIVEN
    start = create_sample(100.0, True, 0.0, 0.0)
    state = DetectorState("IN_MISSION", start_sample=start)
    
    # WHEN
    sample = create_sample(200.0, False, 0.0, 0.0)
    new_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN
    assert new_state.state_name == "IDLE"
    assert event == "MISSION_ENDED"

def test_candidate_ignores_partial_updates():
    # GIVEN
    start = create_sample(100.0, True, 0.0, 0.0)
    state = DetectorState("CANDIDATE", start_sample=start)
    
    # WHEN: Update with NO armed status (e.g. just Position)
    sample = DroneState(
        type=TelemetryType.GLOBAL_POSITION_INT,
        timestamp=110.0,
        lat=0.0,
        lon=0.0,
        armed=None # Explicitly None
    )
    
    new_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN
    assert new_state.state_name == "CANDIDATE" # Should NOT reset
    assert event is None

def test_candidate_backfills_position():
    # GIVEN: Started with Heartbeat (No GPS)
    start = create_sample(100.0, True, None, None) 
    state = DetectorState("CANDIDATE", start_sample=start)
    
    # WHEN: Update with Position (t=110)
    # We still haven't met duration (10s) or distance (ref was None)
    # But this step should establish the ref.
    sample = create_sample(110.0, True, 0.0, 0.0) 
    new_state, _ = MissionDetector.evaluate(state, sample)
    
    # THEN: Start sample should now have position
    assert new_state.start_sample.lat == 0.0
    
    # WHEN: t=140 (40s later) AND moved
    sample2 = create_sample(140.0, True, 0.0002, 0.0)
    final_state, event = MissionDetector.evaluate(new_state, sample2)
    
    # THEN: Success
    assert final_state.state_name == "IN_MISSION"
    assert event == "MISSION_STARTED"

def test_candidate_uses_home_position_fallback():
    # GIVEN: Home Position Known
    state = DetectorState("IDLE")
    home = DroneState(
        type=TelemetryType.HOME_POSITION, 
        timestamp=90.0, 
        lat=0.0, lon=0.0, alt=0.0,
        armed=False
    )
    # Process Home
    state, _ = MissionDetector.evaluate(state, home)
    assert state.home_position == home
    
    # GIVEN: Armed via Heartbeat (No GPS)
    start = create_sample(100.0, True, None, None) 
    state, _ = MissionDetector.evaluate(state, start)
    assert state.start_sample == start # start.lat is None
    
    # WHEN: Update with Position > 10m from HOME (t=140)
    # The 'start_sample' still has None lat/lon, but we have Home.
    sample = create_sample(140.0, True, 0.0002, 0.0)
    final_state, event = MissionDetector.evaluate(state, sample)
    
    # THEN: Success (Using Home as Home)
    assert final_state.state_name == "IN_MISSION"
    assert event == "MISSION_STARTED"
