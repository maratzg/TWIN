from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "demo-data" / "bills-of-lading"


FIXTURES = [
    {
        "filename": "bill-of-lading-a-clean-single-container.pdf",
        "number": "BL-RIX-260924-A",
        "issue_date": "2026-09-24",
        "shipper": "Baltic Timber Export SIA",
        "consignee": "North Sea Trading BV",
        "notify": "North Sea Trading BV",
        "carrier": "Twin Ocean Lines",
        "vessel": "EVER AURORA",
        "imo": "9811001",
        "voyage": "EA0924W",
        "pol": "RIGA",
        "pod": "ROTTERDAM",
        "receipt": "RIGA, LATVIA",
        "delivery": "ROTTERDAM, NETHERLANDS",
        "shipment": "SHP-BL-A-2026",
        "booking": "BOOK-A-77821",
        "goods": "Kiln-dried birch timber on pallets",
        "containers": [("MSKU1234565", "40HC", "SEAL8821", "120", "PALLETS", "18,400 KG")],
        "total_packages": "120",
        "total_weight": "18,400 KG",
        "measurement": "62.500 CBM",
    },
    {
        "filename": "bill-of-lading-b-multiple-containers.pdf",
        "number": "BL-RIX-260924-B",
        "issue_date": "2026-09-24",
        "shipper": "Baltic Timber Export SIA",
        "consignee": "Atlantic Wholesale GmbH",
        "notify": "Atlantic Wholesale GmbH",
        "carrier": "Twin Ocean Lines",
        "vessel": "EVER AURORA",
        "imo": "9811001",
        "voyage": "EA0924W",
        "pol": "RIGA",
        "pod": "HAMBURG",
        "receipt": "RIGA, LATVIA",
        "delivery": "HAMBURG, GERMANY",
        "shipment": "SHP-BL-B-2026",
        "booking": "BOOK-B-77822",
        "goods": "Mixed timber products in three shipper-loaded containers",
        "containers": [
            ("MSKU1234565", "40HC", "SEAL9001", "100", "BUNDLES", "10,000 KG"),
            ("TEMU7654328", "20GP", "SEAL9002", "80", "BUNDLES", "8,400 KG"),
            ("CMAU1112226", "40GP", "SEAL9003", "120", "BUNDLES", "12,000 KG"),
        ],
        "total_packages": "300",
        "total_weight": "30,400 KG",
        "measurement": "108.250 CBM",
    },
    {
        "filename": "bill-of-lading-c-european-format.pdf",
        "number": "EUR-RIX-260924-C",
        "issue_date": "24.09.2026",
        "shipper": "Rigas Koksne SIA",
        "consignee": "Nordhandel GmbH",
        "notify": "Nordhandel GmbH",
        "carrier": "Baltic Shortsea AS",
        "vessel": "BALTIC STAR",
        "imo": "9702202",
        "voyage": "BS-41E",
        "pol": "LV RIX",
        "pod": "DE HAM",
        "receipt": "JELGAVA",
        "delivery": "HAMBURG",
        "shipment": "SHP-BL-C-2026",
        "booking": "BUCH-C-4401",
        "goods": "Sawn softwood",
        "containers": [("OOLU4455664", "40 HQ", "EU-SEAL-41", "96", "PACKAGES", "18.400 KGS")],
        "total_packages": "96",
        "total_weight": "18.400 KGS",
        "measurement": "66,250 CBM",
        "separator": ";",
    },
    {
        "filename": "bill-of-lading-d-invalid-check-digit.pdf",
        "number": "BL-RIX-260924-D",
        "issue_date": "2026-09-24",
        "shipper": "Baltic Timber Export SIA",
        "consignee": "North Sea Trading BV",
        "notify": "North Sea Trading BV",
        "carrier": "Twin Ocean Lines",
        "vessel": "EVER AURORA",
        "imo": "9811001",
        "voyage": "EA0924W",
        "pol": "RIGA",
        "pod": "ROTTERDAM",
        "receipt": "RIGA",
        "delivery": "ROTTERDAM",
        "shipment": "SHP-BL-D-2026",
        "booking": "BOOK-D-77824",
        "goods": "Timber products",
        "containers": [("MSKU1234567", "40HC", "SEAL9021", "100", "BUNDLES", "18,400 KG")],
        "total_packages": "100",
        "total_weight": "18,400 KG",
        "measurement": "61.000 CBM",
    },
    {
        "filename": "bill-of-lading-e-conflicting-weight.pdf",
        "number": "BL-RIX-260924-E",
        "issue_date": "2026-09-24",
        "shipper": "Baltic Timber Export SIA",
        "consignee": "North Sea Trading BV",
        "notify": "North Sea Trading BV",
        "carrier": "Twin Ocean Lines",
        "vessel": "EVER AURORA",
        "imo": "9811001",
        "voyage": "EA0924W",
        "pol": "RIGA",
        "pod": "ROTTERDAM",
        "receipt": "RIGA",
        "delivery": "ROTTERDAM",
        "shipment": "SHP-BL-E-2026",
        "booking": "BOOK-E-77825",
        "goods": "Timber products",
        "containers": [
            ("HLCU3344559", "40HC", "SEAL9031", "90", "BUNDLES", "10,000 KG"),
            ("MAEU8765436", "20GP", "SEAL9032", "70", "BUNDLES", "8,400 KG"),
        ],
        "total_packages": "160",
        "total_weight": "20,000 KG",
        "measurement": "80.000 CBM",
    },
    {
        "filename": "bill-of-lading-f-ambiguous-partial.pdf",
        "number": "BL-RIX-260924-F",
        "issue_date": "2026-09-24",
        "shipper": "Baltic Export Desk",
        "consignee": "To order",
        "notify": "See instructions",
        "carrier": "Twin Ocean Lines",
        "vessel": "EVER AURORA",
        "imo": "9811001",
        "voyage": "-",
        "pol": "RIGA",
        "pod": "-",
        "receipt": "RIGA",
        "delivery": "TO ORDER",
        "shipment": "",
        "booking": "BOOK-F-77826",
        "goods": "General cargo - details to follow",
        "containers": [("GESU2468103", "40", "SEAL9041", "", "", "9,200 KG")],
        "total_packages": "",
        "total_weight": "9,200 KG",
        "measurement": "",
    },
    {
        "filename": "bill-of-lading-g-duplicate.pdf",
        "number": "BL-RIX-260924-A",
        "issue_date": "2026-09-24",
        "shipper": "Baltic Timber Export SIA",
        "consignee": "North Sea Trading BV",
        "notify": "North Sea Trading BV",
        "carrier": "Twin Ocean Lines",
        "vessel": "EVER AURORA",
        "imo": "9811001",
        "voyage": "EA0924W",
        "pol": "RIGA",
        "pod": "ROTTERDAM",
        "receipt": "RIGA",
        "delivery": "ROTTERDAM",
        "shipment": "SHP-BL-G-2026",
        "booking": "BOOK-G-77827",
        "goods": "Duplicate identity demonstration",
        "containers": [("MSKU1234565", "40HC", "SEAL9051", "120", "PALLETS", "18,400 KG")],
        "total_packages": "120",
        "total_weight": "18,400 KG",
        "measurement": "62.500 CBM",
    },
]


