# FinCore Bank - Reference Architecture

This document describes the technical architecture of the FinCore Bank API and shows
how GitHub Copilot fits into the developer workflow at each layer. All nine hackathon
challenges build toward this complete picture.

## System Overview

FinCore Bank's retail API is a Python 3.11 FastAPI application organised into three
layers. Clients - internal tooling, mobile apps, and partner integrations - send HTTP
requests to the API layer. The API layer delegates to a service layer that owns all
business logic. The service layer reads and writes through a model and data layer that
defines the data shapes and persistence mechanism.

The application is designed to run as a single stateless container, with state held
in a PostgreSQL database in production and SQLite during development and the hackathon.

## Architecture Diagram

```
+------------------------------------------------------------------+
|                         HTTP Clients                             |
|   Mobile App   Partner API   Internal Tooling   Test Suite       |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                         API Layer                                |
|                                                                  |
|   POST /auth/token    (authentication, JWT issuance)             |
|   GET  /accounts/     (list, filter by active status)            |
|   POST /accounts/     (open a new account)                       |
|   GET  /accounts/{id} (retrieve by ID)                           |
|   POST /transactions/ (record debit, credit, fee, interest)      |
|   GET  /transactions/{account_id}  (history for one account)     |
|   POST /transfers/    (atomic debit + credit pair)               |
|                                                                  |
|   FastAPI routers + Pydantic request/response validation         |
|   Bearer token enforcement via HTTPBearer dependency             |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                       Service Layer                              |
|                                                                  |
|   AccountService       - account lifecycle, balance mutation     |
|   TransactionService   - transaction validation and recording    |
|   InterestService      - simple and compound interest maths      |
|                                                                  |
|   Business rules, error handling, structlog audit trail          |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                   Model and Data Layer                           |
|                                                                  |
|   Pydantic v2 schemas  - Account, Transaction, Transfer,         |
|                           request/response validation            |
|   In-memory dict store - used in dev and hackathon scenarios     |
|   SQLAlchemy engine    - wired for production SQLite / Postgres  |
|                                                                  |
+------------------------------------------------------------------+
```

## Component Descriptions

### API Layer

The API layer contains FastAPI routers, one per domain area. Each router is
responsible only for HTTP concerns: parsing and validating request bodies with
Pydantic, calling the appropriate service method, and returning a structured response.
Routers do not contain business logic. The `get_current_user` dependency in
`app/api/dependencies.py` enforces authentication on every endpoint except `/health`
and `/auth/token`.

### Service Layer

The service layer owns all business rules. It is where decisions like "can this account
be closed?" or "is this transaction amount valid given the current balance?" are made.
Services hold no HTTP context - they accept and return domain objects (Pydantic models)
and raise typed exceptions from `app/exceptions.py`. This design makes services
directly testable without spinning up the web server.

### Model and Data Layer

The model layer defines the canonical shapes for accounts, transactions, and transfers
using Pydantic v2. These models are used both for API serialisation and as the internal
currency passed between services. The `app/database.py` module sets up a SQLAlchemy
engine and declarative base. During the hackathon the services use an in-memory dict
store; wiring them to SQLAlchemy is an exercise in the later challenges.

## Data Flow: Create Transfer

The following trace shows how a POST /transfers/ request moves through the system:

```
1. Client sends POST /transfers/ with bearer token and TransferRequest body

2. FastAPI routes to transfers.create_transfer()
   - HTTPBearer extracts the JWT
   - get_current_user() decodes and validates it
   - Pydantic validates the TransferRequest body

3. transfers.create_transfer() calls:
   a. account_service.get_account(source_id)   - verify source exists
   b. account_service.get_account(dest_id)     - verify dest exists
   c. transaction_service.create_transaction() - debit source (transfer_out)
      i.  validate_transaction() checks active status and available funds
      ii. account_service.update_balance() writes new source balance
      iii. Transaction record created and stored
   d. transaction_service.create_transaction() - credit dest (transfer_in)
      i.  validate_transaction() checks active status (no funds check for credits)
      ii. account_service.update_balance() writes new dest balance
      iii. Transaction record created and stored

4. TransferResponse returned to client with both transaction IDs
```

## GitHub Copilot in the Developer Workflow

GitHub Copilot assists at every layer of this architecture in distinct ways:

### At the Model Layer
Copilot accelerates schema authoring. When you type a class name and a field or two,
Copilot predicts the remaining fields, type annotations, and validators. The inline
suggestion triggered by the IBAN format comment in `AccountCreate` is an example of
this. Challenge 01 focuses on this layer.

### At the Service Layer
Copilot Chat is most useful for generating test cases and explaining business logic.
Given an existing service method, Copilot can generate pytest unit tests covering happy
paths, error paths, and edge cases. It also helps identify bugs when you ask it to
explain what a method does step by step. Challenges 03 and 04 work in this layer.

