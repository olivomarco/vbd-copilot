# Architecture Design Skill

This skill provides patterns, structure, and quality checks for generating Azure solution architecture documentation.

## Output Files

The architecture-builder-subagent produces exactly 7 files under `outputs/<project-slug>/docs/`:

### 1. executive-brief.md

Customer-facing executive summary (2-3 pages max). Sections:

- **Business Challenge** - the problem in the customer's language, no jargon
- **Recommended Solution** - top 3-5 recommended projects distilled from brainstorming, with one-paragraph description each
- **Expected Business Impact** - quantified ROI, key metrics, and value framing (cost of solution vs. value delivered or current spend replaced)
- **High-Level Timeline** - simplified phased roadmap (phases, durations, key milestones only)
- **Why Azure** - positioning of Azure-native advantages for this specific scenario
- **Next Steps** - concrete call to action (workshop, PoC, pilot)

This is the document you hand to a CTO/CDO. It must stand alone without requiring the technical docs.

### 2. solution-design.md

The single comprehensive architecture document. Sections:

- **Executive Summary** - 2-3 paragraph overview for leadership
- **Architecture Design** - Component breakdown with Azure service choices and justification
- **Data Flows and Integrations** - Sequence of data movement between components, external APIs, data sources
- **Security and Governance** - Entra ID, Key Vault, RBAC, compliance controls
- **Non-Functional Requirements** - Performance targets, scalability, availability (SLA tiers), DR strategy

### 3. architecture-diagram.drawio

A valid draw.io XML file:

- Root element: `<mxfile>`
- At least one `<diagram>` child with `<mxGraphModel>`
- Use `<mxCell>` elements for each component
- Azure-themed shapes and colors
- Show all major components, data flows, and integration points

### 4. data-assessment.md

Data requirements and integration analysis. Sections:

- **Required Data Sources** - each data source needed, its purpose, expected format, and volume
- **Data Quality Prerequisites** - minimum quality standards, cleansing needs, known gaps
- **Privacy and Compliance** - GDPR, sector-specific regulations (e.g. ARERA, PCI-DSS, HIPAA), data residency requirements, DPIAs needed
- **Integration Points** - connections to existing systems (CRM, ERP, billing, APIs), authentication methods, expected latency
- **Data Readiness Risks** - things that could block or delay the project (missing access, poor quality, unresolved ownership)

### 5. responsible-ai.md

Responsible AI and ethics assessment. Sections:

- **AI Use Case Classification** - risk tier per EU AI Act and Microsoft Responsible AI Standard
- **Fairness and Bias** - assessment of potential bias in training data and model outputs, mitigation strategies
- **Transparency and Explainability** - how decisions are explained to end users, audit trail requirements
- **Human Oversight** - human-in-the-loop guardrails, escalation paths, override mechanisms
- **Data Retention and Privacy** - right-to-erasure compliance, data minimization, retention policies
- **Model Monitoring** - drift detection, performance degradation alerts, retraining triggers
- **Content Safety** - guardrails against harmful outputs, grounding requirements, hallucination mitigation

### 6. cost-estimation.md

Azure pricing and ROI analysis:

- Service-by-service cost breakdown with SKU names and tiers
- Monthly estimated cost per service
- Reserved vs pay-as-you-go comparison
- Total monthly and annual estimates
- **ROI framing** - cost of the solution vs. value delivered (revenue uplift, cost savings, or current spend replaced)
- Optimization recommendations

### 7. delivery-plan.md

Phased delivery roadmap:

- Phase breakdown with milestones and durations
- Dependencies between work streams
- Team structure and role requirements
- Risk register with mitigations
- **Engagement plan** - maps delivery phases to customer interactions (discovery workshops, architecture reviews, PoC demos, go/no-go checkpoints, handover sessions)

## Quality Rules

- No placeholder text (TODO, TBD, FIXME, lorem ipsum)
- No emoji characters
- No em-dashes (use hyphens)
- Azure-only services (no AWS, GCP)
- All links must be real and verified

## QA Checks

Use `architecture_qa_checks.py` for automated validation. It checks:

- All 7 files exist
- drawio XML is well-formed with required elements
- Markdown sections are present and populated
- No placeholder text patterns
- No competitor cloud references
