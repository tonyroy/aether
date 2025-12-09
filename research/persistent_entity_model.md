# Research: Persistent Entity Workflows for Drones

## 1. Overview
The proposed pivot suggests modelling each drone as a long-running "Entity Workflow" in Temporal. Missions would be executed as **Child Workflows** (Sub-workflows) triggered by signals or calls to the parent Entity Workflow.

## 2. The Pattern: "Drone-as-a-Workflow"
In this architecture, every registered drone has a corresponding Workflow Execution (e.g., `workflow_id="drone-123"`) that stays open indefinitely (using **Continue-As-New** periodically).

### 2.1 Responsibilities of the Entity Workflow
- **State Guard**: Maintains the "Source of Truth" for the drone's business state (e.g., `IDLE`, `ON_MISSION`, `MAINTENANCE`, `OFFLINE`).
- **Locking Mechanism**: Ensures mutual exclusion. A drone cannot accept a new mission if it is already `ON_MISSION`.
- **Signal Handler**: Listens for external events:
  - `UpdateTelemetry`: Updates internal state (battery, lat/lon).
  - `AssignMission`: Triggers a child mission workflow.
  - `EmergencyStop`: Cancels current mission immediately.

## 3. Mission Dispatch & Matchmaking
The core requirement is to query drones based on criteria: *"Available, in range, serviceable, battery sufficient."*

### 3.1 Challenge: Querying Workflows
Temporal's standard `Query` API is designed for single-entity checking (`Query(drone-123, "getState")`). It is **not** designed for fleet-wide queries like "Select * from Drones where status='IDLE'".

### 3.2 Solution: Search Attributes (Visibility)
Temporal supports **Custom Search Attributes** powered by Elasticsearch.
- The Entity Workflow updates its attributes: `CustomStatus="IDLE"`, `BatteryLevel=85`, `ServiceArea="Canberra"`.
- **Dispatcher Workflow** uses `ListWorkflowExecutions` query:
  `CustomStatus = 'IDLE' AND BatteryLevel > 50 AND ServiceArea = 'Canberra'`
- **Limitation**: Geo-spatial queries (lat/lon radius) are not natively supported efficiently in standard Temporal Visibility.

### 3.3 Solution: Synchronized Database (Hybrid)
For complex spatial querying:
1. Entity Workflow receives telemetry updates.
2. It executes a short Activity to update a **PostGIS / DynamoDB** record (`Drone ID, Lat, Lon, Battery, Status`).
### 3.4 Telemetry Strategy: Reduce Noise
**Question:** Should we pipe all telemetry (1Hz or 10Hz) into the workflow?
**Answer:** **NO.**
- **Problem**: Piping high-frequency data as Signals bloats Temporal History rapidly (limits are ~50k events). It requires constant "Continue-As-New", increasing complexity and load.
- **Solution (Shadow-First)**:
    - **Data-at-Rest**: Store live telemetry in **AWS IoT Device Shadow**.
    - **On-Demand**: The Entity Workflow executes an **Activity** (`GetDroneState`) to fetch the Shadow only when it needs to make a decision (e.g., "Can I accept this mission?").
    - **Event-Driven**: Only Signal the workflow for **Significant Business Events** (e.g., "Armed", "Landed", "Critical Battery Alert").

### 3.5 Offline Detection ("The Heartbeat")
Reliable offline detection is critical for fleet management.
- **Mechanism**: Use **AWS IoT Lifecycle Events**.
- **Implementation**:
    1. Enable "Connect/Disconnect" events in AWS IoT Settings.
    2. Create an IoT Rule that listens to `$aws/events/presence/disconnected/+`.
    3. Trigger a Lambda/Activity that sends a **Signal** (`DroneOffline`) to the corresponding Entity Workflow.
    4. The Workflow transitions internal state to `OFFLINE` and rejects new missions.
    5. Conversely, listen for `$aws/events/presence/connected/+` to Signal `DroneOnline`.

