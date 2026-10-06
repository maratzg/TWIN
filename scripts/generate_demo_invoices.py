"""Generate deterministic, text-based invoice PDFs for the Milestone 3A demo."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "demo-data" / "invoices"


def money(value: str, currency: str = "EUR") -> str:
    return f"{value} {currency}"


def build_invoice(filename: str, data: dict[str, str], note: str) -> None:
    output = OUTPUT_DIR / filename
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Invoice {data['Invoice Number']}",
        author="TWIN demo data generator",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Right", parent=styles["BodyText"], alignment=TA_RIGHT))
    styles.add(
        ParagraphStyle(
            name="Eyebrow",
            parent=styles["BodyText"],
            textColor=colors.HexColor("#64748B"),
            fontSize=8,
            leading=10,
            spaceAfter=4,
        )
    )
    story = [
        Table(
            [[
                Paragraph("<b>TWIN DEMO</b><br/><font color='#64748B'>Document intelligence fixture</font>", styles["BodyText"]),
                Paragraph("<font size='24'><b>INVOICE</b></font>", styles["Right"]),
            ]],
            colWidths=[100 * mm, 70 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
        ),
        Spacer(1, 9 * mm),
    ]

    metadata_rows = [
        ["Invoice Number", data["Invoice Number"], "Invoice Date", data["Invoice Date"]],
        ["Payment Reference", data.get("Payment Reference", "-"), "Due Date", data.get("Due Date", "-")],
        ["Purchase Order", data.get("Purchase Order", "-"), "Currency", data.get("Currency", "-")],
    ]
    metadata = Table(metadata_rows, colWidths=[33 * mm, 52 * mm, 29 * mm, 56 * mm])
    metadata.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748B")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#64748B")),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([metadata, Spacer(1, 9 * mm)])

    parties = Table(
        [
            [Paragraph("SUPPLIER", styles["Eyebrow"]), Paragraph("CUSTOMER", styles["Eyebrow"])],
            [Paragraph(f"<b>{data['Supplier']}</b>", styles["BodyText"]), Paragraph(f"<b>{data['Customer']}</b>", styles["BodyText"])],
            [f"Supplier Registration: {data.get('Supplier Registration', '-')}", f"Customer Registration: {data.get('Customer Registration', '-')}"] ,
            [f"Supplier VAT: {data.get('Supplier VAT', '-')}", f"Customer VAT: {data.get('Customer VAT', '-')}"] ,
        ],
        colWidths=[85 * mm, 85 * mm],
    )
    parties.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#94A3B8")),
                ("LINEBEFORE", (1, 0), (1, -1), 0.7, colors.HexColor("#94A3B8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([parties, Spacer(1, 10 * mm)])

    items = Table(
        [
            ["DESCRIPTION", "QTY", "UNIT PRICE", "AMOUNT"],
            [data.get("Description", "Freight forwarding services"), "1", data["Subtotal"], data["Subtotal"]],
        ],
        colWidths=[90 * mm, 18 * mm, 31 * mm, 31 * mm],
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([items, Spacer(1, 6 * mm)])

    totals = Table(
        [
            ["Subtotal", money(data["Subtotal"], data.get("Currency", "EUR"))],
            ["VAT Rate", data.get("VAT Rate", "21%")],
            ["VAT Amount", money(data["VAT Amount"], data.get("Currency", "EUR"))],
            ["Total Amount", money(data["Total Amount"], data.get("Currency", "EUR"))],
        ],
        colWidths=[42 * mm, 40 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#0F172A")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([totals, Spacer(1, 10 * mm)])

    references = [
        ("Shipment Reference", data.get("Shipment Reference")),
        ("Booking Reference", data.get("Booking Reference")),
        ("B/L Reference", data.get("B/L Reference")),
        ("IBAN", data.get("IBAN")),
    ]
    for label, value in references:
        if value:
            story.append(Paragraph(f"<b>{label}:</b> {value}", styles["BodyText"]))
            story.append(Spacer(1, 2 * mm))
    story.extend(
        [
            Spacer(1, 5 * mm),
            Paragraph(f"<b>Fixture note:</b> {note}", styles["BodyText"]),
            Spacer(1, 5 * mm),
            Paragraph("Generated for local TWIN development only. No real financial data.", styles["Eyebrow"]),
        ]
    )
    document.build(story)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = {
        "Invoice Number": "BFS-2026-0917",
        "Invoice Date": "2026-09-17",
        "Due Date": "2026-10-17",
        "Supplier": "Baltic Freight Services SIA",
        "Supplier Registration": "40203555111",
        "Supplier VAT": "LV40203555111",
        "Customer": "Demo Logistics SIA",
        "Customer Registration": "40000000000",
        "Customer VAT": "LV40000000000",
        "Currency": "EUR",
        "Subtotal": "1000.00",
        "VAT Rate": "21%",
        "VAT Amount": "210.00",
        "Total Amount": "1210.00",
        "Payment Reference": "PAY-BFS-0917",
        "Purchase Order": "PO-2026-441",
        "Shipment Reference": "SHP-2026-0091",
        "Booking Reference": "BOOK-77821",
        "B/L Reference": "BL-RIX-260917",
        "IBAN": "LV80BANK0000123456789",
        "Description": "Ocean freight and terminal handling",
    }
    build_invoice("invoice-a-clean.pdf", base, "Complete high-confidence invoice with operational references.")

    european = {
        **base,
        "Invoice Number": "NSE-2026-1042",
        "Invoice Date": "18.09.2026",
        "Due Date": "18.10.2026",
        "Supplier": "Nordic Shipping Europe OÜ",
        "Supplier Registration": "14999888",
        "Supplier VAT": "EE14999888",
        "Subtotal": "1.250,00",
        "VAT Amount": "262,50",
        "Total Amount": "1.512,50",
        "Payment Reference": "NSE-1042",
        "Shipment Reference": "SHP-2026-0092",
        "Booking Reference": "BOOK-77822",
        "B/L Reference": "BL-TLL-260918",
    }
    build_invoice("invoice-b-european-format.pdf", european, "European date and decimal separators exercise normalization.")

    ambiguous = {
        **base,
        "Invoice Number": "AMB-77",
        "Invoice Date": "09/10/2026",
        "Due Date": "10/09/2026",
        "Supplier": "Harbor Services",
        "Supplier Registration": "-",
        "Supplier VAT": "-",
        "Currency": "EUROS",
        "Subtotal": "850.00",
        "VAT Amount": "178.50",
        "Total Amount": "1028.50",
        "Shipment Reference": "UNKNOWN-SHIPMENT",
        "Booking Reference": "",
        "B/L Reference": "",
    }
    build_invoice("invoice-c-ambiguous.pdf", ambiguous, "Ambiguous identifiers and currency must remain reviewable, never silently committed.")

    mismatch = {
        **base,
        "Invoice Number": "MISMATCH-2026-18",
        "Subtotal": "900.00",
        "VAT Amount": "189.00",
        "Total Amount": "1199.00",
        "Payment Reference": "MISMATCH-18",
    }
    build_invoice("invoice-d-arithmetic-mismatch.pdf", mismatch, "Subtotal plus VAT intentionally differs from total.")

    duplicate = {**base, "Payment Reference": "PAY-BFS-0917-DUP"}
    build_invoice("invoice-e-duplicate.pdf", duplicate, "Same canonical identity as invoice A for duplicate detection.")


if __name__ == "__main__":
    main()

