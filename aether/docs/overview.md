# **Cloud-Native Orchestration of Autonomous Aerial Systems: A Comprehensive Architecture for Generic MAVLink Ecosystems on AWS using Temporal and the Model Context Protocol**

## **1\. Introduction: The Convergence of Cloud Computing and Autonomous Robotics**

The integration of autonomous robotic systems into the cloud computing paradigm represents a fundamental shift in how physical agents are managed, orchestrated, and utilized. Historically, the operation of Unmanned Aerial Vehicles (UAVs) has been characterized by localized control loops, relying heavily on direct radio links to Ground Control Stations (GCS) or onboard companion computers with limited processing power. While sufficient for line-of-sight operations, this model fails to scale for fleet-level management or complex, asynchronous missions requiring advanced reasoning. The emergence of durable execution platforms like Temporal.io, combined with standardized agent interfaces such as the Model Context Protocol (MCP), provides the necessary primitives to elevate drone operations from simple remote control to intelligent, cloud-orchestrated autonomy.

This report presents an exhaustive architectural analysis and implementation strategy for a generic MAVLink ecosystem hosted on Amazon Web Services (AWS). MAVLink, the Micro Air Vehicle Link protocol, serves as the de facto standard for drone telemetry and command and control (C2). By abstracting MAVLink interactions into cloud-native constructs, we transform physical and simulated drones into "Agent Tools"—resources that can be discovered, interrogated, and commanded by Large Language Models (LLMs) residing in Amazon Bedrock.

The proposed architecture moves beyond traditional state machines, utilizing the **Entity Workflow** pattern within Temporal to create persistent "Digital Twins" of robotic assets. This approach addresses the inherent challenges of distributed robotics: intermittent connectivity, high latency, and the asynchronous nature of physical actuation. By prioritizing AWS services such as IoT Core for ingress, Fargate for ephemeral simulation, and Kinesis Video Streams for visual intelligence, the system achieves a serverless, event-driven topology that is both scalable and resilient. Furthermore, the adoption of MCP allows for a standardized, schema-driven interface between the generative AI layer and the deterministic control layer, enabling a generic ecosystem where new vehicle capabilities can be exposed to AI agents without bespoke integration code.

### **1.1 The Imperative for Durable Orchestration in Robotics**

In the domain of autonomous systems, the cost of failure is high. Unlike pure software applications where a crashed service can simply be restarted, a failure in a drone control process can result in physical loss of the vehicle or safety hazards. Traditional orchestration methods often rely on ephemeral scripts or in-memory state machines that are vulnerable to infrastructure failures. If the control process crashes while a drone is executing a long-duration waypoint mission, the context of that mission—what has been completed, what is pending, and the logic for handling anomalies—is lost.

Temporal.io introduces the concept of **Durable Execution**, which is critical for this architecture. By persisting the full event history of a workflow, Temporal ensures that the control logic is resilient to process failures, worker restarts, or network partitions. This is superior to graph-based orchestration libraries like LangGraph for physical systems because Temporal provides guarantees around state preservation and activity retries that are enforced by a central server cluster rather than client-side logic. In this ecosystem, a Temporal workflow does not merely execute a task; it *is* the digital representation of the drone, maintaining its state and lifecycle indefinitely.

### **1.2 The Role of Generative AI and MCP**

The integration of Large Language Models (LLMs) via Amazon Bedrock introduces a reasoning layer capable of interpreting high-level intent (e.g., "Inspect the perimeter for breaches") and decomposing it into actionable machine commands. However, a significant gap exists between the probabilistic nature of LLMs and the deterministic requirements of flight control. The Model Context Protocol (MCP) bridges this gap.

MCP allows the drone ecosystem to expose its capabilities—telemetry retrieval, mission uploads, video analysis—as standardized "Tools" and "Resources." An MCP Server acts as a gateway, translating natural language-driven tool calls from the LLM into precise Temporal workflow signals. This decoupling is essential for a *generic* ecosystem; it allows the AI agent to discover the capabilities of different vehicle types (quadcopters, fixed-wing, rovers) dynamically, without requiring the underlying orchestration logic to be rewritten for each airframe.

## ---

**2\. Architectural Fundamentals: The MAVLink Protocol in the Cloud**

To build a generic ecosystem, one must first understand the intricacies of the underlying communication protocol. MAVLink is a lightweight, binary, header-only message marshaling library designed for resource-constrained systems.1 Its efficiency is paramount for radio links, but adapting it for cloud ingress requires specific architectural patterns to handle serialization, routing, and dialect management.

### **2.1 MAVLink Message Structure and Cloud Encapsulation**

MAVLink messages are defined in XML files, which are then compiled into language-specific bindings (e.g., Python pymavlink or C++ headers). A standard MAVLink 2.0 packet consists of a header containing the System ID, Component ID, Sequence Number, and Message ID, followed by the payload and a checksum.1

