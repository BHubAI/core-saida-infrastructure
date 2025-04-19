import os

import aws_cdk as cdk

from core_sinfra import CoreSaidaInfrastructure

stack_name = os.environ.get("TESTING_STACK_NAME", "CoreSaidaInfrastructure")
app = cdk.App()
CoreSaidaInfrastructure(app, stack_name).build()
app.synth()