### 3.6 Alternative: Querying Connectivity (Pre-Flight Check)
**Question:** Can we just query if it's online?
**Answer:** **YES.**
- **AWS IoT Fleet Indexing**: If enabled, AWS indexes connectivity status.
- **Activity**: `CheckConnectivity(drone_id)` -> Calls `client.search_index(queryString="thingName:drone-1 AND connectivity.connected:true")`.
- **Use Case**: Best used as a **Pre-Flight Check**. Before `MissionWorkflow` starts, the Entity Workflow calls this Activity to assert the drone is actually reachable.
- **Trade-off**: Querying is reactive. Pushing events (Signals) allows the workflow to *proactively* mark itself unavailable for search queries. **Hybrid is best**: Signal for general status, Query for critical confirmation.

## 4. Pros & Cons
| Feature | Benefit |
| :--- | :--- |
| **Consistency** | Strong consistency. Impossible to "double book" a drone if the Workflow manages the state lock. |
| **Audit Log** | Temporal History provides a perfect, immutable log of the drone's entire lifecycle. |
| **Resilience** | If the Orchestrator crashes, the drone's "State" and running missions resume exactly where they left off. |
| **Simplicity** | "Business Logic" is centralized in code, not scattered across DB updates and race conditions. |

### Cons
| Feature | Drawback |
| :--- | :--- |
| **Latency** | Routing every telemetry packet through a Workflow Signal + History Event can be high-overhead for high-frequency updates (e.g., 10Hz). |
| **Complexity** | Requires managing "Continue-As-New" loops to prevent history size limits (50k events). |
| **Search** | Geo-spatial search requires external indexing (Search Attributes or separate DB). |

## 5. Recommendation
**Pivot is strongly recommended.** The pros of strong consistency and orchestration capability outweigh the complexity.

**Proposed Architecture:**
1. **Drone Entity Workflow**: Long-running. Handles lifecycle.
2. **Telemetry**: Keep high-freq telemetry in AWS IoT/Shadow. Only signal the Workflow on **significant changes** (Mode change, Low Battery, Mission Start/End) or periodic heartbeats (every 1 min).
3. **Dispatch**: Use **Temporal Search Attributes** for status/battery filtering. Use a dedicated `FleetState` DB (updated by AWS IoT Rules) for complex spatial queries if needed.
4. **Missions**: Implemented as **Child Workflows**. This isolates mission logic (fails independently) but allows Parent to cancel/monitor.

## 6. Migration Plan
1. **Create `DroneEntityWorkflow`**: Accepts `drone_id`. Loops forever handling Signals.
2. **Refactor `MissionWorkflow`**: Make it a reusable building block.
## 6. Implementation Prerequisites
Before implementation, we must address two key lifecycle requirements:

### 6.1 Bootstrapping (The "Fleet Watcher")
- **Probe**: Entity Workflows do not start automatically.
- **Requirement**: A mechanism to ensure that for every Drone in the Registry, a corresponding `DroneEntityWorkflow` is running.
- **Solution**: A **Bootstrapper Script** (or Cron Workflow) that:
    1. Lists all Things in `AetherDroneGroup`.
    2. Calls `client.start_workflow(..., id="entity-<thingName>")` if not running.
    3. Runs on startup and periodically (reconciliation loop).

### 6.2 Status Synchronization (The "Busy" Flag)
- **Problem**: AWS Fleet Indexing knows if a drone is "Connected", but not if it is "Busy" (executing a mission).
- **Requirement**: Queries like "Find available drone" must exclude busy drones.
- **Solution**:
    - The **Entity Workflow** is the Source of Truth for "Mission Status".
    - **Action**: When accepting a mission, the Workflow MUST execute an Activity to update the **Device Shadow** (e.g., `reported.orchestrator.status = "ON_MISSION"`).
    - **Query**: The Dispatcher then queries `thingName:drone-* AND connectivity.connected:true AND shadow.reported.orchestrator.status:IDLE`.