In a cloud-native environment, transmitting raw binary UDP packets over the public internet is unreliable and difficult to secure. Therefore, the architecture employs an encapsulation strategy at the edge. The companion computer or mavlink-router instance wraps the binary MAVLink packet into a secure transport protocol—specifically MQTT (Message Queuing Telemetry Transport) via AWS IoT Core.

**Table 1: MAVLink to Cloud Protocol Mapping**

| MAVLink Component | Cloud Representation | Purpose |
| :---- | :---- | :---- |
| **System ID** (1-255) | **AWS IoT Thing Name** (e.g., drone-001) | Uniquely identifies the physical asset in the cloud registry. |
| **Message ID** (e.g., 33 GLOBAL\_POSITION\_INT) | **MQTT Topic Suffix** or **JSON Key** | Identifies the type of telemetry data for routing rules. |
| **Payload** (Binary) | **JSON Object** or **Base64 String** | The data content. JSON allows for cloud-side querying; Base64 preserves binary integrity. |
| **Heartbeat** | **MQTT Keep-Alive** / **LWT** | Maintains connection state; Last Will and Testament (LWT) handles ungraceful disconnects. |

The encapsulation process involves deserializing the MAVLink packet at the edge using pymavlink, converting the fields to a JSON object (e.g., {"lat": 37.7749, "lon": \-122.4194, "alt": 100}), and publishing this to a specific MQTT topic. This approach allows AWS services like IoT Core Rules Engine to inspect the payload and route data based on content (e.g., "Route all messages with battery\_voltage \< 10 to the alert queue").

### **2.2 Dialect Management and Schema Generation**

A "generic" ecosystem must support multiple MAVLink "dialects"—sets of message definitions tailored for specific autopilots (e.g., ardupilotmega.xml, common.xml). Hardcoding support for every message type in the cloud application is unmaintainable.

Instead, the system leverages dynamic schema generation. Using the pymavlink library, the MCP server can parse the XML definitions at runtime (or build time) to generate JSON Schemas for the supported commands. For instance, the MAV\_CMD\_NAV\_TAKEOFF command in common.xml defines seven parameters (Pitch, Empty, Empty, Yaw, Lat, Lon, Alt). The system automatically converts this definition into an MCP Tool schema, enabling the LLM to understand exactly what arguments are required to execute a takeoff, without human developers manually writing the interface code.2

### **2.3 Edge Routing with MAVLink Router**

To ensure robust connectivity, the **MAVLink Router** 4 is deployed on the drone's companion computer (e.g., Raspberry Pi) or within the simulation container. The router is critical for splitting the telemetry stream. It allows a single MAVLink source (the Flight Controller) to communicate simultaneously with:

1. **The Cloud Bridge:** A local service that forwards data to AWS IoT Core.  
2. **Local Safety Link:** A direct UDP link for a human safety pilot using a GCS like QGroundControl.  
3. **Video Encoder:** A process that overlays telemetry on the video stream.

This "split" architecture ensures that the autonomous cloud agent does not monopolize the connection, preserving a manual override path which is a critical safety requirement for autonomous operations.4

## ---

**3\. AWS Infrastructure: Ingress and Connectivity Layer**

The AWS infrastructure serves as the central nervous system, handling the secure ingestion of data from potentially thousands of distributed agents. This layer is built primarily on **AWS IoT Core**, which provides the scalability and security features necessary for device management.

### **3.1 AWS IoT Core Configuration**

AWS IoT Core acts as the message broker. Each drone is provisioned as a "Thing" in the IoT registry. Security is enforced via X.509 client certificates, which are used to authenticate the mTLS connection. This ensures that only authorized devices can publish telemetry or subscribe to commands.6

#### **3.1.1 Topic Hierarchy and Rules Engine**

A structured topic hierarchy is essential for organizing traffic. The following design is implemented:

* **Ingress (Telemetry):** mav/{{thingName}}/telemetry  
  * *Payload:* JSON-formatted telemetry (Position, Attitude, Battery).  
  * *Rule:* An AWS IoT Rule selects this data and forwards it to an Amazon SQS queue (TelemetryQueue). SQS is chosen over direct Lambda invocation to provide a buffer against telemetry bursts and to allow the Temporal workers to process batches of messages efficiently.8  
* **Egress (Commands):** mav/{{thingName}}/cmd  
  * *Payload:* JSON-wrapped MAVLink commands (e.g., {"command": "TAKEOFF", "params": \[...\]}).  
  * *Mechanism:* The drone subscribes to this topic. The edge bridge receives the JSON, converts it back to binary MAVLink using pymavlink, and sends it to the flight controller.  
* **State (Shadow):** $aws/things/{{thingName}}/shadow/update  
  * *Purpose:* The Device Shadow service maintains the "reported" state (e.g., current flight mode) and the "desired" state (e.g., target flight mode). This provides a persistence layer for the latest known state, accessible even if the drone disconnects.7

### **3.2 Private Networking and Sidecar Patterns**

