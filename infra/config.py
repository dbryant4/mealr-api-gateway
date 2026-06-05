"""Load deploy configuration from cdk-params.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3

STACK_NAME = "MealrApiGateway"
PARAMS_PATH = Path(__file__).resolve().parent.parent / "cdk-params.json"
API_ID_OUTPUT_KEY = "ApiId"

DEFAULT_ACCOUNT_API_STACK_NAME = "MealrAccountApiStack"
DEFAULT_RECIPES_API_STACK_NAME = "MealrRecipesApiStack"
DEFAULT_SHOPPING_LISTS_API_STACK_NAME = "MealrShoppingApiStack"
DEFAULT_ASK_API_STACK_NAME = "MealrKbApiStack"

REQUIRED_KEYS = (
    "ApiDomainName",
    "ApiDomainCertificateArn",
)


def _get_stack_output(region: str, stack_name: str, output_key: str) -> str:
    """Read a CloudFormation stack output value."""
    cf = boto3.client("cloudformation", region_name=region)
    resp = cf.describe_stacks(StackName=stack_name)
    outputs = resp["Stacks"][0].get("Outputs", [])
    match = next((o["OutputValue"] for o in outputs if o["OutputKey"] == output_key), None)
    if not match:
        raise RuntimeError(
            f"Could not find output '{output_key}' in stack '{stack_name}'. "
            "Is the stack deployed?"
        )
    return match


@dataclass(frozen=True)
class GatewayConfig:
    api_domain_name: str
    api_domain_certificate_arn: str
    account_api_id: str
    recipes_api_id: str
    shopping_lists_api_id: str
    ask_api_id: str
    account_api_stack_name: str = DEFAULT_ACCOUNT_API_STACK_NAME
    recipes_api_stack_name: str = DEFAULT_RECIPES_API_STACK_NAME
    shopping_lists_api_stack_name: str = DEFAULT_SHOPPING_LISTS_API_STACK_NAME
    ask_api_stack_name: str = DEFAULT_ASK_API_STACK_NAME
    api_endpoint_export_name: str = "mealr-api-gateway-CustomDomainTarget"

    @classmethod
    def load(
        cls,
        path: Path = PARAMS_PATH,
        *,
        region: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> GatewayConfig:
        if not path.is_file():
            raise SystemExit(
                f"Missing {path.name}. Copy cdk-params.example.json to {path.name} "
                "and fill in your values, then run cdk deploy again."
            )

        data = json.loads(path.read_text())
        params = data.get(STACK_NAME)
        if not isinstance(params, dict):
            raise SystemExit(
                f"{path.name} must contain a top-level object named {STACK_NAME!r}."
            )

        missing = [key for key in REQUIRED_KEYS if not params.get(key)]
        if missing:
            raise SystemExit(
                f"Missing required keys in {path.name} under {STACK_NAME!r}: "
                f"{', '.join(missing)}"
            )

        ctx = context or {}
        deploy_region = (
            region
            or ctx.get("region")
            or os.environ.get("AWS_DEFAULT_REGION")
            or os.environ.get("AWS_REGION")
            or "us-east-1"
        )

        account_stack = params.get("AccountApiStackName", DEFAULT_ACCOUNT_API_STACK_NAME)
        recipes_stack = params.get("RecipesApiStackName", DEFAULT_RECIPES_API_STACK_NAME)
        shopping_stack = params.get(
            "ShoppingListsApiStackName", DEFAULT_SHOPPING_LISTS_API_STACK_NAME
        )
        ask_stack = params.get("AskApiStackName", DEFAULT_ASK_API_STACK_NAME)

        account_api_id = ctx.get("accountApiId") or _get_stack_output(
            deploy_region, account_stack, API_ID_OUTPUT_KEY
        )
        recipes_api_id = ctx.get("recipesApiId") or _get_stack_output(
            deploy_region, recipes_stack, API_ID_OUTPUT_KEY
        )
        shopping_lists_api_id = ctx.get("shoppingListsApiId") or _get_stack_output(
            deploy_region, shopping_stack, API_ID_OUTPUT_KEY
        )
        ask_api_id = ctx.get("askApiId") or _get_stack_output(
            deploy_region, ask_stack, API_ID_OUTPUT_KEY
        )

        return cls(
            api_domain_name=params["ApiDomainName"],
            api_domain_certificate_arn=params["ApiDomainCertificateArn"],
            account_api_id=account_api_id,
            recipes_api_id=recipes_api_id,
            shopping_lists_api_id=shopping_lists_api_id,
            ask_api_id=ask_api_id,
            account_api_stack_name=account_stack,
            recipes_api_stack_name=recipes_stack,
            shopping_lists_api_stack_name=shopping_stack,
            ask_api_stack_name=ask_stack,
            api_endpoint_export_name=params.get(
                "ApiEndpointExportName", "mealr-api-gateway-CustomDomainTarget"
            ),
        )
