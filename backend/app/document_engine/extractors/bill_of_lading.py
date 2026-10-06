import re

from app.document_engine.normalization.bill_of_lading import normalize_bill_of_lading_value
from app.document_engine.types import ExtractedCandidate, ExtractedPage


FIELD_RULES: dict[str, tuple[list[str], float]] = {
    "bill_of_lading_number": ([r"B/?L\s*(?:No\.?|Number|#)", r"Bill\s+of\s+Lading\s*(?:No\.?|Number|#)"], 0.99),
    "issue_date": ([r"Issue\s*Date", r"Date\s+of\s+Issue", r"Issued"], 0.94),
    "shipper_name": ([r"Shipper"], 0.96),
    "shipper_registration_number": ([r"Shipper\s*(?:Registration|Reg\.?)\s*(?:No\.?|Number)?"], 0.94),
    "shipper_vat_number": ([r"Shipper\s*VAT(?:\s*(?:No\.?|Number|ID))?"], 0.96),
    "consignee_name": ([r"Consignee"], 0.96),
    "consignee_registration_number": ([r"Consignee\s*(?:Registration|Reg\.?)\s*(?:No\.?|Number)?"], 0.94),
    "consignee_vat_number": ([r"Consignee\s*VAT(?:\s*(?:No\.?|Number|ID))?"], 0.96),
    "notify_party_name": ([r"Notify\s*Party"], 0.92),
    "carrier_name": ([r"Carrier", r"Shipping\s*Line"], 0.91),
    "vessel_name": ([r"Vessel(?:\s*Name)?", r"Ocean\s*Vessel"], 0.97),
    "vessel_imo_number": ([r"IMO(?:\s*(?:No\.?|Number))?"], 0.97),
    "voyage_number": ([r"Voyage(?:\s*(?:No\.?|Number))?", r"Voy\.\s*No\.?"], 0.97),
    "port_of_loading": ([r"Port\s+of\s+Loading", r"POL"], 0.97),
    "port_of_discharge": ([r"Port\s+of\s+Discharge", r"POD"], 0.97),
    "place_of_receipt": ([r"Place\s+of\s+Receipt"], 0.90),
    "place_of_delivery": ([r"Place\s+of\s+Delivery"], 0.90),
    "shipment_reference": ([r"Shipment\s*(?:Reference|Ref\.?)"], 0.90),
    "booking_reference": ([r"Booking\s*(?:Reference|Ref\.?|No\.?|Number)"], 0.92),
    "description_of_goods": ([r"Description\s+of\s+Goods", r"Goods\s+Description"], 0.90),
    "total_packages": ([r"Total\s+(?:No\.\s+of\s+)?Packages", r"Packages\s+Total"], 0.93),
    "total_gross_weight": ([r"Total\s+Gross\s+Weight", r"Gross\s+Weight\s+Total"], 0.96),
    "measurement": ([r"Measurement", r"Total\s+Volume"], 0.91),
}

CONTAINER_FIELDS = (
    "container_number",
    "container_size_type",
    "seal_number",
    "package_count",
    "package_type",
    "gross_weight",
)