For simulated drones running in the cloud (AWS Fargate), exposing MAVLink ports to the public internet is a security risk. Instead, the architecture utilizes a **Sidecar Pattern** with **Tailscale** to create a private, encrypted mesh network.9

In this configuration, the Fargate Task Definition contains two containers:

1. **Simulation Container:** Runs ArduPilot SITL. It exposes MAVLink on localhost UDP ports.  
2. **Tailscale Sidecar:** Runs the Tailscale daemon. It connects to the private Tailnet and proxies traffic to the simulation container's ports.

This approach allows the Temporal workers and MCP servers (also on the Tailnet) to address the simulated drones by their Tailscale IP addresses or DNS names (e.g., sim-drone-05), treating them exactly as if they were physical devices on a local LAN, without managing complex VPC Peering or Transit Gateways for ephemeral tasks.11

### **3.3 Dynamic Provisioning via Lambda**

To support the "Generic" requirement of being able to spawn drones on demand, the system utilizes AWS Lambda. An **MCP Tool** (spawn\_drone) triggers a Temporal Activity, which in turn invokes a Lambda function. This Lambda uses the boto3 library to call the Amazon ECS RunTask API.13

**Key Implementation Detail:** The Lambda function injects environment variables into the Fargate task at runtime. These variables determine the drone's initial configuration:

* LATITUDE / LONGITUDE: Starting coordinates.  
* SYSID: MAVLink System ID.  
* TAILSCALE\_AUTH\_KEY: Ephemeral key retrieved from AWS Secrets Manager for joining the network.

This allows the AI agent to dynamically expand its fleet based on mission requirements (e.g., "I need three more drones to cover this search area").14

## ---

**4\. Orchestration Layer: Temporal.io and the Entity Workflow Pattern**

The orchestration layer is the brain of the ecosystem. While the AI agent provides high-level intent, **Temporal.io** ensures that these intents are executed reliably. The choice of Temporal over LangGraph is driven by the need for durable state management and long-running processes that survive infrastructure failures.16

### **4.1 The Entity Workflow Pattern**

Standard workflow engines typically model a business process (e.g., "Process Order"). In contrast, robotics requires modeling the *device itself*. We implement the **Entity Workflow** pattern, where a single Temporal workflow execution corresponds 1:1 with a specific drone.18

* **Workflow ID:** drone-entity-{{UUID}}  
* **Duration:** The workflow runs continuously as long as the drone is active (potentially days or weeks).  
* **Responsibility:** It acts as the "Digital Twin," holding the canonical state of the drone and serializing all access to it. This prevents race conditions where two agents might try to command the drone simultaneously.

### **4.2 Signal Channels for Asynchronous Communication**

Robotics interactions are inherently asynchronous. A command is sent, and an acknowledgment might arrive seconds later. Telemetry arrives continuously. Temporal **Signals** are the mechanism used to handle these inputs without blocking the workflow.19

The Drone Entity Workflow defines signal methods:

* signal\_telemetry(telemetry\_batch): Updates the internal state variables (Position, Battery, Mode).  
* signal\_command(command\_intent): Receives instructions from the MCP agent.  
* signal\_intervention(override): A high-priority signal for safety overrides.

The workflow's main loop uses workflow.wait\_condition to react to these signals. For example, when a signal\_command is received, the workflow wakes up, validates the command against the current state (e.g., "Cannot takeoff if battery \< 20%"), and then executes the appropriate Activity.

### **4.3 Implementing the Generic MAVLink Activity**

To support the generic nature of the ecosystem, we avoid creating separate activities for every possible MAVLink command. Instead, we implement a **Generic Command Activity**.

**Activity Logic:**

1. **Input:** Accepts a generic payload: {"command\_id": int, "params": \[float,...\]}.  
2. **Protocol:** Uses boto3 to publish this payload to the AWS IoT Core command topic (mav/{{id}}/cmd).  
3. **Verification:** The activity subscribes to the telemetry stream (or a specific ACK topic) to verify that the drone received and accepted the command. It uses a Temporal Retry Policy to handle transient network failures (e.g., packet loss).21

**Table 2: Comparison of Orchestration Approaches**

| Feature | Temporal.io (Selected) | LangGraph | Relevance to Robotics |
| :---- | :---- | :---- | :---- |
| **State Persistence** | Event History (Database backed) | Client-side / Graph State | Temporal ensures mission state survives worker crashes. |
| **Execution Model** | Deterministic Workflow | Graph Traversal | Temporal's determinism is crucial for debugging physical behaviors. |
| **Long-Running** | Native support (Months/Years) | Session-based | Drones require persistent twins that outlive a single chat session. |
| **Language Support** | Python, Go, Java, TS | Python, JS | Temporal's multi-language support allows efficient worker implementation. |

### **4.4 Handling Telemetry: Polling vs. Streaming**

A key design decision is how the AI agent consumes telemetry.

