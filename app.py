#!/usr/bin/env python3
"""AWS CDK application entry point for mealr-api-gateway."""

import aws_cdk as cdk

from infra.config import GatewayConfig
from infra.gateway_stack import GatewayStack


def main() -> None:
    app = cdk.App(outdir="cdk.out")
    GatewayStack(app, "MealrApiGateway", config=GatewayConfig.load())
    app.synth()


if __name__ == "__main__":
    main()
