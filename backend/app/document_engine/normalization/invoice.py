import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y")
MONEY_FIELDS = {"subtotal", "vat_amount", "total_amount"}
IDENTIFIER_FIELDS = {
    "invoice_number",
    "supplier_registration_number",
    "supplier_vat_number",
    "customer_registration_number",
    "customer_vat_number",
    "payment_reference",
    "purchase_order_reference",
    "shipment_reference",
    "booking_reference",
    "bill_of_lading_reference",
    "bank_details",
}


def normalize_invoice_value(field: str, value: str | None):
    if value is None:
        return None
    clean = " ".join(str(value).replace("\u00a0", " ").split()).strip()
    if not clean or clean.casefold() in {"-", "—", "n/a", "na", "unknown"}:
        return None
    if field in {"invoice_date", "due_date"}:
        return _date(clean)
    if field in MONEY_FIELDS:
        return _decimal(clean, percentage=False)
    if field == "vat_rate":
        return _decimal(clean, percentage=True)
    if field == "currency":
        return _currency(clean)
    if field == "direction":
        value_lower = clean.lower()
        return value_lower if value_lower in {"payable", "receivable"} else None
    if field in {"supplier_vat_number", "customer_vat_number"}:
        return re.sub(r"[\s.\-]", "", clean).upper()
    if field in IDENTIFIER_FIELDS:
        return clean.strip()
    return clean


def _date(value: str) -> str | None:
    candidate = re.sub(r"(?i)^(?:date)\s*[:\-]?\s*", "", value).strip()
    for format_string in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, format_string).date().isoformat()
        except ValueError:
            continue
    return None


def _decimal(value: str, *, percentage: bool) -> str | None:
    candidate = value.replace("−", "-")
    candidate = re.sub(r"(?i)\b(?:EUR|USD|GBP|SEK|NOK|DKK|PLN)\b", "", candidate)
    candidate = candidate.replace("€", "").replace("$", "").replace("£", "")
    if percentage:
        candidate = candidate.replace("%", "")
    candidate = candidate.replace(" ", "").replace("'", "")
    if not re.fullmatch(r"[-+]?\d[\d.,]*", candidate):
        return None
    if "," in candidate and "." in candidate:
        decimal_separator = "," if candidate.rfind(",") > candidate.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        candidate = candidate.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in candidate:
        tail = candidate.rsplit(",", 1)[1]
        candidate = candidate.replace(",", ".") if len(tail) in {1, 2} else candidate.replace(",", "")
    elif "." in candidate and len(candidate.rsplit(".", 1)[1]) not in {1, 2}:
        candidate = candidate.replace(".", "")
    try:
        number = Decimal(candidate)
    except InvalidOperation:
        return None
    places = Decimal("0.01")
    return str(number.quantize(places))


def _currency(value: str) -> str | None:
    upper = value.upper().strip()
    symbols = {"€": "EUR", "$": "USD", "£": "GBP"}
    if upper in symbols:
        return symbols[upper]
    matches = re.findall(r"\b[A-Z]{3}\b", upper)
    return matches[0] if matches else None