* **Streaming:** Pushing every telemetry packet to the LLM is wasteful and would overflow the context window.22  
* **Polling (Cached):** The Entity Workflow maintains a cached state object (current\_position, last\_update\_time). The MCP Agent *polls* this state only when necessary (e.g., when deciding the next move).

The architecture uses the **Cached Polling** approach. The Temporal workflow acts as a buffer. It ingests the high-frequency stream (via Signals) but exposes a queryable state. The MCP tool get\_drone\_state simply performs a Temporal Query on the workflow, returning the latest snapshot instantaneously without querying the physical device.23

### **4.5 Managing History Size with Continue-As-New**

Long-running workflows accumulate large event histories, which can degrade performance. To mitigate this, the Drone Entity Workflow implements the **Continue-As-New** pattern.24 Periodically (e.g., every 10,000 events or every hour), the workflow calls continue\_as\_new, passing the current state (position, mission status) to a fresh workflow execution. This resets the history while preserving the Digital Twin's continuity, ensuring the system can run indefinitely.

## ---

**5\. Ephemeral Simulation Environments: Fargate and ArduPilot SITL**

To enable the AI agent to "explore" safely, the system provides a simulation capability. This allows the agent to test a mission plan in a virtual environment before executing it on physical hardware.

### **5.1 ArduPilot SITL Architecture**

Software-In-The-Loop (SITL) compiles the ArduPilot autopilot code into a native executable that runs on a standard x86 or ARM Linux environment.25 It decouples the flight logic from the hardware sensors, allowing physics backends to simulate sensor inputs.

The simulation container utilizes sim\_vehicle.py 27 to orchestrate the instances. This script launches:

1. The **ArduCopter** binary (the firmware).  
2. The **Physics Model** (simulating gravity, inertia, wind).  
3. **MAVProxy**: A ground station console that acts as a router, forwarding MAVLink packets from the binary to the exposed UDP ports.27

### **5.2 Dynamic Parameter Simulation**

A generic ecosystem must support environmental variance. The MCP Agent can configure the simulation parameters via MAVLink parameter protocols (PARAM\_SET).

* SIM\_WIND\_SPD: Sets the simulated wind speed.  
* SIM\_GPS\_DISABLE: Simulates GPS failure.

By exposing these as MCP tools (set\_simulation\_environment), the AI agent can run scenarios like "Test landing behavior in 15 m/s wind".28

### **5.3 Containerization and Fargate Launch Types**

The Docker image for the simulation is optimized for headless execution. It includes the boto3 library to fetch secrets and configuration at startup.

* **Base Image:** Ubuntu 22.04 or Alpine Linux.  
* **Dependencies:** Python 3, pymavlink, mavproxy, ArduPilot binaries.

When the deploy\_drone Temporal Activity is called, it constructs a RunTask request to AWS ECS Fargate.13

* **Launch Type:** FARGATE (Serverless).  
* **Network Configuration:** awsvpc mode, placing the task in a private subnet.  
* **Tags:** Tags the task with the WorkflowID to allow for easy termination and cost tracking.

Using Fargate eliminates the need to manage a cluster of EC2 instances. The system pays only for the CPU and memory consumed while the simulation is active, scaling to zero when no missions are running.30

## ---

**6\. The Model Context Protocol (MCP): Bridging Agents and Robotics**

The Model Context Protocol acts as the standardized API layer for the ecosystem. It defines a schema for how the "Agent Tools" (drones) describe themselves to the "Agent Host" (Bedrock LLM).32

### **6.1 MCP Server Implementation**

The MCP Server is a Python application running in a container (typically on ECS or Lambda). It implements the MCP specification, exposing a set of **Tools**, **Resources**, and **Prompts**.

#### **6.1.1 Tool Definition and Schema Mapping**

The core of the generic ecosystem is the automated mapping of MAVLink commands to MCP Tool schemas. The system uses the pymavlink library to introspect the MAVLink XML definitions.

**Example Schema Transformation:**

* **Source (MAVLink XML):**  
  XML  
  \<command name\="MAV\_CMD\_NAV\_WAYPOINT"\>  
     \<param index\="1"\>Hold time\</param\>  
     \<param index\="5"\>Latitude\</param\>  
     \<param index\="6"\>Longitude\</param\>  
     \<param index\="7"\>Altitude\</param\>  
  \</command\>

* **Generated MCP Tool Schema:**  
  JSON  
  {  
    "name": "mav\_cmd\_nav\_waypoint",  
    "description": "Navigate to waypoint. Hold time in seconds.",  
    "inputSchema": {  
      "type": "object",  
      "properties": {  
        "hold\_time": {"type": "number", "description": "Hold time in seconds"},  
        "latitude": {"type": "number"},  
        "longitude": {"type": "number"},  
        "altitude": {"type": "number"}  
      },  
      "required": \["latitude", "longitude", "altitude"\]  
    }  
  }

This automated generation ensures that as MAVLink evolves or new custom dialects are added, the AI Agent immediately gains access to these capabilities without code changes.34