### At the API Layer
Copilot assists with route stubs, middleware patterns, and dependency injection
boilerplate. When you describe a new endpoint in a comment, it can suggest the
complete route handler. Challenge 07 (Agent Mode) works across the API and service
layers simultaneously.

### At the Standards Layer
Custom instructions in `.github/copilot-instructions.md` teach Copilot about FinCore
Bank's coding standards: Decimal for money, RS256 for JWT, audit logging requirements.
Once in place, Copilot applies these standards automatically in every suggestion across
the codebase. Challenge 05 builds this file.

## GitHub Copilot Features Reference

| Feature | VS Code Entry Point | Best Used For | Challenges |
|---|---|---|---|
| Inline suggestions (ghost text) | Automatic while typing | Field definitions, boilerplate, repetitive patterns | 01, 02 |
| Copilot Chat - ask a question | Ctrl+Alt+I, then type | Explaining code, generating tests, debugging | 02, 03, 04 |
| @workspace participant | Chat: type @workspace | Questions that need cross-file context | 02, 06 |
| /fix slash command | Chat: type /fix | Targeted bug fixes with explanation | 04 |
| /tests slash command | Chat: type /tests | Generating test cases for selected code | 03 |
| /explain slash command | Chat: type /explain | Understanding unfamiliar code | 02, 04 |
| Custom instructions | .github/copilot-instructions.md | Team-wide coding standards enforcement | 05 |
| Copilot Edits (Plan Mode) | Copilot menu > Open Copilot Edits | Multi-file refactoring with a review step | 06 |
| Agent Mode | Copilot Edits > set to Agent | End-to-end feature implementation | 07 |
| Copilot Coding Agent | github.com > Issues > "Assign to Copilot" | Autonomous PR from an issue description | 08 |

## Challenge-to-Architecture Layer Mapping

| Challenge | Title | Primary Layer | Copilot Feature |
|---|---|---|---|
| 00 | Environment Setup | All | Inline + Chat basics |
| 01 | Ghost Text Mastery | Model layer | Inline suggestions |
| 02 | Chat Context and Participants | Service + API | Chat, @workspace, /explain |
| 03 | Test-Driven Development | Service layer | /tests, Chat |
| 04 | Debugging and Code Quality | Service layer | /fix, /explain, Chat |
| 05 | Custom Instructions | All (standards) | copilot-instructions.md |
| 06 | Multi-File Refactoring | Service + API | Plan Mode, @workspace |
| 07 | End-to-End Feature Development | All layers | Agent Mode |
| 08 | Copilot Coding Agent (Capstone) | All layers | Copilot Coding Agent |

## Production Deployment on Azure

In a production deployment, the FinCore Bank API would run on the following Azure
services:

| Component | Azure Service | Purpose |
|---|---|---|
| API hosting | Azure App Service (Python) | Managed web hosting with autoscale |
| Database | Azure Database for PostgreSQL | Managed PostgreSQL with high availability |
| Secrets | Azure Key Vault | Stores FINCORE_SECRET_KEY, DB credentials |
| Container registry | Azure Container Registry | Hosts the production Docker image |
| Observability | Azure Monitor + Application Insights | Structured log ingestion from structlog |
| CI/CD | GitHub Actions | Build, test, and deploy pipeline |
| Identity | Azure Entra ID | Federated user identity for enterprise login |

The dev container in this repository replicates the runtime environment locally so that
developers can build and test against a faithful representation of the production stack.

## Known Issues and Sprint Backlog

The following gaps are present in the starter application intentionally. Each challenge
targets one or more of them:

1. Monetary fields use `float` instead of `Decimal`. Surfaces in challenges 01, 03, 05.
2. `InterestService` has an off-by-one bug and swallows errors with bare `except:`.
   Surfaces in challenge 04.
3. No `.github/copilot-instructions.md` to encode FinCore Bank coding standards.
   Created in challenge 05.
4. No audit logging in the service layer. Added in challenge 06.
5. JWT uses HS256 instead of RS256. Addressed as a stretch goal in challenge 07 via custom instructions.
6. The `/transfers` endpoint has no idempotency protection. Addressed in challenge 08.
7. Unit tests for `AccountService` and `InterestService` are missing. Added in
   challenges 03 and 04.

## Further Reading

- GitHub Copilot official documentation: https://docs.github.com/en/copilot
- GitHub Copilot Chat in VS Code: https://code.visualstudio.com/docs/copilot/copilot-chat
- GitHub Copilot custom instructions: https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot
- Pydantic v2 documentation: https://docs.pydantic.dev/latest/
- FastAPI documentation: https://fastapi.tiangolo.com
- structlog documentation: https://www.structlog.org/en/stable/
