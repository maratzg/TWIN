from decimal import Decimal, InvalidOperation

from app.document_engine.types import ValidationFinding
from app.document_engine.validation.iso6346 import iso6346_status


REQUIRED_CREATION_FIELDS = {
    "bill_of_lading_number",
    "vessel_name",
    "voyage_number",
    "port_of_loading",
    "port_of_discharge",
}


def validate_bill_of_lading_candidates(
    values: dict[str, object],
    containers: list[dict[str, object]],
    *,
    candidate_statuses: list[tuple[str, str, int, str]],
    duplicate: bool,
    shipment_resolution: str,
    canonical_conflicts: list[str],
    weight_tolerance: Decimal,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if not values.get("bill_of_lading_number"):
        findings.append(ValidationFinding("bill_of_lading_number", "ERROR", "MISSING_BILL_OF_LADING_NUMBER", "Bill of Lading number is required."))

    for field, group_type, group_index, status in candidate_statuses:
        display = field.replace("_", " ").title()
        if status == "error":
            findings.append(ValidationFinding(field, "ERROR", "INVALID_FIELD_VALUE", f"{display} could not be normalized safely.", group_type, group_index))
        elif status == "review":
            findings.append(ValidationFinding(field, "WARNING", "LOW_CONFIDENCE_FIELD", f"{display} needs human confirmation.", group_type, group_index))

    if duplicate:
        findings.append(ValidationFinding("bill_of_lading_number", "ERROR", "DUPLICATE_BILL_OF_LADING", "A canonical Bill of Lading with this normalized number already exists."))

    if bool(values.get("vessel_name")) != bool(values.get("voyage_number")):
        findings.append(ValidationFinding(None, "WARNING", "VESSEL_VOYAGE_INCOMPLETE", "Vessel and voyage should be reviewed together when either value is present."))

    if shipment_resolution == "unresolved":
        missing = [field for field in sorted(REQUIRED_CREATION_FIELDS) if not values.get(field)]
        if not containers:
            missing.append("container")
        if missing:
            findings.append(ValidationFinding(None, "ERROR", "SHIPMENT_UNRESOLVED", f"No shipment matched and a new shipment cannot be created until these fields are resolved: {', '.join(missing)}."))
        else:
            findings.append(ValidationFinding(None, "WARNING", "NEW_SHIPMENT_CANDIDATE", "No canonical shipment matched; approval will allow a new shipment and its logistics relationships to be created."))

    for conflict in canonical_conflicts:
        findings.append(ValidationFinding(None, "ERROR", "CANONICAL_CONFLICT", conflict))

    loading = str(values.get("port_of_loading") or "").strip().casefold()
    discharge = str(values.get("port_of_discharge") or "").strip().casefold()
    if loading and discharge and loading == discharge:
        findings.append(ValidationFinding("port_of_discharge", "WARNING", "SAME_LOADING_AND_DISCHARGE_PORT", "Port of loading and port of discharge are the same."))

    seen: set[str] = set()
    container_weights: list[Decimal] = []
    for index, container in enumerate(containers):
        number = str(container.get("container_number") or "")
        status = iso6346_status(number)
        if status == "structurally_invalid":
            findings.append(ValidationFinding("container_number", "ERROR", "INVALID_CONTAINER_FORMAT", "Container number must use the ISO 6346 owner/category/serial/check-digit structure.", "container", index))
        elif status == "check_digit_invalid":
            findings.append(ValidationFinding("container_number", "ERROR", "INVALID_CONTAINER_CHECK_DIGIT", "Container number has an invalid ISO 6346 check digit; it was not altered.", "container", index))
        if number in seen:
            findings.append(ValidationFinding("container_number", "ERROR", "DUPLICATE_CONTAINER_OCCURRENCE", "The same container appears more than once in this Bill of Lading.", "container", index))
        seen.add(number)
        if container.get("container_size_type") in {"20", "40", "45"}:
            findings.append(ValidationFinding("container_size_type", "WARNING", "AMBIGUOUS_CONTAINER_TYPE", "Only the container length is known, so equipment type and TEU were not inferred.", "container", index))

        weight = _decimal(container.get("gross_weight"))
        if container.get("gross_weight") is not None and weight is None:
            findings.append(ValidationFinding("gross_weight", "ERROR", "INVALID_WEIGHT", "Container gross weight must be numeric.", "container", index))
        elif weight is not None:
            if weight < 0:
                findings.append(ValidationFinding("gross_weight", "ERROR", "NEGATIVE_WEIGHT", "Container gross weight cannot be negative.", "container", index))
            else:
                container_weights.append(weight)

        packages = container.get("package_count")
        if packages is not None:
            try:
                if int(str(packages)) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                findings.append(ValidationFinding("package_count", "ERROR", "INVALID_PACKAGE_COUNT", "Package count must be a non-negative whole number.", "container", index))

    total_weight = _decimal(values.get("total_gross_weight"))
    if total_weight is not None and total_weight < 0:
        findings.append(ValidationFinding("total_gross_weight", "ERROR", "NEGATIVE_WEIGHT", "Total gross weight cannot be negative."))
    if total_weight is not None and container_weights and len(container_weights) == len(containers):
        if abs(sum(container_weights, Decimal("0")) - total_weight) > weight_tolerance:
            findings.append(ValidationFinding("total_gross_weight", "ERROR", "TOTAL_WEIGHT_MISMATCH", "The stated total gross weight differs from the sum of container gross weights beyond the configured tolerance."))
    return findings


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except InvalidOperation:
        return None
