#!/usr/bin/env python3
"""AWS CDK application entry point for mealr-api-gateway."""

import aws_cdk as cdk

from infra.config import GatewayConfig
from infra.gateway_stack import GatewayStack


def main() -> None:
    app = cdk.App(outdir="cdk.out")
    region = app.node.try_get_context("region")
    GatewayStack(
        app,
        "MealrApiGateway",
        config=GatewayConfig.load(region=region, context=app.node.get_all_context()),
    )
    app.synth()


if __name__ == "__main__":
    main()
