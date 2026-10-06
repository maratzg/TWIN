import re

from app.document_engine.normalization import normalize_invoice_value
from app.document_engine.types import ExtractedCandidate, ExtractedPage


FIELD_RULES: dict[str, tuple[list[str], float]] = {
    "invoice_number": ([r"Invoice\s*(?:No\.?|Number|#)"], 0.99),
    "invoice_date": ([r"Invoice\s*Date", r"Date\s+of\s+Issue"], 0.98),
    "due_date": ([r"Due\s*Date", r"Payment\s+Due"], 0.97),
    "supplier_name": ([r"Supplier", r"Vendor", r"From"], 0.95),
    "supplier_registration_number": ([r"Supplier\s*(?:Registration|Reg\.?)(?:\s*(?:No\.?|Number))?"], 0.97),
    "supplier_vat_number": ([r"Supplier\s*VAT(?:\s*(?:No\.?|Number|ID))?"], 0.98),
    "customer_name": ([r"Customer", r"Bill\s*To"], 0.95),
    "customer_registration_number": ([r"Customer\s*(?:Registration|Reg\.?)(?:\s*(?:No\.?|Number))?"], 0.97),
    "customer_vat_number": ([r"Customer\s*VAT(?:\s*(?:No\.?|Number|ID))?"], 0.98),
    "currency": ([r"Currency"], 0.99),
    "subtotal": ([r"Subtotal", r"Net\s*Amount"], 0.99),
    "vat_amount": ([r"VAT(?:\s*Amount)?", r"Tax\s*Amount"], 0.98),
    "total_amount": ([r"(?:Grand\s*)?Total(?:\s*Amount)?", r"Amount\s*Due"], 0.99),
    "vat_rate": ([r"VAT\s*Rate", r"Tax\s*Rate"], 0.96),
    "payment_reference": ([r"Payment\s*Reference", r"Payment\s*Ref\.?"], 0.90),
    "purchase_order_reference": ([r"Purchase\s*Order", r"PO\s*(?:No\.?|Number|#)"], 0.88),
    "shipment_reference": ([r"Shipment\s*Reference", r"Shipment\s*Ref\.?"], 0.78),
    "booking_reference": ([r"Booking\s*Reference", r"Booking\s*Ref\.?"], 0.78),
    "bill_of_lading_reference": ([r"B/?L\s*Reference", r"Bill\s*of\s*Lading"], 0.78),
    "bank_details": ([r"IBAN", r"Bank\s*Account"], 0.84),
}


class InvoiceExtractor:
    document_type = "INVOICE"
    version = "invoice-rules-v1"

    def extract(self, pages: list[ExtractedPage]) -> list[ExtractedCandidate]:
        candidates: list[ExtractedCandidate] = []
        for field, (labels, confidence) in FIELD_RULES.items():
            match = self._find(pages, labels, field)
            if match is None:
                continue
            raw_value, page_number, evidence = match
            candidates.append(
                ExtractedCandidate(
                    field_name=field,
                    raw_value=raw_value,
                    normalized_value=normalize_invoice_value(field, raw_value),
                    confidence=confidence,
                    extraction_method="labeled_field",
                    page_number=page_number,
                    evidence=evidence,
                )
            )
        return candidates

    @staticmethod
    def _find(
        pages: list[ExtractedPage], labels: list[str], field: str
    ) -> tuple[str, int, str] | None:
        for page in pages:
            lines = [" ".join(line.split()) for line in page.text.splitlines() if line.strip()]
            for index, evidence in enumerate(lines):
                for label in labels:
                    if field == "vat_amount" and re.search(r"(?i)VAT\s*Rate", evidence):
                        continue
                    pattern = rf"^\s*(?:{label})\s*[:#\-]\s*(.+?)\s*$"
                    matched = re.match(pattern, evidence, re.I)
                    if matched and matched.group(1).strip():
                        return matched.group(1).strip(), page.page_number, evidence[:1000]
                    # Layout-aware PDF extraction commonly places a table label and
                    # its value on adjacent text lines. Party columns are paired, so
                    # both values follow both labels.
                    if re.fullmatch(rf"\s*(?:{label})\s*[:#\-]?\s*", evidence, re.I):
                        offset = 2 if field in {"supplier_name", "customer_name"} else 1
                        if index + offset < len(lines):
                            value = lines[index + offset].strip()
                            if value:
                                return value, page.page_number, f"{evidence}: {value}"[:1000]
        return None