### **6.2 Bedrock Agent Integration**

Amazon Bedrock Agents consume these MCP tools. The integration follows the **MCP Client** pattern.35

1. **Discovery:** The Bedrock Agent connects to the MCP Server and requests list\_tools.  
2. **Context Loading:** The tools (e.g., list\_drones, spawn\_drone, send\_command) are loaded into the LLM's context window.  
3. **Reasoning:** The LLM uses its training to determine which tool to call. For example, if the user says "Survey the field," the LLM might call spawn\_drone followed by a sequence of mav\_cmd\_nav\_waypoint calls.

### **6.3 Tool Implementation Logic**

The MCP Tools do not execute logic directly; they act as the interface to the Temporal Orchestrator.

* **Tool:** execute\_mission\_command  
* **Implementation:**  
  1. Connects to the Temporal Client.  
  2. Identifies the workflow handle drone-entity-{id}.  
  3. Sends a CommandSignal to the workflow with the parameters provided by the LLM.  
  4. Returns "Command Sent" to the LLM (asynchronous) or waits for the CommandCompleted signal (synchronous).

This architecture separates the *intent* (generated by the AI) from the *execution* (managed by Temporal).36

## ---

**7\. Visual Intelligence: Kinesis Video Streams and Multimodal Analysis**

A purely telemetry-based drone is limited. To "explore and gather information," the agent must see. The architecture integrates **Amazon Kinesis Video Streams (KVS)** and **Amazon Bedrock's Multimodal capabilities** (Claude 3.5 Sonnet) to provide visual reasoning.

### **7.1 Video Ingestion Pipeline**

The drone (or simulation) runs a GStreamer pipeline that acts as a KVS Producer.38

**GStreamer Pipeline Components:**

1. **Source:** v4l2src (Camera) or ximagesrc (Simulation window).  
2. **Encoder:** x264enc (H.264 compression).  
3. **Sink:** kvssink. This proprietary AWS element handles the authentication and streaming to Kinesis.

The stream is persisted in KVS, indexed by fragment timestamps. This allows for both live viewing and historical playback.

### **7.2 On-Demand Visual Analysis**

Processing video frames continuously with an LLM is cost-prohibitive and introduces high latency. The system employs an **On-Demand Analysis** pattern.

1. **Trigger:** The AI Agent (via MCP) decides it needs visual confirmation (e.g., "Check if the landing zone is clear").  
2. **Tool Call:** The Agent calls the MCP Tool analyze\_current\_view.  
3. **Frame Extraction:**  
   * The MCP Server uses the boto3 Kinesis Video Media client.  
   * It calls GetMedia with StartSelectorType='NOW'.39  
   * It retrieves the latest MKV fragment and uses OpenCV to decode the raw bytes into an image (JPEG).  
4. **Analysis:**  
   * The image is encoded to Base64.  
   * The MCP Server calls bedrock-runtime.invoke\_model.  
   * **Payload:** It sends the image \+ a specific prompt (e.g., "Describe the terrain. Is it safe to land?") to Claude 3.5 Sonnet.41  
5. **Result:** The text description ("Terrain is rocky, high probability of obstruction") is returned to the Agent.

This "Look-Think-Act" loop allows the drone to perform complex semantic tasks (e.g., "Find the red car") that are impossible with standard MAVLink telemetry.

## ---

**8\. Security, Governance, and Network Isolation**

Security is paramount when connecting physical actuators to the cloud. The architecture employs a defense-in-depth strategy.

### **8.1 Mutual TLS (mTLS) and IoT Policies**

All connections to AWS IoT Core are authenticated using X.509 certificates.

* **Provisioning:** Each drone is issued a unique certificate during manufacturing (or container startup).  
* **Policies:** AWS IoT Policies enforce least privilege. A drone is allowed to publish *only* to mav/{client\_id}/telemetry and subscribe *only* to mav/{client\_id}/cmd. It cannot access other topics or other drones' data.7

### **8.2 IAM Roles for Service Accounts**

The compute components (Temporal Workers, MCP Servers) running on AWS (EC2 or Fargate) utilize **IAM Roles**.

* **Temporal Worker Role:** Granted iot:Publish (to send commands), kinesis:GetMedia (to fetch video), and ecs:RunTask (to spawn simulations).  
* **Key Management:** No long-term access keys are stored in the code. Credentials are retrieved dynamically from the instance metadata service.9

### **8.3 Tailscale and Network Isolation**

The generic ecosystem relies on **Tailscale** for secure peer-to-peer networking between the cloud control plane and the simulated/real drones.10

* **ACLs (Access Control Lists):** Tailscale ACLs are configured to isolate the fleet. Drones can communicate with the Temporal Workers, but not with each other. This prevents a compromised drone from attacking the fleet.  
* **Ephemeral Auth Keys:** The provisioning Lambda generates single-use, pre-authorized keys for the simulation containers. These keys expire automatically when the simulation ends, ensuring good hygiene for the overlay network.