class BillOfLadingExtractor:
    document_type = "BILL_OF_LADING"
    version = "bill-of-lading-rules-v1"

    def extract(self, pages: list[ExtractedPage]) -> list[ExtractedCandidate]:
        candidates: list[ExtractedCandidate] = []
        for field, (labels, confidence) in FIELD_RULES.items():
            match = self._find(pages, labels)
            if match is None:
                continue
            raw_value, page_number, evidence = match
            candidates.append(self._candidate(field, raw_value, confidence, page_number, evidence))
            if field == "measurement":
                unit = "CBM" if re.search(r"(?i)\b(?:CBM|M3|M³)\b", raw_value) else None
                if unit:
                    candidates.append(self._candidate("measurement_unit", unit, confidence, page_number, evidence))
        candidates.extend(self._extract_containers(pages))
        return candidates

    def _extract_containers(self, pages: list[ExtractedPage]) -> list[ExtractedCandidate]:
        result: list[ExtractedCandidate] = []
        seen: set[tuple[int, str]] = set()
        for page in pages:
            lines = [" ".join(line.split()) for line in page.text.splitlines() if line.strip()]
            for line_index, line in enumerate(lines):
                number_match = re.search(r"\b([A-Z]{4}(?:[\s-]*\d){7})\b", line, re.I)
                if not number_match:
                    continue
                raw_number = number_match.group(1)
                key = (page.page_number, re.sub(r"\W", "", raw_number).upper())
                if key in seen:
                    continue
                seen.add(key)
                parts = [part.strip() for part in re.split(r"\s*[|;]\s*", line)]
                values: dict[str, str | None] = {field: None for field in CONTAINER_FIELDS}
                values["container_number"] = raw_number
                if len(parts) >= 6:
                    number_position = next((index for index, part in enumerate(parts) if raw_number in part), 0)
                    row = parts[number_position:number_position + 6]
                    if len(row) == 6:
                        values = dict(zip(CONTAINER_FIELDS, row, strict=True))
                else:
                    window = " | ".join(lines[line_index:line_index + 7])
                    patterns = {
                        "container_size_type": r"(?i)(?:Size\s*/?\s*Type|Type)\s*[:#-]\s*([^|;]+)",
                        "seal_number": r"(?i)Seal(?:\s*(?:No\.?|Number))?\s*[:#-]\s*([^|;]+)",
                        "package_count": r"(?i)(?:Packages?|Pkgs?)\s*[:#-]\s*(\d[\d\s,.]*)",
                        "package_type": r"(?i)Package\s*Type\s*[:#-]\s*([^|;]+)",
                        "gross_weight": r"(?i)Gross\s*Weight\s*[:#-]\s*([\d\s.,]+\s*(?:KGS?|KG|T|TONNES?))",
                    }
                    for field, pattern in patterns.items():
                        matched = re.search(pattern, window)
                        values[field] = matched.group(1).strip() if matched else None
                group_index = len({candidate.group_index for candidate in result if candidate.group_type == "container"})
                for field, raw_value in values.items():
                    if raw_value is None or not raw_value.strip():
                        continue
                    result.append(
                        self._candidate(
                            field,
                            raw_value,
                            0.98 if field == "container_number" else 0.94,
                            page.page_number,
                            line[:1000],
                            group_type="container",
                            group_index=group_index,
                        )
                    )
        return result

    @staticmethod
    def _find(pages: list[ExtractedPage], labels: list[str]) -> tuple[str, int, str] | None:
        for page in pages:
            lines = [" ".join(line.split()) for line in page.text.splitlines() if line.strip()]
            for index, evidence in enumerate(lines):
                for label in labels:
                    matched = re.match(rf"^\s*(?:{label})\s*[:#\-]\s*(.+?)\s*$", evidence, re.I)
                    if matched and matched.group(1).strip():
                        return matched.group(1).strip(), page.page_number, evidence[:1000]
                    if re.fullmatch(rf"\s*(?:{label})\s*[:#\-]?\s*", evidence, re.I) and index + 1 < len(lines):
                        value = lines[index + 1].strip()
                        if value:
                            return value, page.page_number, f"{evidence}: {value}"[:1000]
        return None

    @staticmethod
    def _candidate(
        field: str,
        raw_value: str,
        confidence: float,
        page_number: int,
        evidence: str,
        *,
        group_type: str = "document",
        group_index: int = 0,
    ) -> ExtractedCandidate:
        return ExtractedCandidate(
            field_name=field,
            raw_value=raw_value,
            normalized_value=normalize_bill_of_lading_value(field, raw_value),
            confidence=confidence,
            extraction_method="labeled_field" if group_type == "document" else "container_row",
            page_number=page_number,
            evidence=evidence,
            group_type=group_type,
            group_index=group_index,
        )
