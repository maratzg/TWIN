import io

from openpyxl import Workbook

from app.input_engine.parsers import TabularParser


def test_csv_parsing_and_header_detection() -> None:
    content = b"Shipment export\nCUST;BL_NO;GWT\nIKEA;BL-1;1200\nABB;BL-2;900\n"
    parsed = TabularParser().parse("shipments.csv", content)
    assert parsed.header_row == 2
    assert parsed.columns == ["CUST", "BL_NO", "GWT"]
    assert parsed.rows[0]["CUST"] == "IKEA"


def test_excel_parsing_selects_populated_sheet() -> None:
    workbook = Workbook()
    workbook.active.title = "Notes"
    workbook.active.append(["Read me"])
    data = workbook.create_sheet("Data")
    data.append(["Monthly export"])
    data.append(["CLIENT_NAME", "CNTR_NO", "SALES"])
    data.append(["IKEA", "MSCU1234567", 1000])
    buffer = io.BytesIO()
    workbook.save(buffer)

    parsed = TabularParser().parse("shipments.xlsx", buffer.getvalue())
    assert parsed.selected_sheet == "Data"
    assert parsed.header_row == 2
    assert parsed.rows[0]["SALES"] == 1000

