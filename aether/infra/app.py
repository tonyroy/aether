#!/usr/bin/env python3
import os

import aws_cdk as cdk
from infra.iot_stack import IoTStack

app = cdk.App()

# Deploy to default AWS account/region from CLI configuration
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION')
)

IoTStack(app, "AetherIoTStack", env=env)

app.synth()
