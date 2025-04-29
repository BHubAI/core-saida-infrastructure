import os

import aws_cdk as cdk

from core_sinfra import CoreSaidaInfrastructure

stack_name = os.environ.get("CDK_STACK_NAME", "CoreSaidaInfrastructure")
app = cdk.App()

# Get environment from context or use defaults
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", os.environ.get("AWS_ACCOUNT_ID")),
    region=os.environ.get(
        "CDK_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1")
    ),
)

CoreSaidaInfrastructure(app, stack_name, env=env)
app.synth()