## ---

**9\. Operational Scenarios and Use Cases**

To demonstrate the efficacy of this architecture, we examine two operational scenarios.

### **9.1 Scenario A: Autonomous Infrastructure Inspection**

**Mission:** "Inspect the bridge at coordinates X,Y for structural cracks."

1. **Agent Planning:** The Bedrock Agent receives the request. It queries list\_active\_drones. Finding none, it calls spawn\_drone (Fargate) to deploy a simulated drone for mission validation.  
2. **Mission Upload:** The Agent generates a flight plan (Waypoints) circling the bridge coordinates and uses the MCP Tool upload\_mission to send it to the drone via Temporal.  
3. **Execution:** The Agent calls start\_mission. The Temporal Entity Workflow sends MAV\_CMD\_MISSION\_START.  
4. **Visual Inspection:** At specific waypoints, the Agent uses analyze\_current\_view with the prompt "Identify any visible cracks in the concrete surface."  
5. **Outcome:** The MCP Server pulls the frame from Kinesis, Claude 3.5 analyzes it, and returns "Hairline crack detected on Pylon 4." The Agent logs this finding and commands the drone to Return to Launch (RTL).

### **9.2 Scenario B: Dynamic Search and Rescue**

**Mission:** "Search Sector 7 for a missing hiker with a blue jacket."

1. **Fleet Coordination:** The Agent spawns three drones (spawn\_drone x3).  
2. **Pattern Generation:** The Agent calculates a parallel sweep search pattern and assigns unique waypoints to each drone.  
3. **Asynchronous Orchestration:** The Temporal workflows manage the three drones in parallel.  
4. **Event-Driven Discovery:** Drone 2 reaches a waypoint. The Agent triggers a visual check: "Is there a person in a blue jacket?".  
5. **Positive Identification:** Bedrock confirms the sighting.  
6. **Swarm Reaction:** The Agent commands Drone 2 to LOITER (hover) over the target. It commands Drones 1 and 3 to RTL. It sends the coordinates to the human operator via a notification tool.

## ---

**10\. Conclusion and Future Outlook**

The architecture detailed in this report represents a mature, cloud-native approach to the "Internet of Robotic Things." By leveraging AWS IoT Core for secure ingress, AWS Fargate for scalable simulation, and Amazon Kinesis for visual data, the infrastructure solves the fundamental challenges of connectivity and scale.

The integration of **Temporal.io** provides the durable execution guarantees required to entrust physical assets to software control. It transforms the ephemeral nature of cloud functions into persistent, stateful "Digital Twins" that mirror the lifecycle of the robots they manage.

Finally, the **Model Context Protocol** serves as the linchpin, translating the generic, binary world of MAVLink into a semantic, tool-based interface for Generative AI. This allows for a generic ecosystem where the AI's reasoning capabilities can evolve independently of the robotic hardware, enabling a future where autonomous agents can explore, reason, and act upon the physical world with unprecedented flexibility and intelligence.

### **10.1 Key Recommendations**

1. **Adopt the Entity Workflow Pattern:** Treat workflows as long-running object instances, not just process scripts.  
2. **Automate Schema Generation:** Use pymavlink to generate MCP schemas from MAVLink XML to ensure the ecosystem remains generic and extensible.  
3. **Use Sidecars for Networking:** Tailscale or similar mesh overlays significantly reduce the complexity of securing ephemeral simulation environments compared to traditional VPNs.  
4. **Prioritize On-Demand Vision:** Design the AI interaction to pull video frames only when necessary to optimize for cost and latency.

This comprehensive architecture enables a seamless transition from manual drone piloting to fully orchestrated, AI-driven fleet operations on the AWS cloud.

#### **Works cited**

