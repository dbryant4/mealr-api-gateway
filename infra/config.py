"""Load deploy configuration from cdk-params.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

STACK_NAME = "MealrApiGateway"
PARAMS_PATH = Path(__file__).resolve().parent.parent / "cdk-params.json"

REQUIRED_KEYS = (
    "ApiDomainName",
    "ApiDomainCertificateArn",
    "RecipesApiId",
    "MealPlansApiId",
    "AskApiId",
    "ShoppingListsApiId",
)


@dataclass(frozen=True)
class GatewayConfig:
    api_domain_name: str
    api_domain_certificate_arn: str
    recipes_api_id: str
    meal_plans_api_id: str
    ask_api_id: str
    shopping_lists_api_id: str
    api_endpoint_export_name: str = "mealr-api-gateway-CustomDomainTarget"

    @classmethod
    def load(cls, path: Path = PARAMS_PATH) -> GatewayConfig:
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

        return cls(
            api_domain_name=params["ApiDomainName"],
            api_domain_certificate_arn=params["ApiDomainCertificateArn"],
            recipes_api_id=params["RecipesApiId"],
            meal_plans_api_id=params["MealPlansApiId"],
            ask_api_id=params["AskApiId"],
            shopping_lists_api_id=params["ShoppingListsApiId"],
            api_endpoint_export_name=params.get(
                "ApiEndpointExportName", "mealr-api-gateway-CustomDomainTarget"
            ),
        )
