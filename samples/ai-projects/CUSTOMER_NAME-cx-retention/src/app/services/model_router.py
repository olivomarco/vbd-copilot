"""Model routing logic -- classify queries as simple or complex.

Simple queries (approximately 80% of traffic) are routed to GPT-4o-mini
for cost efficiency. Complex queries are routed to GPT-4o for stronger
numerical reasoning.

Classification criteria:
  - Complex if: bill_ref is provided, message > 200 chars, contains
    numerical-comparison keywords, or conversation turn > 5.
  - Simple otherwise (default).
"""

from __future__ import annotations

import logging
import re

from app.config import Settings
from app.models.schemas import ModelClassification

logger = logging.getLogger(__name__)

# Italian keywords that signal numerical comparison or complex reasoning
_COMPLEX_KEYWORDS: set[str] = {
    "confronto", "confronta", "differenza", "aumento", "diminuzione",
    "rispetto", "precedente", "variazione", "calcolo", "calcola",
    "dettaglio", "ripartizione", "scostamento", "percentuale",
    "media", "totale", "somma", "tabella",
}

_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(_COMPLEX_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


class ModelRouter:
    """Classify user queries and select the appropriate LLM deployment."""

    def __init__(self, settings: Settings) -> None:
        self._gpt4o_deployment = settings.azure_openai_gpt4o_deployment
        self._gpt4o_mini_deployment = settings.azure_openai_gpt4o_mini_deployment

    def classify(
        self,
        message: str,
        bill_ref: str | None = None,
        conversation_turn: int = 0,
    ) -> ModelClassification:
        """Determine which model deployment to use for the query.

        Args:
            message: The user's question text.
            bill_ref: Optional bill reference (indicates personalised lookup).
            conversation_turn: Number of user turns in the current session.

        Returns:
            ModelClassification with the chosen deployment, whether billing
            data is needed, and a short reasoning string.
        """
        reasons: list[str] = []
        needs_billing = False

        # Rule 1: bill reference present
        if bill_ref:
            reasons.append("bill reference provided")
            needs_billing = True

        # Rule 2: long message
        if len(message) > 200:
            reasons.append(f"message length {len(message)} > 200")

        # Rule 3: numerical-comparison keywords
        if _KEYWORD_PATTERN.search(message):
            reasons.append("contains numerical-comparison keywords")

        # Rule 4: deep conversation
        if conversation_turn > 5:
            reasons.append(f"conversation turn {conversation_turn} > 5")

        is_complex = len(reasons) > 0
        model = self._gpt4o_deployment if is_complex else self._gpt4o_mini_deployment
        reasoning = (
            f"Complex routing: {'; '.join(reasons)}"
            if is_complex
            else "Simple FAQ query -- using cost-effective model"
        )

        classification = ModelClassification(
            model=model,
            needs_billing_data=needs_billing,
            reasoning=reasoning,
        )

        logger.info(
            "Query classified: model=%s needs_billing=%s reasoning=%s",
            classification.model,
            classification.needs_billing_data,
            classification.reasoning,
        )
        return classification
