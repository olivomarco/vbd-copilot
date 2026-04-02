# Project Context

- **Owner:** Marco Olivo
- **Project:** CSA-Copilot — AI-powered engagement platform for Cloud Solution Architects. 80% test coverage gate enforced via pytest --cov.
- **Stack:** Python 3.11+, pytest with pytest-asyncio (asyncio_mode = auto), coverage config in pyproject.toml
- **Test files:** test_store.py, test_router.py, test_collector.py, test_models.py, test_queries.py, test_hackathon_qa.py, test_pricing.py, test_tools.py, test_loader.py, test_commands.py, test_app.py, test_registry.py
- **QA scripts:** skills/pptx-generator/pptx_qa_checks.py, skills/demo-generator/demo_qa_checks.py, skills/architecture-design/architecture_qa_checks.py, skills/code-project/infra_qa_checks.py, skills/code-project/pipeline_qa_checks.py, skills/code-project/docs_qa_checks.py, skills/hackathon-generator/hackathon_qa_checks.py
- **Coverage config:** source=["."], omit app.py, ui.py, tests/, skills/, agent_defs/, scripts/, outputs/, plans/
- **Created:** 2026-04-02

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->
