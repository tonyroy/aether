
from aws_cdk import (
    CfnOutput,
    Stack,
)
from aws_cdk import (
    aws_iot as iot,
)
from constructs import Construct


class IoTStack(Stack):
    """AWS IoT Core stack for drone fleet management"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # IoT Policy for drones
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["iot:Connect"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:client/${{iot:Connection.Thing.ThingName}}"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Publish"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/${{iot:Connection.Thing.ThingName}}/telemetry",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/${{iot:Connection.Thing.ThingName}}/status",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/$aws/things/${{iot:Connection.Thing.ThingName}}/shadow/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Subscribe"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:topicfilter/mav/${{iot:Connection.Thing.ThingName}}/cmd",
                        f"arn:aws:iot:{self.region}:{self.account}:topicfilter/mav/${{iot:Connection.Thing.ThingName}}/mission",
                        f"arn:aws:iot:{self.region}:{self.account}:topicfilter/$aws/things/${{iot:Connection.Thing.ThingName}}/shadow/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Receive"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/${{iot:Connection.Thing.ThingName}}/cmd",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/${{iot:Connection.Thing.ThingName}}/mission",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/$aws/things/${{iot:Connection.Thing.ThingName}}/shadow/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:GetThingShadow",
                        "iot:UpdateThingShadow",
                        "iot:DeleteThingShadow"
                    ],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:thing/${{iot:Connection.Thing.ThingName}}"
                    ]
                }
            ]
        }

        self.drone_policy = iot.CfnPolicy(
            self, "DronePolicy",
            policy_name="AetherDronePolicy",
            policy_document=policy_document
        )

        # IoT Policy for Orchestrator
        orchestrator_policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["iot:Connect"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:client/orchestrator"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Publish"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/*/cmd",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/*/mission",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/$aws/things/*/shadow/update"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Subscribe"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:topicfilter/mav/*/status",
                        f"arn:aws:iot:{self.region}:{self.account}:topicfilter/mav/*/telemetry"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Receive"],
                    "Resource": [
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/*/status",
                        f"arn:aws:iot:{self.region}:{self.account}:topic/mav/*/telemetry"
                    ]
                }
            ]
        }

        self.orchestrator_policy = iot.CfnPolicy(
            self, "OrchestratorPolicy",
            policy_name="AetherOrchestratorPolicy",
            policy_document=orchestrator_policy_doc
        )

        # Enable Fleet Indexing (Registry + Shadow + Connectivity)
        from aws_cdk.aws_iam import PolicyStatement
        from aws_cdk.custom_resources import AwsCustomResource, AwsCustomResourcePolicy, AwsSdkCall, PhysicalResourceId

        self.fleet_indexing = AwsCustomResource(
            self, "FleetIndexing",
            on_create=AwsSdkCall(
                service="Iot",
                action="updateIndexingConfiguration",
                parameters={
                    "thingIndexingConfiguration": {
                        "thingIndexingMode": "REGISTRY_AND_SHADOW",
                        "thingConnectivityIndexingMode": "STATUS"
                    }
                },
                physical_resource_id=PhysicalResourceId.of("FleetIndexingConfig")
            ),
            on_update=AwsSdkCall(
                service="Iot",
                action="updateIndexingConfiguration",
                parameters={
                    "thingIndexingConfiguration": {
                        "thingIndexingMode": "REGISTRY_AND_SHADOW",
                        "thingConnectivityIndexingMode": "STATUS"
                    }
                },
                physical_resource_id=PhysicalResourceId.of("FleetIndexingConfig")
            ),
            policy=AwsCustomResourcePolicy.from_statements(
                statements=[
                    PolicyStatement(
                        actions=["iot:UpdateIndexingConfiguration"],
                        resources=["*"]
                    )
                ]
            )
        )

        # Output the IoT endpoint
        CfnOutput(
            self, "IoTEndpoint",
            value=f"{self.account}.iot.{self.region}.amazonaws.com",
            description="AWS IoT Core endpoint for drones",
            export_name="AetherIoTEndpoint"
        )

        CfnOutput(
            self, "PolicyName",
            value=self.drone_policy.policy_name,
            description="IoT Policy name for drones",
            export_name="AetherDronePolicyName"
        )
