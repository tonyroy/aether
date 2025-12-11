# Vision: Aether - Drone Operations Tracking Platform (Pivot)

## 1. The Core Philosophy
Aether is pivoting from an **Active Orchestrator** (commanding drones) to a **Passive Operations Platform** (tracking & logging).
This acknowledges the regulatory and technical barriers to widespread autonomous command, focusing instead on solving the immediate problem for commercial operators: **Frictionless Flight Logging & Fleet Management**.

"Drone Logs as a Service" - enrollment is easy, logging is automatic.

---

## 2. Key Features

### 2.1 Frictionless Logging ("Mission Detection")
*   **No Manual Start/Stop**: The operator does not need to open an app to "start a mission".
*   **Automatic Detection**: The system detects a "Session" based purely on telemetry (e.g., Drone Arming, Takeoff, Movement).
*   **Intelligent Boundaries**: A "Session" is not just a single flight. It might involve multiple battery swaps or short landings (e.g., a crop spraying job). The system uses configurable rules to group these events into a single logical "Job" or "Mission".

### 2.2 Passive vs Active
*   **Old Model (Active)**: Cloud says "Go here" -> Drone obeys.
*   **New Model (Passive)**: Drone goes where operator says -> Cloud watches, records, and analyzes.
*   The `EntityWorkflow` acts as a **Digital Twin/Observer**, receiving state updates and updating the "Session" record.

### 2.3 Multi-Tenancy & Self-Service
*   **SaaS Model**: Operators create accounts, enroll drones (via QR code/Cert provision), and pay per drone/month.
*   **Data Isolation**: Tenant A cannot see Tenant B's fleet.
*   **Scalability**: Built on AWS IoT & Temporal to handle thousands of concurrent streams.

---

## 3. Technical Architecture (Proposed Modification)

### 3.1 Drone Entity Workflow as "The Observer"
The existing `DroneEntityWorkflow` remains long-running but changes role.
*   **Before**: Guarded the drone to prevent double-booking.
*   **Now**: Monitors the telemetry stream for **State Transitions**.
    *   `DISARMED` -> `ARMED`: Possible session start.
    *   `LANDED` -> `IN_AIR`: Confirmed activity.
    *   `ARMED` -> `DISARMED`: Possible session pause/end.

### 3.2 Session Recording Workflow
When a session is detected, the Entity Workflow spawns a `SessionRecordingWorkflow` (Child).
*   **Responsibilities**:
    *   Accumulate flight metrics (Max Altitude, Distance Flown, Battery Used).
    *   Buffer/Stream high-freq logs to a data store (S3/Timestream).
    *   Apply "End of Mission" logic (e.g., "If disarmed > 10 mins, close session").

### 3.3 Rule Engine
A configurable engine (likely within the Entity Workflow) defines:
*   **Start Trigger**: e.g., "Armed for > 5 seconds".
*   **End Trigger**: e.g., "Disarmed AND No heartbeat for 5 mins" OR "Manual 'End Job' signal".
*   **Phase Detection**: "Hovering", "Traveling", "Mapping".

---

## 4. Open Questions
1.  **Telemetry Ingress**: Do we pipe *all* telemetry to the Workflow (expensive) or rely on Edge/Cloud Rules to generate events (e.g., "Takeoff Detected")?
2.  **Data Ownership**: How do we efficiently isolate Tenant data in S3/DynamoDB?
3.  **Real-Time vs Post-Process**: Do users need to see the "Live Tracking" map, or is a post-flight report sufficient?
