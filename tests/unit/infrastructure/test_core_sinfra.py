import os

import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest
from aws_cdk.assertions import Template

from core_sinfra import CoreSaidaInfrastructure


@pytest.fixture(scope="session")
def stack() -> Template:
    stack_name = os.environ.get("TESTING_STACK_NAME", "CoreSaidaInfrastructure")
    assert stack_name != ""

    app = cdk.App()
    stack = CoreSaidaInfrastructure(app, "CoreSaidaInfrastructure")
    return assertions.Template.from_stack(stack)


def test_stack_created(stack):
    assert stack