def build_bill(data: dict[str, object]) -> None:
    path = OUTPUT_DIR / str(data["filename"])
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor("#132A45"), alignment=TA_CENTER)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#52667A"), alignment=TA_CENTER, spaceAfter=8)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white, backColor=colors.HexColor("#1E5D79"), borderPadding=(4, 6), spaceBefore=7, spaceAfter=5)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8.2, leading=11, textColor=colors.HexColor("#1B2A39"))
    mono = ParagraphStyle("Mono", parent=body, fontName="Courier", fontSize=7.2, leading=10, leftIndent=3)
    footer = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.HexColor("#60758A"), alignment=TA_RIGHT)

    document = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm, topMargin=13 * mm, bottomMargin=13 * mm, title=f"Synthetic Bill of Lading {data['number']}")
    story = [
        Paragraph("ORIGINAL BILL OF LADING", title),
        Paragraph("Synthetic non-confidential demonstration document", subtitle),
        Table(
            [[Paragraph(f"<b>B/L No:</b> {data['number']}", body), Paragraph(f"<b>Issue Date:</b> {data['issue_date']}", body)],
             [Paragraph(f"<b>Carrier:</b> {data['carrier']}", body), Paragraph(f"<b>Booking Reference:</b> {data['booking'] or '-'}", body)],
             [Paragraph(f"<b>Shipment Reference:</b> {data['shipment'] or '-'}", body), Paragraph("<b>Freight:</b> PREPAID", body)]],
            colWidths=[88 * mm, 88 * mm],
            style=TableStyle([("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#9EB1C2")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#CED8E1")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7F9")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]),
        ),
        Paragraph("PARTIES", section),
        Table(
            [[Paragraph(f"<b>Shipper:</b><br/>{data['shipper']}", body), Paragraph(f"<b>Consignee:</b><br/>{data['consignee']}", body), Paragraph(f"<b>Notify Party:</b><br/>{data['notify']}", body)]],
            colWidths=[58.7 * mm] * 3,
            style=TableStyle([("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#9EB1C2")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#CED8E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]),
        ),
        Paragraph("TRANSPORT", section),
        Table(
            [[Paragraph(f"<b>Vessel:</b> {data['vessel']}", body), Paragraph(f"<b>IMO No:</b> {data['imo']}", body), Paragraph(f"<b>Voyage No:</b> {data['voyage']}", body)],
             [Paragraph(f"<b>Port of Loading:</b> {data['pol']}", body), Paragraph(f"<b>Port of Discharge:</b> {data['pod']}", body), Paragraph(f"<b>Place of Delivery:</b> {data['delivery']}", body)],
             [Paragraph(f"<b>Place of Receipt:</b> {data['receipt']}", body), "", ""]],
            colWidths=[58.7 * mm] * 3,
            style=TableStyle([("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#9EB1C2")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#CED8E1")), ("SPAN", (0, 2), (2, 2)), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]),
        ),
        Paragraph("CONTAINERS AND CARGO", section),
    ]
    separator = f" {data.get('separator', '|')} "
    header = separator.join(["Container No", "Size/Type", "Seal No", "Packages", "Package Type", "Gross Weight"])
    story.append(Paragraph(header, mono))
    for row in data["containers"]:
        story.append(Paragraph(separator.join(row), mono))
    story.extend([
        Spacer(1, 3 * mm),
        KeepTogether([
            Paragraph(f"<b>Description of Goods:</b> {data['goods']}", body),
            Paragraph(f"<b>Total Packages:</b> {data['total_packages'] or '-'}", body),
            Paragraph(f"<b>Total Gross Weight:</b> {data['total_weight']}", body),
            Paragraph(f"<b>Measurement:</b> {data['measurement'] or '-'}", body),
        ]),
        Spacer(1, 7 * mm),
        Paragraph("Received for carriage in apparent good order and condition. This synthetic document is for TWIN product testing only.", body),
        Spacer(1, 8 * mm),
        Table([[Paragraph("For the carrier", body), Paragraph("Authorized signature", footer)]], colWidths=[88 * mm, 88 * mm], style=TableStyle([("LINEABOVE", (1, 0), (1, 0), .5, colors.HexColor("#52667A")), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    ])
    document.build(story)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for fixture in FIXTURES:
        build_bill(fixture)
    print(f"Generated {len(FIXTURES)} synthetic Bills of Lading in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
