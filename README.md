# mealr-api-gateway

**Version:** see [`VERSION`](VERSION) (semver).

Owns the **custom domain** (`api.mealr.com`) and **base-path mappings** that route traffic to each downstream Mealr service's API Gateway. No business logic, no Lambda, no auth — each service owns those entirely.

---

## Table of contents

- [What this repo owns](#what-this-repo-owns)
- [Architecture](#architecture)
- [Path mappings](#path-mappings)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Stack parameters](#stack-parameters)
- [Local development](#local-development)
- [Deploy (AWS CDK)](#deploy-aws-cdk)
- [Wire downstream API IDs](#wire-downstream-api-ids)
- [Custom domain DNS](#custom-domain-dns)
- [Errors](#errors)
- [Troubleshooting](#troubleshooting)
- [Maintaining this README](#maintaining-this-readme)

---

## What this repo owns

- **`AWS::ApiGatewayV2::DomainName`** for `api.mealr.com` (or configured domain).
- **`AWS::ApiGatewayV2::ApiMapping`** per service — maps a base-path prefix to a downstream HTTP API's `$default` stage.
- **CloudFormation export** of the regional domain target for DNS wiring.

Nothing else. No routes, no Lambda, no IAM, no auth.

---

## Architecture

```text
DNS  api.mealr.com
         │
         ▼
AWS API Gateway Custom Domain
         │
         ├── /recipes         ──►  mealr-recipes-api         HTTP API ($default)
         ├── /meal-plans      ──►  mealr-meal-plans-api      HTTP API ($default)
         ├── /shopping-lists  ──►  mealr-shopping-list-api   HTTP API ($default)
         └── /ai              ──►  mealr-ai-api              HTTP API ($default)
```

Each downstream API Gateway handles its own routing, Lambda integrations, and Cognito JWT authorizer. API Gateway **strips the base-path prefix** before forwarding, so a request to `api.mealr.com/recipes/abc` reaches the recipes API at `GET /abc`.

---

## Path mappings

| Base path | Downstream service |
| --- | --- |
| `/recipes` | mealr-recipes-api |
| `/meal-plans` | mealr-meal-plans-api |
| `/shopping-lists` | mealr-shopping-list-api |
| `/ai` | mealr-ai-api |

---

## Repository layout

| Path | Purpose |
| --- | --- |
| `VERSION` | Semver for this repo (`MAJOR.MINOR.PATCH`); bump per `.cursor/rules/semver.mdc` |
| `infra/gateway_stack.py` | CDK stack: `CfnDomainName` + four `CfnApiMapping` resources |
| `infra/config.py` | Loads and validates `cdk-params.json` at synth time |
| `app.py` | CDK `App` entrypoint; synth writes to `cdk.out/` |
| `cdk.json` | CDK CLI config; `app` runs `.venv/bin/python app.py` |
| `requirements.txt` | CDK runtime deps (`aws-cdk-lib`, `constructs`) |
| `requirements-dev.txt` | CDK CLI (`aws-cdk.cli`) |
| `cdk-params.example.json` | Committed template — copy to `cdk-params.json` and fill in values |
| `cdk-params.json` | Local deploy config (**gitignored**); read by `app.py` at synth time |

---

## Prerequisites

- **Python 3.12+**.
- **AWS credentials** for the account/region you deploy to.
- **CDK CLI** from the venv (`pip install -r requirements-dev.txt`). `cdk.json` runs the app via `.venv/bin/python app.py`.
- An **ACM certificate** in the same region as your API Gateway, valid for the custom domain.
- Downstream stacks (**mealr-recipes-api**, **mealr-meal-plans-api**, **mealr-shopping-list-api**, **mealr-ai-api**) must already be deployed and expose their **HTTP API IDs** (see [Wire downstream API IDs](#wire-downstream-api-ids)).

> No CDK bootstrap required — this stack has no Lambda assets or S3 uploads.

---

## Stack parameters

Configuration lives in **`cdk-params.json`**, read at synth time by `infra/config.py`.

```bash
cp cdk-params.example.json cdk-params.json
# edit cdk-params.json
```

| Key | Required | Description |
| --- | --- | --- |
| `ApiDomainName` | Yes | Custom domain hostname (e.g. `api.mealr.com`) |
| `ApiDomainCertificateArn` | Yes | ACM certificate ARN in this region |
| `RecipesApiId` | Yes | HTTP API ID from mealr-recipes-api |
| `MealPlansApiId` | Yes | HTTP API ID from mealr-meal-plans-api |
| `ShoppingListsApiId` | Yes | HTTP API ID from mealr-shopping-list-api (`ShoppingApiId` output) |
| `AiApiId` | Yes | HTTP API ID from mealr-ai-api |
| `ApiEndpointExportName` | No | CloudFormation export name for `CustomDomainTarget` (default `mealr-api-gateway-CustomDomainTarget`) |

---

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Validate the template without deploying:

```bash
cdk synth
```

---

## Deploy (AWS CDK)

With `cdk-params.json` filled in and the venv active:

```bash
cdk deploy
```

After deploy, the stack outputs **`CustomDomainTarget`** — the regional domain name to use as your DNS target (see [Custom domain DNS](#custom-domain-dns)) — and **`StackVersion`**, the semver of this release (from `VERSION` at synth time).

---

## Wire downstream API IDs

Each downstream stack must output (and ideally export) its **HTTP API ID**. Recommended export names:

| Stack | Recommended export name |
| --- | --- |
| mealr-recipes-api | `mealr-recipes-api-HttpApiId` |
| mealr-meal-plans-api | `mealr-meal-plans-api-HttpApiId` |
| mealr-shopping-list-api | `ShoppingApiId` stack output |
| mealr-ai-api | `mealr-ai-api-HttpApiId` |

Look up or export those values and put them in `cdk-params.json` as `RecipesApiId`, `MealPlansApiId`, `ShoppingListsApiId`, `AiApiId`.

**Path stripping reminder:** API Gateway strips the base-path prefix before forwarding. Routes in each downstream API should be defined _without_ the service prefix:

| Request to custom domain | Forwarded to downstream API as |
| --- | --- |
| `GET /recipes/abc` | `GET /abc` |
| `POST /meal-plans/generate` | `POST /generate` |
| `POST /shopping-lists/` | `POST /` |
| `GET /shopping-lists/{id}` | `GET /{id}` |
| `POST /ai/query` | `POST /query` |

---

## Custom domain DNS

After deploy, point your domain's DNS at the `CustomDomainTarget` stack output:

- **Route 53:** Create an `A` record (alias) pointing to the regional domain name from the output.
- **Other DNS providers:** Create a `CNAME` pointing to the same value.

---

## Errors

Gateway-level errors (before the request reaches a downstream API):

| Scenario | Result |
| --- | --- |
| No mapping matches the base path | `404 {"message":"Not Found"}` from API Gateway |
| Invalid base-path mapping (misconfigured API ID/stage) | `500` or `403` from API Gateway |

All other errors (auth, validation, business logic) are owned by the downstream APIs.

---

## Troubleshooting

| Symptom | Things to check |
| --- | --- |
| `cdk synth` fails: missing `cdk-params.json` | Run `cp cdk-params.example.json cdk-params.json` and fill in required keys. |
| `cdk` command not found | Activate the venv or run `.venv/bin/cdk`. |
| Deploy fails: certificate not found / not valid | ACM cert must be in the **same region** as the stack and in `ISSUED` status. |
| DNS not resolving after deploy | Check that the `A`/`CNAME` record points to the `CustomDomainTarget` output, not the API execute URL. |
| `api.mealr.com/recipes/...` returns `404` | Confirm the `RecipesApiId` in `cdk-params.json` matches the deployed API and that stage is `$default`. |

---

## Maintaining this README

When you change path mappings, parameters, or layout:

1. Update the [**Path mappings**](#path-mappings) table to match `_MAPPINGS` in `infra/gateway_stack.py`.
2. Update the [**Stack parameters**](#stack-parameters) table if keys change in `infra/config.py`.
3. Update the [**Table of contents**](#table-of-contents) if sections are added or renamed.
4. Follow the Cursor project rule [`.cursor/rules/readme-sync.mdc`](.cursor/rules/readme-sync.mdc).
