from datetime import date
from decimal import Decimal, InvalidOperation

from app.document_engine.types import ValidationFinding


REQUIRED_FIELDS = {
    "invoice_number",
    "invoice_date",
    "currency",
    "subtotal",
    "vat_amount",
    "total_amount",
    "direction",
}


def validate_invoice_candidates(
    values: dict[str, object],
    *,
    candidate_statuses: dict[str, str],
    party_resolution: str,
    duplicate: bool,
    reference_conflict: bool,
    tolerance: Decimal,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for field in sorted(REQUIRED_FIELDS):
        if values.get(field) in {None, ""}:
            findings.append(
                ValidationFinding(field, "ERROR", "MISSING_REQUIRED_FIELD", f"{field.replace('_', ' ').title()} is required.")
            )
    for field, status in candidate_statuses.items():
        if status == "error":
            findings.append(
                ValidationFinding(field, "ERROR", "INVALID_FIELD_VALUE", f"{field.replace('_', ' ').title()} could not be normalized safely.")
            )
        elif status == "review":
            findings.append(
                ValidationFinding(field, "WARNING", "LOW_CONFIDENCE_FIELD", f"{field.replace('_', ' ').title()} needs human confirmation.")
            )

    invoice_date = _date(values.get("invoice_date"))
    due_date = _date(values.get("due_date"))
    if invoice_date and due_date and due_date < invoice_date:
        findings.append(ValidationFinding("due_date", "ERROR", "DUE_BEFORE_INVOICE_DATE", "Due date cannot be earlier than the invoice date."))

    amounts = {field: _decimal(values.get(field)) for field in ("subtotal", "vat_amount", "total_amount")}
    for field, amount in amounts.items():
        if amount is not None and amount < 0:
            findings.append(ValidationFinding(field, "ERROR", "NEGATIVE_AMOUNT", "Invoice amounts cannot be negative."))
    if all(amount is not None for amount in amounts.values()):
        expected = amounts["subtotal"] + amounts["vat_amount"]
        if abs(expected - amounts["total_amount"]) > tolerance:
            findings.append(
                ValidationFinding(
                    "total_amount",
                    "ERROR",
                    "ARITHMETIC_MISMATCH",
                    "Subtotal plus VAT does not equal the total within the configured rounding tolerance.",
                )
            )

    currency = values.get("currency")
    if currency and (not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha()):
        findings.append(ValidationFinding("currency", "ERROR", "INVALID_CURRENCY", "Currency must be a three-letter code."))
    if party_resolution == "unresolved":
        findings.append(ValidationFinding(None, "ERROR", "PARTY_UNRESOLVED", "The external invoice party could not be resolved safely."))
    elif party_resolution == "new_candidate":
        findings.append(ValidationFinding(None, "WARNING", "NEW_PARTY_CANDIDATE", "A new canonical party will be created when this reviewed invoice is committed."))
    if duplicate:
        findings.append(ValidationFinding("invoice_number", "ERROR", "DUPLICATE_INVOICE", "A canonical invoice with this identity already exists."))
    if reference_conflict:
        findings.append(ValidationFinding(None, "WARNING", "REFERENCE_CONFLICT", "Extracted references resolve to different shipments."))
    return findings


def _date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except InvalidOperation:
        return None
