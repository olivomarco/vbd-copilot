# FinCore Bank API - Engineering Onboarding

Welcome to the FinCore Bank engineering team.

You have been dropped into the middle of a sprint. The core banking API is partially
built, partially broken, and the previous developer left a trail of improvement markers and
known issues in the backlog. Your job is to work through the sprint tasks using GitHub
Copilot to accelerate your productivity.

## What This Application Does

FinCore Bank is a UK-headquartered retail bank. This repository contains the internal
REST API that powers account management, transaction processing, and fund transfers for
retail customers. It is a Python 3.11 FastAPI application backed by SQLite for
development (PostgreSQL in production).

## Running the Application

From this directory (`resources/starter/`):

```
uvicorn app.main:app --reload
```

The API will start at http://localhost:8000. The interactive docs are at
http://localhost:8000/docs (development mode only).

To authenticate with the demo API, obtain a token first:

```
curl -X POST http://localhost:8000/auth/token \
  -d "username=developer@fincore.bank&password=hackathon2024"
```

## Running Tests

From this directory:

```
pytest
```

Or for verbose output:

```
pytest -v tests/
```

## Known Issues and Backlog

The following issues have been noted by the outgoing developer. These are the areas
you will be working through during the hackathon sprint:

- Monetary fields use `float` instead of `Decimal`. This causes rounding errors that
  could affect transaction accuracy. See `app/models/`.
- `InterestService` has calculation bugs that have not been caught because there are
  no unit tests. See `app/services/interest_service.py`.
- There is no audit logging anywhere in the service layer. Compliance requires that
  all balance changes are logged with who made the change and when.
- The JWT implementation uses HS256. Banking security policy requires RS256.
- The `/transfers` endpoint has no idempotency protection. Duplicate requests can
  result in double charges.
- Unit tests for `AccountService` and `InterestService` are missing entirely.

## Directory Structure

```
app/
  main.py           - FastAPI application setup and router registration
  config.py         - Settings loaded from environment variables
  exceptions.py     - Custom exception hierarchy
  database.py       - SQLAlchemy engine setup (not yet wired to services)
  models/           - Pydantic v2 request/response schemas
  services/         - Business logic layer
  api/
    routers/        - FastAPI route handlers
    dependencies.py - Shared FastAPI dependency functions
  utils/
    logging.py      - structlog configuration
tests/
  unit/             - Unit tests for service layer
  integration/      - API-level smoke tests
synthetic_data/
  transactions.csv  - 200 sample transactions for analysis tasks
```
