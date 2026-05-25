"""CDK stack: custom domain + base-path mappings to downstream HTTP API Gateways."""

from pathlib import Path

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from constructs import Construct

from infra.config import GatewayConfig

_VERSION = Path(__file__).resolve().parent.parent.joinpath("VERSION").read_text().strip()
_STACK_DESCRIPTION = (
    f"Mealr unified API gateway v{_VERSION}: regional custom domain and HTTP API "
    "v2 base-path mappings (/recipes, /meal-plans, /shopping-lists, /ai) to "
    "downstream service APIs. No Lambda, JWT, CORS, or business logic in this stack."
)

# base-path prefix → (downstream API ID field, logical CDK id suffix)
_MAPPINGS: list[tuple[str, str]] = [
    ("recipes", "Recipes"),
    ("meal-plans", "MealPlans"),
    ("ai", "Ai"),
    ("shopping-lists", "ShoppingLists"),
]


class GatewayStack(Stack):
    """Routes traffic from api.mealr.com to each downstream HTTP API by base path.

    No business logic, no Lambda, no auth. Each downstream service owns its own
    API Gateway with its own Cognito JWT authorizer.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: GatewayConfig,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, description=_STACK_DESCRIPTION, **kwargs)

        domain = apigw.CfnDomainName(
            self,
            "ApiCustomDomain",
            domain_name=config.api_domain_name,
            domain_name_configurations=[
                apigw.CfnDomainName.DomainNameConfigurationProperty(
                    certificate_arn=config.api_domain_certificate_arn,
                    endpoint_type="REGIONAL",
                )
            ],
        )

        api_ids = {
            "Recipes": config.recipes_api_id,
            "MealPlans": config.meal_plans_api_id,
            "Ai": config.ai_api_id,
            "ShoppingLists": config.shopping_lists_api_id,
        }

        for base_path, logical_id in _MAPPINGS:
            apigw.CfnApiMapping(
                self,
                f"{logical_id}ApiMapping",
                api_id=api_ids[logical_id],
                domain_name=domain.ref,
                stage="$default",
                api_mapping_key=base_path,
            )

        CfnOutput(
            self,
            "StackVersion",
            description="Semver of this mealr-api-gateway release (from VERSION at synth time)",
            value=_VERSION,
        )

        CfnOutput(
            self,
            "CustomDomainTarget",
            description=(
                "Regional domain name to use as your DNS alias/CNAME target "
                f"for {config.api_domain_name}"
            ),
            value=domain.attr_regional_domain_name,
            export_name=config.api_endpoint_export_name,
        )