1. Protocol Overview \- MAVLink Guide, accessed December 4, 2025, [https://mavlink.io/en/about/overview.html](https://mavlink.io/en/about/overview.html)  
2. Using Pymavlink Libraries (mavgen) \- MAVLink Guide, accessed December 4, 2025, [https://mavlink.io/en/mavgen\_python/](https://mavlink.io/en/mavgen_python/)  
3. Lantero/pytoschema: A package to convert Python type annotations into JSON schemas \- GitHub, accessed December 4, 2025, [https://github.com/Lantero/pytoschema](https://github.com/Lantero/pytoschema)  
4. mavlink-router/mavlink-router: Route mavlink packets between endpoints \- GitHub, accessed December 4, 2025, [https://github.com/mavlink-router/mavlink-router](https://github.com/mavlink-router/mavlink-router)  
5. Routing \- MAVLink Guide, accessed December 4, 2025, [https://mavlink.io/en/guide/routing.html](https://mavlink.io/en/guide/routing.html)  
6. AWS IoT tutorials, accessed December 4, 2025, [https://docs.aws.amazon.com/iot/latest/developerguide/iot-tutorials.html](https://docs.aws.amazon.com/iot/latest/developerguide/iot-tutorials.html)  
7. Getting started with AWS IoT Core tutorials, accessed December 4, 2025, [https://docs.aws.amazon.com/iot/latest/developerguide/iot-gs.html](https://docs.aws.amazon.com/iot/latest/developerguide/iot-gs.html)  
8. aws-samples/aws-lambda-ecs-run-task \- GitHub, accessed December 4, 2025, [https://github.com/aws-samples/aws-lambda-ecs-run-task](https://github.com/aws-samples/aws-lambda-ecs-run-task)  
9. Fargate security considerations for Amazon ECS \- Amazon Elastic Container Service, accessed December 4, 2025, [https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-security-considerations.html](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-security-considerations.html)  
10. Run a Tailscale VPN relay on ECS/Fargate \- Platformers, accessed December 4, 2025, [https://platformers.dev/log/2022/tailscale-ecs/](https://platformers.dev/log/2022/tailscale-ecs/)  
11. Running Tailscale as a Sidecar Container \+ Tailscale on the Host system causes network issues if Tailscale takes too long to connect \#7540 \- GitHub, accessed December 4, 2025, [https://github.com/tailscale/tailscale/issues/7540](https://github.com/tailscale/tailscale/issues/7540)  
12. hardfinhq/tailscale-subnet-router/aws \- Terraform Registry, accessed December 4, 2025, [https://registry.terraform.io/modules/hardfinhq/tailscale-subnet-router/aws/latest](https://registry.terraform.io/modules/hardfinhq/tailscale-subnet-router/aws/latest)  
13. run\_task \- Boto3 1.42.0 documentation, accessed December 4, 2025, [https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs/client/run\_task.html](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs/client/run_task.html)  
14. Starting a container with dynamic arguments from Lambda \- Stack Overflow, accessed December 4, 2025, [https://stackoverflow.com/questions/61494853/starting-a-container-with-dynamic-arguments-from-lambda](https://stackoverflow.com/questions/61494853/starting-a-container-with-dynamic-arguments-from-lambda)  
15. Using Fargate for Long-Running Tasks | by Dylan Sena \- Medium, accessed December 4, 2025, [https://dcsena.medium.com/using-fargate-for-long-running-tasks-81236f7f47d5](https://dcsena.medium.com/using-fargate-for-long-running-tasks-81236f7f47d5)  
16. Temporal \+ AI Agents: The Missing Piece for Production-Ready Agentic Systems \- DEV Community, accessed December 4, 2025, [https://dev.to/akki907/temporal-workflow-orchestration-building-reliable-agentic-ai-systems-3bpm](https://dev.to/akki907/temporal-workflow-orchestration-building-reliable-agentic-ai-systems-3bpm)  
17. Temporal: Beyond State Machines for Reliable Distributed Applications, accessed December 4, 2025, [https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications)  
18. Managing very long-running Workflows with Temporal, accessed December 4, 2025, [https://temporal.io/blog/very-long-running-workflows](https://temporal.io/blog/very-long-running-workflows)  
19. IoT devices management \- Community Support \- Temporal, accessed December 4, 2025, [https://community.temporal.io/t/iot-devices-management/1141](https://community.temporal.io/t/iot-devices-management/1141)  
20. Orchestrating ambient agents with Temporal, accessed December 4, 2025, [https://temporal.io/blog/orchestrating-ambient-agents-with-temporal](https://temporal.io/blog/orchestrating-ambient-agents-with-temporal)  
21. How many Activities should I use in my Temporal Workflow?, accessed December 4, 2025, [https://temporal.io/blog/how-many-activities-should-i-use-in-my-temporal-workflow](https://temporal.io/blog/how-many-activities-should-i-use-in-my-temporal-workflow)  
22. Polling and Streaming \- DEV Community, accessed December 4, 2025, [https://dev.to/pragyasapkota/polling-and-streaming-15h5](https://dev.to/pragyasapkota/polling-and-streaming-15h5)  
23. Best Practices for Managing a stateful In‑Memory Cache in Temporal Python Workflows, accessed December 4, 2025, [https://community.temporal.io/t/best-practices-for-managing-a-stateful-in-memory-cache-in-temporal-python-workflows/17374](https://community.temporal.io/t/best-practices-for-managing-a-stateful-in-memory-cache-in-temporal-python-workflows/17374)  
24. Entity Workflow Pattern / Continue As New and Signal order \- Temporal Community, accessed December 4, 2025, [https://community.temporal.io/t/entity-workflow-pattern-continue-as-new-and-signal-order/18325](https://community.temporal.io/t/entity-workflow-pattern-continue-as-new-and-signal-order/18325)  
25. SITL Simulator (Software in the Loop) — Dev documentation \- ArduPilot, accessed December 4, 2025, [https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html)  
26. Code Overview (Copter) — Dev documentation \- ArduPilot, accessed December 4, 2025, [https://ardupilot.org/dev/docs/apmcopter-code-overview.html](https://ardupilot.org/dev/docs/apmcopter-code-overview.html)  
27. Using SITL — Dev documentation \- Simulation \- ArduPilot, accessed December 4, 2025, [https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html](https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html)  
28. SITL Parameters — Dev documentation \- ArduPilot, accessed December 4, 2025, [https://ardupilot.org/dev/docs/sitl-parameters.html](https://ardupilot.org/dev/docs/sitl-parameters.html)  
29. Using Simulation Parameters to Control the Simulation — Dev documentation \- ArduPilot, accessed December 4, 2025, [https://ardupilot.org/dev/docs/SITL\_simulation\_parameters.html](https://ardupilot.org/dev/docs/SITL_simulation_parameters.html)  
30. Build and simulate a Mini Pupper robot in the cloud without managing any infrastructure, accessed December 4, 2025, [https://aws.amazon.com/blogs/robotics/build-and-simulate-a-mini-pupper-robot-in-the-cloud-without-managing-any-infrastructure/](https://aws.amazon.com/blogs/robotics/build-and-simulate-a-mini-pupper-robot-in-the-cloud-without-managing-any-infrastructure/)  
31. Run any high-fidelity simulation in AWS RoboMaker with GPU and container support, accessed December 4, 2025, [https://aws.amazon.com/blogs/robotics/run-any-high-fidelity-simulation-in-aws-robomaker-with-gpu-and-container-support/](https://aws.amazon.com/blogs/robotics/run-any-high-fidelity-simulation-in-aws-robomaker-with-gpu-and-container-support/)  
32. awslabs/run-model-context-protocol-servers-with-aws-lambda \- GitHub, accessed December 4, 2025, [https://github.com/awslabs/run-model-context-protocol-servers-with-aws-lambda](https://github.com/awslabs/run-model-context-protocol-servers-with-aws-lambda)  
33. Tools \- Model Context Protocol, accessed December 4, 2025, [https://modelcontextprotocol.io/legacy/concepts/tools](https://modelcontextprotocol.io/legacy/concepts/tools)  
34. Model Context Protocol (MCP). MCP is an open protocol that… | by Aserdargun | Nov, 2025, accessed December 4, 2025, [https://medium.com/@aserdargun/model-context-protocol-mcp-e453b47cf254](https://medium.com/@aserdargun/model-context-protocol-mcp-e453b47cf254)  
35. Harness the power of MCP servers with Amazon Bedrock Agents | Artificial Intelligence, accessed December 4, 2025, [https://aws.amazon.com/blogs/machine-learning/harness-the-power-of-mcp-servers-with-amazon-bedrock-agents/](https://aws.amazon.com/blogs/machine-learning/harness-the-power-of-mcp-servers-with-amazon-bedrock-agents/)  
36. The curse of the A-word \- Temporal, accessed December 4, 2025, [https://temporal.io/blog/sergey-the-curse-of-the-a-word](https://temporal.io/blog/sergey-the-curse-of-the-a-word)  
37. Code execution with MCP: Building more efficient agents \- Anthropic, accessed December 4, 2025, [https://www.anthropic.com/engineering/code-execution-with-mcp](https://www.anthropic.com/engineering/code-execution-with-mcp)  
38. Use the C++ producer SDK on Raspberry Pi \- Amazon Kinesis Video Streams, accessed December 4, 2025, [https://docs.aws.amazon.com/kinesisvideostreams/latest/dg/producersdk-cpp-rpi.html](https://docs.aws.amazon.com/kinesisvideostreams/latest/dg/producersdk-cpp-rpi.html)  
39. GetMedia \- Amazon Kinesis Video Streams, accessed December 4, 2025, [https://docs.aws.amazon.com/kinesisvideostreams/latest/dg/API\_dataplane\_GetMedia.html](https://docs.aws.amazon.com/kinesisvideostreams/latest/dg/API_dataplane_GetMedia.html)  
40. Boto3 Kinesis Video GetMedia and OpenCV \- Stack Overflow, accessed December 4, 2025, [https://stackoverflow.com/questions/50061634/boto3-kinesis-video-getmedia-and-opencv](https://stackoverflow.com/questions/50061634/boto3-kinesis-video-getmedia-and-opencv)  
41. Implementing Claude 3.5 Sonnet on AWS: A Practical Guide – Part 2 \- IOD, accessed December 4, 2025, [https://iamondemand.com/blog/implementing-claude-3-5-sonnet-on-aws-a-practical-guide-part-2/](https://iamondemand.com/blog/implementing-claude-3-5-sonnet-on-aws-a-practical-guide-part-2/)  
42. Sending images to Claude 3 using Amazon Bedrock. | by codingmatheus \- Medium, accessed December 4, 2025, [https://medium.com/@codingmatheus/sending-images-to-claude-3-using-amazon-bedrock-b588f104424f](https://medium.com/@codingmatheus/sending-images-to-claude-3-using-amazon-bedrock-b588f104424f)