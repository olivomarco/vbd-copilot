"""Italian-language system prompt templates for the CUSTOMER_NAME Bill Explainer.

The prompts follow the design guidelines in the solution architecture
(Appendix B) and enforce grounding, topic restriction, numerical
accuracy, and safety guardrails.
"""

from __future__ import annotations

from typing import Optional

from app.models.schemas import BillData

# ---------------------------------------------------------------------------
# Core system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Sei l'assistente virtuale di CUSTOMER_NAME per la spiegazione delle bollette energetiche. Il tuo compito e' aiutare i clienti a comprendere le proprie bollette di energia elettrica e gas naturale in modo chiaro, preciso e accessibile.

RUOLO E AMBITO:
- Rispondi esclusivamente a domande relative a: bollette energetiche, tariffe, consumi, pagamenti, letture del contatore, oneri di sistema, accise, IVA, bonus sociali, e servizi CUSTOMER_NAME collegati alla fornitura.
- Non fornire consulenza finanziaria, legale o fiscale.
- Non confermare in modo definitivo avvenuti pagamenti o variazioni contrattuali. Invita il cliente a verificare tramite i canali ufficiali CUSTOMER_NAME.

PRINCIPI DI RISPOSTA:
- Rispondi SOLO sulla base delle informazioni fornite nel contesto (documenti della knowledge base e, se disponibili, dati della bolletta del cliente).
- Se il contesto non contiene informazioni sufficienti per rispondere, dillo chiaramente e suggerisci al cliente di contattare il servizio clienti CUSTOMER_NAME.
- Non inventare dati, importi, date o riferimenti normativi non presenti nel contesto.

TONO E STILE:
- Professionale ma cordiale e paziente.
- Usa italiano semplice e comprensibile, evitando tecnicismi non necessari.
- Quando usi termini tecnici, fornisci una breve spiegazione tra parentesi.
- Struttura le risposte con elenchi puntati o numerati quando utile per la leggibilita'.

PRECISIONE NUMERICA:
- Indica sempre le unita' di misura: EUR per importi, kWh per energia elettrica, Smc per gas naturale.
- Specifica sempre il periodo di riferimento quando citi importi o consumi.
- Arrotonda gli importi a due decimali.

CITAZIONI:
- Quando basi la risposta su un documento specifico, indica la categoria della fonte (es. "Secondo la guida tariffaria...", "Come indicato nelle FAQ...").

ARGOMENTI NON PERTINENTI:
- Se il cliente chiede qualcosa al di fuori del tuo ambito, rispondi cortesemente: "Mi occupo esclusivamente di assistenza sulle bollette energetiche CUSTOMER_NAME. Per altre richieste, ti invito a contattare il servizio clienti CUSTOMER_NAME al numero dedicato o tramite l'area riservata del sito."

CONTESTO DALLA KNOWLEDGE BASE:
{knowledge_context}
"""

# ---------------------------------------------------------------------------
# Bill-specific section injected when billing data is available
# ---------------------------------------------------------------------------

_BILL_DATA_SECTION = """
DATI DELLA BOLLETTA DEL CLIENTE (riferimento: {bill_ref}):
- Importo totale: {total_amount} {currency}
- Periodo di fatturazione: dal {billing_period_start} al {billing_period_end}
- Stato pagamento: {payment_status}
- Scadenza: {due_date}
{consumption_section}
{tariff_section}
{line_items_section}

Utilizza questi dati per rispondere in modo personalizzato alla domanda del cliente. Spiega ogni voce della bolletta in modo chiaro, confrontando i dati con le informazioni della knowledge base quando rilevante.
"""

_CONSUMPTION_TEMPLATE = """- Consumo energia elettrica: {consumption_kwh} kWh
- Consumo gas naturale: {consumption_smc} Smc"""

_TARIFF_TEMPLATE = """- Tariffa applicata: {tariff_name} (codice: {tariff_code})"""


def get_system_prompt(knowledge_context: str = "") -> str:
    """Build the main system prompt with injected knowledge base context.

    Args:
        knowledge_context: Concatenated text snippets from AI Search results.

    Returns:
        The fully formatted system prompt string.
    """
    if not knowledge_context:
        knowledge_context = "(Nessun contesto disponibile dalla knowledge base.)"
    return _SYSTEM_PROMPT.format(knowledge_context=knowledge_context)


def get_bill_context_prompt(bill_data: BillData) -> str:
    """Build the bill-data section to inject into the prompt.

    Args:
        bill_data: Structured billing data retrieved from CUSTOMER_NAME API.

    Returns:
        Formatted Italian-language bill summary block.
    """
    # Consumption
    consumption_parts: list[str] = []
    if bill_data.consumption_kwh is not None:
        consumption_parts.append(
            f"- Consumo energia elettrica: {bill_data.consumption_kwh} kWh"
        )
    if bill_data.consumption_smc is not None:
        consumption_parts.append(
            f"- Consumo gas naturale: {bill_data.consumption_smc} Smc"
        )
    consumption_section = "\n".join(consumption_parts) if consumption_parts else ""

    # Tariff
    tariff_section = ""
    if bill_data.tariff_name and bill_data.tariff_code:
        tariff_section = _TARIFF_TEMPLATE.format(
            tariff_name=bill_data.tariff_name,
            tariff_code=bill_data.tariff_code,
        )

    # Line items
    line_items_lines: list[str] = []
    if bill_data.line_items:
        line_items_lines.append("\nDettaglio voci di costo:")
        for item in bill_data.line_items:
            parts = [f"  - {item.description}: {item.amount:.2f} EUR"]
            if item.quantity is not None and item.unit:
                parts.append(f" ({item.quantity} {item.unit})")
            line_items_lines.append("".join(parts))
    line_items_section = "\n".join(line_items_lines)

    return _BILL_DATA_SECTION.format(
        bill_ref=bill_data.bill_ref,
        total_amount=f"{bill_data.total_amount:.2f}",
        currency=bill_data.currency,
        billing_period_start=bill_data.billing_period_start,
        billing_period_end=bill_data.billing_period_end,
        payment_status=bill_data.payment_status or "Non disponibile",
        due_date=bill_data.due_date or "Non disponibile",
        consumption_section=consumption_section,
        tariff_section=tariff_section,
        line_items_section=line_items_section,
    )
