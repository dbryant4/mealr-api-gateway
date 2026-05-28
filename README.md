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
- [Wire downstream stacks](#wire-downstream-stacks)
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
         ├── /shopping-lists  ──►  mealr-shopping-list-api   HTTP API ($default)
         └── /ask              ──►  mealr-kb-api              HTTP API ($default)
```

Each downstream API Gateway handles its own routing, Lambda integrations, and Cognito JWT authorizer. API Gateway **strips the base-path prefix** before forwarding, so a request to `api.mealr.com/recipes/abc` reaches the recipes API at `GET /abc`.

At synth time, this stack reads each downstream stack's **`ApiId`** output via CloudFormation `DescribeStacks` (stack names are configurable in `cdk-params.json`).

---

## Path mappings

| Base path | Downstream service | Default stack name |
| --- | --- | --- |
| `/recipes` | mealr-recipes-api | `MealrRecipesApiStack` |
| `/shopping-lists` | mealr-shopping-list-api | `MealrShoppingApiStack` |
| `/ask` | mealr-kb-api | `MealrKbApiStack` |

---

## Repository layout

| Path | Purpose |
| --- | --- |
| `VERSION` | Semver for this repo (`MAJOR.MINOR.PATCH`); bump per `.cursor/rules/semver.mdc` |
| `infra/gateway_stack.py` | CDK stack: `CfnDomainName` + three `CfnApiMapping` resources |
| `infra/config.py` | Loads `cdk-params.json` and resolves downstream `ApiId` outputs at synth time |
| `app.py` | CDK `App` entrypoint; synth writes to `cdk.out/` |
| `cdk.json` | CDK CLI config; `app` runs `.venv/bin/python app.py` |
| `requirements.txt` | CDK runtime deps (`aws-cdk-lib`, `constructs`, `boto3`) |
| `requirements-dev.txt` | CDK CLI (`aws-cdk.cli`) |
| `cdk-params.example.json` | Committed template — copy to `cdk-params.json` and fill in values |
| `cdk-params.json` | Local deploy config (**gitignored**); read by `app.py` at synth time |

---

## Prerequisites

- **Python 3.12+**.
- **AWS credentials** for the account/region you deploy to, with **`cloudformation:DescribeStacks`** (used at synth time to read downstream `ApiId` outputs).
- **CDK CLI** from the venv (`pip install -r requirements-dev.txt`). `cdk.json` runs the app via `.venv/bin/python app.py`.
- An **ACM certificate** in the same region as your API Gateway, valid for the custom domain.
- Downstream stacks (**mealr-recipes-api**, **mealr-shopping-list-api**, **mealr-kb-api**) must already be deployed with an **`ApiId`** stack output (see [Wire downstream stacks](#wire-downstream-stacks)).

> No CDK bootstrap required — this stack has no Lambda assets or S3 uploads.

---

## Stack parameters

Configuration lives in **`cdk-params.json`**, read at synth time by `infra/config.py`.

```bash
cp cdk-params.example.json cdk-params.json
# edit cdk-params.json
```

| Key | Required | Default | Description |
| --- | --- | --- | --- |
| `ApiDomainName` | Yes | — | Custom domain hostname (e.g. `api.mealr.com`) |
| `ApiDomainCertificateArn` | Yes | — | ACM certificate ARN in this region |
| `RecipesApiStackName` | No | `MealrRecipesApiStack` | CloudFormation stack for `/recipes` mapping |
| `ShoppingListsApiStackName` | No | `MealrShoppingApiStack` | CloudFormation stack for `/shopping-lists` mapping |
| `AskApiStackName` | No | `MealrKbApiStack` | CloudFormation stack for `/ask` mapping |
| `ApiEndpointExportName` | No | `mealr-api-gateway-CustomDomainTarget` | CloudFormation export name for `CustomDomainTarget` |

**CDK context overrides** (optional — skip `DescribeStacks` for offline synth):

| Context key | Purpose |
| --- | --- |
| `recipesApiId` | Override resolved recipes HTTP API ID |
| `shoppingListsApiId` | Override resolved shopping-lists HTTP API ID |
| `askApiId` | Override resolved ask HTTP API ID |
| `region` | AWS region for `DescribeStacks` (default `us-east-1`) |

Example:

```bash
cdk synth \
  -c recipesApiId=abc123 \
  -c shoppingListsApiId=def456 \
  -c askApiId=ghi789
```

---

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Validate the template without deploying (requires AWS credentials and deployed downstream stacks, or context overrides above):

```bash
cdk synth
```

---

## Deploy (AWS CDK)

Deploy downstream API stacks first, then the gateway. With `cdk-params.json` filled in and the venv active:

```bash
cdk deploy
```

After deploy, the stack outputs **`CustomDomainTarget`** — the regional domain name to use as your DNS target (see [Custom domain DNS](#custom-domain-dns)) — and **`StackVersion`**, the semver of this release (from `VERSION` at synth time).

---

## Wire downstream stacks

Each downstream stack outputs **`ApiId`** and exports it for cross-stack use:

| Service repo | Default stack name | CloudFormation export | Gateway base path |
| --- | --- | --- | --- |
| mealr-recipes-api | `MealrRecipesApiStack` | `RecipesApiId` | `/recipes` |
| mealr-shopping-list-api | `MealrShoppingApiStack` | `ShoppingListsApiId` | `/shopping-lists` |
| mealr-kb-api | `MealrKbApiStack` | `AskApiId` | `/ask` |

Deploy order:

1. `cdk deploy` in each downstream repo (prerequisites: `MealrPdfIngestorStack` for recipes/shopping; `MealrKbStack` for kb-api).
2. `cdk deploy` in this repo — reads each stack's **`ApiId`** output at synth time.

If you renamed a downstream stack, set the matching `*ApiStackName` key in `cdk-params.json`.

**Path stripping reminder:** API Gateway strips the base-path prefix before forwarding. Routes in each downstream API should be defined _without_ the service prefix:

| Request to custom domain | Forwarded to downstream API as |
| --- | --- |
| `GET /recipes/abc` | `GET /abc` |
| `POST /shopping-lists/` | `POST /` |
| `GET /shopping-lists/{id}` | `GET /{id}` |
| `POST /ask/query` | `POST /query` |

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
| `cdk synth` fails: could not find output `ApiId` | Deploy the downstream stack first, or fix `*ApiStackName` in `cdk-params.json`. Shopping stack output key is **`ApiId`** (not `ShoppingApiId`). |
| `cdk synth` fails: AWS credentials / `DescribeStacks` | Use valid AWS credentials, or pass `-c recipesApiId=...` (and shopping/ask) to skip lookup. |
| `cdk` command not found | Activate the venv or run `.venv/bin/cdk`. |
| Deploy fails: certificate not found / not valid | ACM cert must be in the **same region** as the stack and in `ISSUED` status. |
| DNS not resolving after deploy | Check that the `A`/`CNAME` record points to the `CustomDomainTarget` output, not the API execute URL. |
| `api.mealr.com/recipes/...` returns `404` | Confirm downstream stack is deployed, `ApiId` is correct, and stage is `$default`. |

---

## Maintaining this README

When you change path mappings, parameters, or layout:

1. Update the [**Path mappings**](#path-mappings) table to match `_MAPPINGS` in `infra/gateway_stack.py`.
2. Update the [**Stack parameters**](#stack-parameters) table if keys change in `infra/config.py`.
3. Update the [**Table of contents**](#table-of-contents) if sections are added or renamed.
4. Follow the Cursor project rule [`.cursor/rules/readme-sync.mdc`](.cursor/rules/readme-sync.mdc).
