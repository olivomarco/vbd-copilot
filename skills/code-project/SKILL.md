# Code Project Skill

This skill provides patterns, structure, and quality checks for generating full-stack Azure project implementations.

## Mandatory Work Packages

The ai-implementor conductor produces 8 work packages under `outputs/ai-projects/<project-slug>/`:

### 1. Infrastructure (infra/)
Bicep modules with parameter files:
- Logical module separation: networking, security, compute, data, monitoring
- Parameter files for dev/staging/prod environments
- Resource naming convention: kebab-case with environment prefix
- Tags for cost tracking and governance
- Security: Key Vault for secrets, managed identities, RBAC, private endpoints

### 2. Application Code (src/)
All application components:
- Azure SDK with DefaultAzureCredential for authentication
- Environment-based configuration (no hardcoded values)
- Clear separation of concerns
- Package manifest (requirements.txt, package.json, or .csproj)

### 3. CI/CD Pipelines (.github/workflows/)
GitHub Actions or Azure DevOps pipelines:
- Infrastructure deployment workflow
- Application deployment workflow
- Appropriate triggers (push, PR, manual dispatch)
- Secrets via `${{ secrets.X }}` - never hardcoded

### 4. Deploy Script (scripts/deploy.sh)
Single idempotent bash script:
```
set -euo pipefail
Functions: deploy_infra(), deploy_app(), main()
Flags: --help, --infra-only, --app-only
Params: resource group, location, environment (via args or env vars)
Prerequisites check: az CLI, logged-in session
```

### 5. Unit Tests (tests/unit/)
- Standard framework: pytest (Python), Jest (Node), xunit/nunit (.NET)
- Cover core business logic, not boilerplate
- Include test config (conftest.py, jest.config, etc.)
- Runnable with single standard command

### 6. Smoke Tests (tests/smoke/)
- Health check for each deployed endpoint
- Basic API operations (create/read minimum)
- Use env vars for endpoint URLs
- Skip gracefully when endpoints unreachable

### 7. Validation Script (tests/validate.sh)
Single entry-point for verification:
```
set -euo pipefail
Functions: validate_infra(), run_unit_tests(), run_smoke_tests(), main()
Flag: --live (enables smoke tests)
Prerequisites check: runtimes, az CLI, test frameworks
Summary: PASS/FAIL at the end
```

### 8. README (README.md)
Sections: project overview, prerequisites, env setup, infra deployment, app deployment, quick deploy (deploy.sh), validation (validate.sh), local dev, demo guide (with sample I/O), troubleshooting.

## Build Order
infra -> app code -> pipelines -> deploy script -> unit tests -> smoke tests -> validate.sh -> README

## Review Process
4 specialist reviewers, each scoped to one area:
- **infra-reviewer-subagent**: infra/ directory
- **code-reviewer-subagent**: src/ and tests/
- **pipeline-reviewer-subagent**: .github/workflows/, scripts/deploy.sh, tests/validate.sh
- **docs-reviewer-subagent**: README.md

## QA Checks
- `infra_qa_checks.py` - Bicep syntax, security patterns, naming, tags
- `pipeline_qa_checks.py` - Workflow YAML, secret handling, script structure
- `docs_qa_checks.py` - README sections, path accuracy, command correctness

## Quality Rules
- No placeholder text (TODO, TBD, FIXME)
- No emoji characters
- No em-dashes (use hyphens)
- Azure-only services and SDKs
- All environment variables documented
