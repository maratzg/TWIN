from app.input_engine.validation import validate_rows


MAPPING = {
    "BL": "bill_of_lading_number",
    "CONT": "container_number",
    "ETD": "etd",
    "ETA": "eta",
    "REV": "revenue",
    "CUR": "currency",
}


def test_invalid_numbers_and_dates_are_structured_errors() -> None:
    number_result = validate_rows([(2, {"BL": "BL-1", "REV": "many"})], MAPPING)[0]
    date_result = validate_rows([(3, {"BL": "BL-2", "ETD": "not-a-date"})], MAPPING)[0]
    assert number_result.disposition == "invalid"
    assert number_result.issues[0].code == "INVALID_NUMBER"
    assert date_result.disposition == "invalid"
    assert date_result.issues[0].code == "INVALID_DATE"


def test_duplicate_detection() -> None:
    rows = [(2, {"BL": "BL-1"}), (3, {"BL": "BL-1"})]
    results = validate_rows(rows, MAPPING)
    assert results[0].disposition == "ready"
    assert results[1].disposition == "invalid"
    assert results[1].issues[0].code == "DUPLICATE_IN_FILE"


def test_warning_routes_record_to_review() -> None:
    result = validate_rows([(2, {"BL": "BL-2", "CONT": "bad"})], MAPPING)[0]
    assert result.disposition == "review"
    assert result.issues[0].severity == "WARNING"

