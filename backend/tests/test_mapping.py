from app.input_engine.mapping import MappingService, normalize_header


def test_header_normalization() -> None:
    assert normalize_header("  Bill / of-Lading  ") == "BILL_OF_LADING"
    assert normalize_header("client.name") == "CLIENT_NAME"


def test_known_alias_matching() -> None:
    proposal = MappingService().propose("CNTR_NO")
    assert proposal.canonical_field == "container_number"
    assert proposal.mapping_method == "known_alias"
    assert proposal.confidence == 0.99


def test_company_mapping_has_priority() -> None:
    proposal = MappingService().propose("VSL", {"VSL": "shipment_reference"})
    assert proposal.canonical_field == "shipment_reference"
    assert proposal.mapping_method == "company_confirmed"
    assert proposal.confidence == 1.0


def test_ambiguous_reference_is_not_guessed() -> None:
    proposal = MappingService().propose("REF")
    assert proposal.canonical_field is None
    assert proposal.mapping_method == "unresolved_ambiguous"

