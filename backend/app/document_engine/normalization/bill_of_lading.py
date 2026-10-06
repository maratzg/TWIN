import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y")
IDENTIFIER_FIELDS = {
    "bill_of_lading_number",
    "shipment_reference",
    "booking_reference",
    "shipper_registration_number",
    "shipper_vat_number",
    "consignee_registration_number",
    "consignee_vat_number",
    "vessel_imo_number",
    "voyage_number",
    "seal_number",
}


def normalize_bill_of_lading_value(field: str, value: str | None):
    if value is None:
        return None
    clean = " ".join(str(value).replace("\u00a0", " ").split()).strip()
    if not clean or clean.casefold() in {"-", "—", "n/a", "na", "unknown"}:
        return None
    if field == "issue_date":
        return _date(clean)
    if field == "container_number":
        candidate = re.sub(r"[^A-Za-z0-9]", "", clean).upper()
        return candidate if re.fullmatch(r"[A-Z]{4}\d{7}", candidate) else None
    if field == "container_size_type":
        return normalize_container_size_type(clean)
    if field in {"gross_weight", "total_gross_weight"}:
        return normalize_weight_kg(clean)
    if field in {"package_count", "total_packages"}:
        candidate = re.sub(r"[\s,.]", "", clean)
        return int(candidate) if candidate.isdigit() else None
    if field == "measurement":
        return _decimal_measurement(clean)
    if field == "measurement_unit":
        upper = re.sub(r"[^A-Z0-9]", "", clean.upper())
        return "CBM" if upper in {"CBM", "M3"} else upper or None
    if field in {"port_of_loading", "port_of_discharge", "place_of_receipt", "place_of_delivery"}:
        return clean.upper()
    if field == "vessel_imo_number":
        digits = re.sub(r"\D", "", clean)
        return digits if len(digits) == 7 else None
    if field in IDENTIFIER_FIELDS:
        return clean.upper() if field != "seal_number" else re.sub(r"\s", "", clean).upper()
    return clean


def normalize_container_size_type(value: str) -> str | None:
    upper = value.upper().replace("’", "'")
    compact = re.sub(r"[\s'\-/]", "", upper)
    aliases = {
        "20GP": "20GP",
        "20DV": "20GP",
        "20STD": "20GP",
        "20STANDARD": "20GP",
        "20": "20",
        "40GP": "40GP",
        "40DV": "40GP",
        "40STD": "40GP",
        "40STANDARD": "40GP",
        "40HC": "40HC",
        "40HQ": "40HC",
        "40HIGHCUBE": "40HC",
        "45HC": "45HC",
        "45HQ": "45HC",
        "45HIGHCUBE": "45HC",
        "40": "40",
        "45": "45",
    }
    return aliases.get(compact)


def normalize_weight_kg(value: str) -> str | None:
    candidate = value.upper().replace("−", "-")
    unit_match = re.search(r"\b(KGS?|KILOGRAMS?|TONNES?|TONS?|T)\b", candidate)
    unit = unit_match.group(1) if unit_match else "KG"
    candidate = re.sub(r"\b(KGS?|KILOGRAMS?|TONNES?|TONS?|T)\b", "", candidate).strip()
    candidate = candidate.replace("'", "").replace(" ", "")
    if not re.fullmatch(r"[-+]?\d[\d.,]*", candidate):
        return None
    if "," in candidate and "." in candidate:
        decimal_sep = "," if candidate.rfind(",") > candidate.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        candidate = candidate.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in candidate:
        tail = candidate.rsplit(",", 1)[1]
        candidate = candidate.replace(",", ".") if len(tail) in {1, 2} else candidate.replace(",", "")
    elif "." in candidate:
        tail = candidate.rsplit(".", 1)[1]
        if len(tail) == 3:
            candidate = candidate.replace(".", "")
    try:
        amount = Decimal(candidate)
    except InvalidOperation:
        return None
    if unit in {"T", "TON", "TONS", "TONNE", "TONNES"}:
        amount *= Decimal("1000")
    return str(amount.quantize(Decimal("0.001")))


def derive_teu(size_type: str | None) -> str | None:
    if size_type == "20GP":
        return "1.00"
    if size_type in {"40GP", "40HC", "45HC"}:
        return "2.00"
    return None


def _date(value: str) -> str | None:
    candidate = re.sub(r"(?i)^(?:date(?:\s+of\s+issue)?|issued)\s*[:\-]?\s*", "", value).strip()
    for format_string in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, format_string).date().isoformat()
        except ValueError:
            continue
    return None


def _decimal_measurement(value: str) -> str | None:
    candidate = re.sub(r"(?i)\b(?:CBM|M3|M³)\b", "", value).replace(" ", "").strip()
    if not re.fullmatch(r"\d[\d.,]*", candidate):
        return None
    if "," in candidate and "." not in candidate:
        candidate = candidate.replace(",", ".")
    elif "," in candidate and "." in candidate:
        candidate = candidate.replace(",", "")
    try:
        return str(Decimal(candidate).quantize(Decimal("0.001")))
    except InvalidOperation:
        return None
