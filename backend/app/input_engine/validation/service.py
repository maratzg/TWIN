import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.input_engine.normalization.service import NormalizationError, normalize_value


CONTAINER_PATTERN = re.compile(r"^[A-Z]{4}[0-9]{7}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
IDENTIFIER_FIELDS = (
    "shipment_reference",
    "booking_reference",
    "bill_of_lading_number",
    "container_number",
)


@dataclass(frozen=True)
class ValidationIssue:
    row: int
    field: str | None
    severity: str
    code: str
    message: str


@dataclass
class ValidationResult:
    row_number: int
    system_normalized_data: dict[str, Any]
    normalized_data: dict[str, Any]
    disposition: str
    issues: list[ValidationIssue]


def _validate_normalized(row_number: int, data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not any(data.get(field) for field in IDENTIFIER_FIELDS):
        issues.append(
            ValidationIssue(
                row_number,
                None,
                "ERROR",
                "MISSING_IDENTIFIER",
                "A shipment, bill of lading, or container reference is required.",
            )
        )
    for field in ("revenue", "gross_weight", "teu"):
        if data.get(field) is not None and Decimal(data[field]) < 0:
            issues.append(
                ValidationIssue(row_number, field, "ERROR", "NEGATIVE_VALUE", f"{field.replace('_', ' ').title()} cannot be negative.")
            )
    currency = data.get("currency")
    if currency and not CURRENCY_PATTERN.fullmatch(currency):
        issues.append(ValidationIssue(row_number, "currency", "ERROR", "INVALID_CURRENCY", "Currency must be a three-letter code."))
    container = data.get("container_number")
    if container and not CONTAINER_PATTERN.fullmatch(container.replace(" ", "")):
        issues.append(
            ValidationIssue(row_number, "container_number", "WARNING", "INVALID_CONTAINER_SHAPE", "Container number does not match the expected four letters and seven digits shape.")
        )
    if data.get("etd") and data.get("eta") and date.fromisoformat(data["eta"]) < date.fromisoformat(data["etd"]):
        issues.append(ValidationIssue(row_number, "eta", "WARNING", "ETA_BEFORE_ETD", "ETA is earlier than ETD and requires review."))
    return issues


def _duplicate_key(data: dict[str, Any]) -> tuple[str, str] | None:
    for field in IDENTIFIER_FIELDS:
        if data.get(field):
            return field, str(data[field]).upper()
    return None


def validate_rows(
    rows: list[tuple[int, dict[str, Any]]],
    mapping: dict[str, str],
    unresolved_columns: set[str] | None = None,
    corrections: dict[int, dict[str, Any]] | None = None,
) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    seen: dict[tuple[str, str], int] = {}
    unresolved_columns = unresolved_columns or set()
    corrections = corrections or {}

    for row_number, raw in rows:
        issues: list[ValidationIssue] = []
        system_normalized: dict[str, Any] = {}
        row_corrections = corrections.get(row_number, {})
        for source_column, canonical_field in mapping.items():
            try:
                normalized_value = normalize_value(raw.get(source_column), canonical_field)
                if normalized_value is not None:
                    system_normalized[canonical_field] = normalized_value
            except NormalizationError as exc:
                if canonical_field not in row_corrections:
                    issues.append(ValidationIssue(row_number, exc.field, "ERROR", exc.code, exc.message))
        normalized = {**system_normalized, **row_corrections}
        if normalized:
            issues.extend(_validate_normalized(row_number, normalized))
            duplicate_key = _duplicate_key(normalized)
            if duplicate_key and duplicate_key in seen:
                issues.append(
                    ValidationIssue(
                        row_number,
                        duplicate_key[0],
                        "ERROR",
                        "DUPLICATE_IN_FILE",
                        f"Duplicate of source row {seen[duplicate_key]}.",
                    )
                )
            elif duplicate_key:
                seen[duplicate_key] = row_number
        nonempty_unmapped = [column for column in unresolved_columns if raw.get(column) not in (None, "")]
        if nonempty_unmapped:
            issues.append(
                ValidationIssue(
                    row_number,
                    nonempty_unmapped[0],
                    "WARNING",
                    "UNMAPPED_VALUE",
                    f"Unmapped source data exists in: {', '.join(sorted(nonempty_unmapped))}.",
                )
            )
        severities = {issue.severity for issue in issues}
        disposition = "invalid" if "ERROR" in severities else "review" if "WARNING" in severities else "ready"
        results.append(
            ValidationResult(row_number, system_normalized, normalized, disposition, issues)
        )
    return results
