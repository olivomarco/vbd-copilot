# Architecture Design Skill

This skill provides patterns, structure, and quality checks for generating Azure solution architecture documentation.

## Output Files

The architecture-builder-subagent produces exactly 5 files under `outputs/<project-slug>/docs/`:

### 1. solution-design.md
The single comprehensive architecture document. Sections:
- **Executive Summary** - 2-3 paragraph overview for leadership
- **Architecture Design** - Component breakdown with Azure service choices and justification
- **Data Flows and Integrations** - Sequence of data movement between components, external APIs, data sources
- **Security and Governance** - Entra ID, Key Vault, RBAC, responsible AI, compliance controls
- **Non-Functional Requirements** - Performance targets, scalability, availability (SLA tiers), DR strategy

### 2. architecture-diagram.drawio
A valid draw.io XML file:
- Root element: `<mxfile>`
- At least one `<diagram>` child with `<mxGraphModel>`
- Use `<mxCell>` elements for each component
- Azure-themed shapes and colors
- Show all major components, data flows, and integration points

### 3. architecture-diagram.md
ASCII art alternative:
- Fenced code block containing box-drawing characters (+, -, |, >, <)
- Legend explaining symbols
- Component descriptions below the diagram

### 4. cost-estimation.md
Azure pricing analysis:
- Service-by-service cost breakdown with SKU names and tiers
- Monthly estimated cost per service
- Reserved vs pay-as-you-go comparison
- Total monthly and annual estimates
- Optimization recommendations

### 5. delivery-plan.md
Phased delivery roadmap:
- Phase breakdown with milestones and durations
- Dependencies between work streams
- Team structure and role requirements
- Risk register with mitigations

## Quality Rules
- No placeholder text (TODO, TBD, FIXME, lorem ipsum)
- No emoji characters
- No em-dashes (use hyphens)
- Azure-only services (no AWS, GCP)
- All links must be real and verified

## QA Checks
Use `architecture_qa_checks.py` for automated validation. It checks:
- All 5 files exist
- drawio XML is well-formed with required elements
- Markdown sections are present and populated
- No placeholder text patterns
- No competitor cloud references
- ASCII diagram presence in architecture-diagram.md
