# Responsible AI

CSA-Copilot uses AI models to produce customer-facing technical content. The following principles apply:

## Human in the loop

Every pipeline has mandatory approval stops before content is built and before output is delivered. No content reaches a customer without a human reviewing and accepting the plan.

## Accuracy over speed

All research is restricted to official Microsoft and GitHub sources (MS Learn, docs.github.com, devblogs.microsoft.com, techcommunity.microsoft.com). Invented URLs are explicitly forbidden; every link in generated output must be real and verifiable.

## Transparency

Generated `.pptx` files and demo guides are first drafts, not finished deliverables. The README, app UI, and speaker notes all state this. Users are expected to review, fact-check, and own the content before presenting it.

## No sensitive data in prompts

Do not include customer names, internal project codenames, NDA-protected details, pricing data, or personal information in generation prompts. Use generic placeholders (e.g. "Contoso") when a customer name is needed for narrative context.

## Content scope

The tool is scoped to technical education content for Microsoft Cloud products. It is not intended to generate marketing claims, competitive comparisons, financial projections, or legal/compliance guidance.

## Model behaviour

This tool delegates to GitHub Copilot models via the GitHub Copilot SDK. It does not fine-tune or modify model weights. All model usage is subject to the [GitHub Copilot Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#github-copilot) and [Microsoft Responsible AI principles](https://www.microsoft.com/en-us/ai/responsible-ai).
