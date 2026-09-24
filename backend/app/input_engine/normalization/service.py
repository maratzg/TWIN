import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d")
DECIMAL_FIELDS = {"gross_weight", "teu", "revenue"}
DATE_FIELDS = {"etd", "eta"}
UPPER_FIELDS = {"currency", "container_number", "status"}


class NormalizationError(ValueError):
    def __init__(self, field: str, code: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.code = code
        self.message = message


def parse_decimal(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float, Decimal)):
        candidate = str(value)
    else:
        text = str(value).strip()
        if re.search(r"[A-Za-z]", text):
            raise NormalizationError(
                field,
                "INVALID_NUMBER",
                f"{field.replace('_', ' ').title()} contains a unit or text and requires review.",
            )
        candidate = re.sub(r"[^0-9,.\-]", "", text)
    if not candidate or candidate in {"-", ".", ","}:
        raise NormalizationError(field, "INVALID_NUMBER", f"{field.replace('_', ' ').title()} could not be parsed.")
    if "," in candidate and "." in candidate:
        if candidate.rfind(",") > candidate.rfind("."):
            candidate = candidate.replace(".", "").replace(",", ".")
        else:
            candidate = candidate.replace(",", "")
    elif "," in candidate:
        parts = candidate.split(",")
        candidate = "".join(parts) if len(parts[-1]) == 3 and len(parts) > 1 else candidate.replace(",", ".")
    try:
        return format(Decimal(candidate), "f")
    except InvalidOperation as exc:
        raise NormalizationError(field, "INVALID_NUMBER", f"{field.replace('_', ' ').title()} could not be parsed.") from exc


def parse_date(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError as exc:
        raise NormalizationError(field, "INVALID_DATE", f"{field.upper()} is not a recognized date.") from exc


def normalize_record(raw: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source_column, canonical_field in mapping.items():
        value = raw.get(source_column)
        if value is None:
            continue
        if canonical_field in DECIMAL_FIELDS:
            result[canonical_field] = parse_decimal(value, canonical_field)
        elif canonical_field in DATE_FIELDS:
            result[canonical_field] = parse_date(value, canonical_field)
        elif isinstance(value, str):
            cleaned = " ".join(value.strip().split())
            result[canonical_field] = cleaned.upper() if canonical_field in UPPER_FIELDS else cleaned
        else:
            result[canonical_field] = str(value).strip()
    return result


def normalize_value(value: Any, canonical_field: str) -> Any:
    if canonical_field in DECIMAL_FIELDS:
        return parse_decimal(value, canonical_field)
    if canonical_field in DATE_FIELDS:
        return parse_date(value, canonical_field)
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    return cleaned.upper() if canonical_field in UPPER_FIELDS else cleaned
