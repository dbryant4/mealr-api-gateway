# Mealr platform architecture

High-level view of the Mealr system for operators and contributors. GitHub renders the Mermaid diagrams in this file natively.

## Table of Contents

- [System overview](#system-overview)
- [Authentication](#authentication)
- [API gateway](#api-gateway)
- [Recipe ingest pipeline](#recipe-ingest-pipeline)
- [Ask / knowledge base](#ask--knowledge-base)
- [This repository](#this-repository)
- [Repository map](#repository-map)

---

## System overview

Production hostnames shown are the current defaults (`app2.mealr.recipes`, `api2.mealr.recipes`). Each service stack can override domains via CDK context.

```mermaid
flowchart TB
  user(["User browser"])

  subgraph edge ["Edge"]
    web["mealr-web<br/>app2.mealr.recipes<br/>CloudFront + React SPA"]
    gw["mealr-api-gateway<br/>api2.mealr.recipes<br/>base-path routing only"]
  end

  subgraph identity ["Identity"]
    cognito["mealr-auth<br/>Cognito User Pool<br/>OIDC + MFA"]
  end

  subgraph apis ["HTTP APIs — each stack runs its own JWT authorizer"]
    account["mealr-account-api<br/>/account"]
    recipes["mealr-recipes-api<br/>/recipes"]
    shopping["mealr-shopping-list-api<br/>/shopping-lists"]
    ask["mealr-kb-api<br/>/ask"]
  end

  subgraph pipeline ["Ingest & search"]
    ingestor["mealr-pdf-ingestor<br/>Step Functions"]
    kb["mealr-kb<br/>Bedrock Knowledge Base sync"]
  end

  subgraph storage ["Shared data plane"]
    s3in[("S3 input bucket<br/>imports/… PDFs")]
    s3out[("S3 output bucket<br/>recipes/userId/…")]
    ddb[("DynamoDB<br/>import jobs, lists,<br/>shares, metadata")]
  end

  user -->|OIDC PKCE sign-in| cognito
  user --> web
  web -->|Bearer access token| gw
  gw --> account
  gw --> recipes
  gw --> shopping
  gw --> ask

  account -->|AdminGetUser / user APIs| cognito
  recipes --> s3out
  recipes --> s3in
  recipes --> ddb
  recipes -.->|presigned PUT + job rows| s3in
  recipes -.->|retry / reprocess| ingestor
  shopping --> s3out
  shopping --> ddb
  ask -->|Retrieve + Converse| kb
  ask --> ddb

  s3in -->|ObjectCreated .pdf| ingestor
  ingestor --> s3out
  ingestor --> ddb
  s3out -->|recipe.json created| kb

  style gw fill:#dbeafe,stroke:#2563eb,stroke-width:2px
```

---

## Authentication

```mermaid
sequenceDiagram
  participant U as User
  participant W as mealr-web
  participant C as mealr-auth (Cognito)
  participant G as mealr-api-gateway
  participant A as Downstream API

  U->>W: Open app
  W->>C: OIDC authorization code + PKCE
  C->>W: ID + access tokens
  W->>G: HTTPS + Authorization Bearer
  G->>A: Forward (strip base path)
  A->>A: Lambda authorizer validates JWT
  A->>W: JSON response
```

- **mealr-web** stores tokens client-side (`oidc-client-ts`) and attaches the **access token** to API calls.
- **mealr-api-gateway** routes only — it does not validate JWTs.
- Each HTTP API (**recipes**, **shopping-lists**, **ask**, **account**) runs its own Cognito JWT authorizer.

---

## API gateway

| Client path | Service | Notes |
|-------------|---------|--------|
| `https://api2.mealr.recipes/account/*` | mealr-account-api | Profile, password, MFA, passkeys |
| `https://api2.mealr.recipes/recipes/*` | mealr-recipes-api | Recipes, imports, shares, library |
| `https://api2.mealr.recipes/shopping-lists/*` | mealr-shopping-list-api | Shopping lists |
| `https://api2.mealr.recipes/ask/*` | mealr-kb-api | Recipe Q&A |

API Gateway **strips the base path** before forwarding (e.g. `GET /recipes/` → downstream `GET /`).

---

## Recipe ingest pipeline

```mermaid
flowchart LR
  subgraph upload ["Upload (mealr-web + recipes API)"]
    A["POST /imports/batches"]
    B["Presigned PUT"]
  end

  subgraph ingestor ["mealr-pdf-ingestor"]
    D["Dispatcher"]
    SFN["Step Functions<br/>Extract → Validate →<br/>Render → Banner → Save"]
  end

  A --> B
  B --> s3in[("S3 input")]
  s3in --> D
  D --> SFN
  SFN --> s3out[("S3 output<br/>recipe.json + images")]
  SFN --> jobs[("ImportJobsTable")]

  style ingestor fill:#f3f4f6
```

**mealr-recipes-api** creates import job rows and presigned URLs; the **ingestor** owns the pipeline and writes structured recipes to the output bucket.

---

## Ask / knowledge base

```mermaid
flowchart LR
  s3out[("recipe.json in S3")] -->|EventBridge| sync["mealr-kb sync Lambda"]
  sync --> kbdoc["kb/*.md + metadata"]
  kbdoc --> bedrock["Amazon Bedrock<br/>Knowledge Base"]
  web["mealr-web / Ask"] --> askapi["mealr-kb-api"]
  askapi --> bedrock
  askapi -->|Converse| llm["Claude"]
```

**mealr-kb** indexes recipes for semantic search; **mealr-kb-api** retrieves context and generates answers with citations.

---

## This repository

**mealr-api-gateway** owns the shared API custom domain (`api2.mealr.recipes`) and **base-path mappings** to four downstream HTTP APIs. It contains no Lambda, no routes, and no authentication — only `CfnDomainName` + `CfnApiMapping` resources.

Path mappings: see repo `README.md` and `infra/gateway_stack.py`.

---

## Repository map

| Repository | Role |
|------------|------|
| [mealr-web](https://github.com/dbryant4/mealr-web) | React UI, CloudFront, `/assets` recipe images |
| **mealr-api-gateway** | **Custom domain + path mappings (this repo)** |
| [mealr-auth](https://github.com/dbryant4/mealr-auth) | Cognito user pool |
| [mealr-recipes-api](https://github.com/dbryant4/mealr-recipes-api) | Recipes, imports, shares, library |
| [mealr-shopping-list-api](https://github.com/dbryant4/mealr-shopping-list-api) | Shopping lists |
| [mealr-kb-api](https://github.com/dbryant4/mealr-kb-api) | Ask / Q&A API |
| [mealr-account-api](https://github.com/dbryant4/mealr-account-api) | Profile & security |
| [mealr-pdf-ingestor](https://github.com/dbryant4/mealr-pdf-ingestor) | PDF → JSON pipeline |
| [mealr-kb](https://github.com/dbryant4/mealr-kb) | Bedrock KB indexing |

Keep this document aligned across repos when platform wiring changes.