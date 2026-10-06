import re

from app.document_engine.types import ClassificationResult, ExtractedPage


class DocumentClassifier:
    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold

    def classify(self, pages: list[ExtractedPage]) -> ClassificationResult:
        text = "\n".join(page.text for page in pages)
        invoice_checks = [
            ("invoice_heading", r"\binvoice\b", 0.45),
            ("invoice_number_label", r"invoice\s*(?:no\.?|number|#)", 0.25),
            ("total_label", r"(?im)^\s*(?:grand\s+)?total\s*[:\-]", 0.10),
            ("vat_signal", r"\bVAT\b|value\s+added\s+tax", 0.08),
            ("due_date_label", r"due\s+date", 0.06),
            ("party_labels", r"(?im)^\s*(?:supplier|customer|bill\s+to)\s*[:\-]", 0.06),
        ]
        bill_checks = [
            ("bill_of_lading_heading", r"(?im)^\s*(?:original\s+)?bill\s+of\s+lading\b", 0.40),
            ("bill_of_lading_number", r"(?i)(?:B/?L|bill\s+of\s+lading)\s*(?:no\.?|number|#)\s*[:#\-]", 0.18),
            ("shipper_consignee", r"(?is)\bshipper\b.*\bconsignee\b|\bconsignee\b.*\bshipper\b", 0.12),
            ("loading_discharge_ports", r"(?is)port\s+of\s+loading.*port\s+of\s+discharge|\bPOL\b.*\bPOD\b", 0.12),
            ("vessel_voyage", r"(?is)\bvessel\b.*\bvoyage\b|\bvoyage\b.*\bvessel\b", 0.08),
            ("container_and_seal", r"(?is)container\s*(?:no\.?|number).*(?:seal\s*(?:no\.?|number))", 0.06),
            ("cargo_signals", r"(?i)gross\s+weight|description\s+of\s+goods|packages", 0.04),
        ]
        invoice_signals = [name for name, pattern, _weight in invoice_checks if re.search(pattern, text, re.I)]
        bill_signals = [name for name, pattern, _weight in bill_checks if re.search(pattern, text, re.I)]
        invoice_score = min(0.99, sum(weight for name, _pattern, weight in invoice_checks if name in invoice_signals))
        bill_score = min(0.99, sum(weight for name, _pattern, weight in bill_checks if name in bill_signals))
        if bill_score >= self.threshold and bill_score > invoice_score:
            return ClassificationResult("BILL_OF_LADING", round(bill_score, 2), "keyword_rules_v2", bill_signals)
        if invoice_score >= self.threshold:
            return ClassificationResult("INVOICE", round(invoice_score, 2), "keyword_rules_v2", invoice_signals)
        score = max(invoice_score, bill_score)
        signals = invoice_signals if invoice_score >= bill_score else bill_signals
        return ClassificationResult("UNKNOWN", round(score, 2), "keyword_rules_v2", signals)
