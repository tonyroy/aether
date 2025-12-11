# Architecture: Passive Drone Tracking & Mission Detection

## 1. Overview
This design pivots the Aether platform to a **Passive Listener**. It ingests telemetry events to detect, record, and visualize drone operations without issuing commands.

### 1.1 Core Value Proposition
*   **Compliance & Logs**: Automated flight logging for regulatory reporting.
*   **Real-Time Awareness**: "Air Traffic Control" dashboard for fleet managers.
*   **Zero Friction**: No pilot input required; flights are detected automatically.

---

## 2. System Architecture

```mermaid
graph TD
    Drone[Drone] -->|MQTT / Telemetry| IoT[AWS IoT Core]
    
    %% Real-Time Path (Hot)
    IoT -->|Rule: SELECT *| Kinesis[Kinesis / Firehose]
    Kinesis -->|Batch| Timestream[Amazon Timestream (Logs)]
    IoT -->|Rule: Pub/Sub| AppSync[AWS AppSync]
    AppSync -->|WS| Dashboard[Live Dashboard]

    %% Detection Path (Event)
    IoT -->|Rule: Filter Significant Events| RuleEng[IoT Rules Engine]
    RuleEng -->|Lambda / Direct| Temporal[Temporal Orchestrator]
    
    subgraph Temporal Cloud
        Entity[DroneEntityWorkflow]
        Session[SessionWorkflow (Child)]
    end
    
    Temporal -->|Signal: State Change| Entity
    Entity -->|Start/Signal| Session
```

---

## 3. The State Machine (Drone Entity)
The `DroneEntityWorkflow` tracks the high-level lifecycle.

### 3.1 States
1.  **OFFLINE**: No connectivity (IoT Lifecycle Event: Disconnected).
2.  **ONLINE_IDLE**: Connected, Disarmed.
3.  **ONLINE_ARMED** (Candidate): Connected, Armed, but not yet a "Mission". (e.g., Pre-flight checks on ground).
4.  **IN_MISSION**: **Confirmed** flight activity based on Configurable Rules (e.g., flying > 30s).
5.  **ERROR**: Device reporting hardware failure or telemetry anomaly.

### 3.2 Detection Logic (Configurable Rule Engine)
Instead of hardcoding transitions, the Workflow evaluates a `DetectionProfile`:
*   **Trigger**: `State: ARMED`
*   **Confirmation Condition**: `Duration(ARMED) > 30s` AND `DistanceTraveled > 10m`
*   **False Start**: If `DISARMED` occurs before Confirmation, revert to `ONLINE_IDLE` (log as "Ground Test").

---

## 4. "Project Profile" Configuration
A JSON configuration defines how sessions are detected.
```json
{
  "profile_id": "default_commercial",
  "rules": {
    "mission_start": {
      "min_flight_duration_sec": 30,
      "min_distance_meters": 15,
      "require_gps_lock": true
    },
    "mission_end": {
      "timeout_after_disarm_sec": 600,
      "auto_close_on_error": false
    }
  }
}
```

## 5. Implementation Strategy

### 5.1 Telemetry Ingress & Mapping
*   **MVP Mapping**: Use **Device Shadow** (`reported.location`).
    *   Drone updates Shadow at low freq (e.g., every 5s or on significant change).
    *   UI polls/subscribes to Shadow.
*   **High-Freq Ingress**:
    *   AWS IoT Rule buffers high-freq telemetry to Kinesis/Timestream (for post-flight replay).
    *   "Significant Events" (Arm/Disarm, 10s Interval) routed to Temporal for Rule Evaluation.

### 5.3 Data Storage (Multi-Tenancy)
*   **Hot Data**: Temporal (State).
*   **Warm Data**: Simple S3 Bucket `s3://aether-logs/{tenant_id}/{drone_id}/{session_id}.json`.
*   **Cold Data**: Parquet/Iceberg for analytics.

### 5.4 Advanced Data Capture (Future Iteration)
*   **Flight Plan Events**:
    *   Detect MAVLink `MISSION_ITEM` uploads (from GCS like QGroundControl).
    *   Log these as "Mission Plan Updated" events in the session timeline.
*   **Log Retrieval (.bin)**:
    *   **Trigger**: Session End (and/or User Profile policy e.g. "Always" vs "On Failure").
    *   **Mechanism**: Request drone to upload ArduPilot `.bin` DataFlash logs to S3.
    *   **Requirement**: Update Cloud Connector to handle file upload requests.

---

## 6. Next Steps (Implementation)
1.  **Refactor `DroneEntityWorkflow`**: Remove "dispatch" logic. Add State Machine for Arm/Disarm signals.
2.  **Mock Telemetry Stream**: Create a script `tools/simulate_flight.py` to publish MQTT patterns (Arm, Takeoff, Fly, Land, Disarm).
3.  **Test Detection**: Verify Workflow transitions from IDLE -> IN_MISSION without manual generic.
