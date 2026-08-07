"""Generate shop order invoice / receipt PDFs."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import Settings, get_settings
from .database import ShopOrder, ShopOrderItem


def _money(cents: int, currency: str = "EUR") -> str:
    return f"{cents / 100:.2f} {currency}"


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def invoice_filename(order: ShopOrder) -> str:
    return f"Rechnung-{order.order_number}.pdf"


def invoice_number(order: ShopOrder) -> str:
    return f"RE-{order.order_number}"


def build_invoice_pdf(
    order: ShopOrder,
    items: list[ShopOrderItem],
    *,
    settings: Optional[Settings] = None,
) -> bytes:
    settings = settings or get_settings()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Rechnung {invoice_number(order)}",
        author=settings.shop_company_name or settings.shop_brand_name,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=6,
        textColor=colors.HexColor("#0b1210"),
    )
    meta_style = ParagraphStyle("InvoiceMeta", parent=styles["Normal"], fontSize=9, leading=12)
    body_style = ParagraphStyle("InvoiceBody", parent=styles["Normal"], fontSize=10, leading=13)
    small_style = ParagraphStyle("InvoiceSmall", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#475569"))

    brand = settings.shop_brand_name or "FuckCo2"
    company = settings.shop_company_name or brand
    contact = settings.shop_contact or ""
    issued = (order.paid_at or order.created_at)
    issued_label = issued.strftime("%d.%m.%Y") if issued else "—"

    seller_lines = [
        f"<b>{_escape(company)}</b>",
        f"Marke: {_escape(brand)}",
    ]
    if contact:
        seller_lines.append(f"E-Mail: {_escape(contact)}")
    if settings.shop_bank_holder:
        seller_lines.append(f"Kontoinhaber: {_escape(settings.shop_bank_holder)}")

    buyer_lines = [f"<b>{_escape(order.customer_name)}</b>"]
    if order.company:
        buyer_lines.append(_escape(order.company))
    buyer_lines.append(_escape(order.address_line1))
    if order.address_line2:
        buyer_lines.append(_escape(order.address_line2))
    buyer_lines.append(_escape(f"{order.postal_code} {order.city}"))
    buyer_lines.append(_escape(order.country))
    buyer_lines.append(f"E-Mail: {_escape(order.customer_email)}")

    story = [
        Paragraph("Rechnung", title_style),
        Paragraph(
            f"Rechnungsnummer: <b>{_escape(invoice_number(order))}</b><br/>"
            f"Bestellnummer: {_escape(order.order_number)}<br/>"
            f"Datum: {issued_label}<br/>"
            f"Status: {_escape(order.status)} · Zahlung: {_escape(order.payment_method)}",
            meta_style,
        ),
        Spacer(1, 8 * mm),
        Table(
            [
                [
                    Paragraph("<b>Verkäufer</b><br/>" + "<br/>".join(seller_lines), body_style),
                    Paragraph("<b>Rechnungsempfänger</b><br/>" + "<br/>".join(buyer_lines), body_style),
                ]
            ],
            colWidths=[85 * mm, 85 * mm],
        ),
        Spacer(1, 8 * mm),
    ]

    table_data = [
        [
            Paragraph("<b>#</b>", meta_style),
            Paragraph("<b>Artikel</b>", meta_style),
            Paragraph("<b>Menge</b>", meta_style),
            Paragraph("<b>Einzelpreis</b>", meta_style),
            Paragraph("<b>Summe</b>", meta_style),
        ]
    ]
    for index, item in enumerate(items, start=1):
        table_data.append(
            [
                Paragraph(str(index), meta_style),
                Paragraph(_escape(item.product_name) + (f"<br/><font size='7'>SKU {_escape(item.product_sku)}</font>" if item.product_sku else ""), meta_style),
                Paragraph(str(item.quantity), meta_style),
                Paragraph(_money(item.unit_price_cents, order.currency), meta_style),
                Paragraph(_money(item.line_total_cents, order.currency), meta_style),
            ]
        )

    items_table = Table(table_data, colWidths=[10 * mm, 78 * mm, 18 * mm, 32 * mm, 32 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8efec")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    totals = [
        ["Zwischensumme (brutto)", _money(order.subtotal_cents, order.currency)],
        ["Versand", _money(order.shipping_cents, order.currency)],
        ["davon MwSt", _money(order.vat_cents, order.currency)],
        ["Gesamt", _money(order.total_cents, order.currency)],
    ]
    totals_table = Table(totals, colWidths=[120 * mm, 50 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#0b1210")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))

    if order.payment_method == "invoice":
        payment_note = (
            "<b>Zahlungsinformationen</b><br/>"
            "Bitte überweisen Sie den offenen Betrag mit der Bestellnummer als Verwendungszweck.<br/>"
            f"Empfänger: {_escape(settings.shop_bank_holder or company)}<br/>"
            f"IBAN: {_escape(settings.shop_bank_iban or '—')}<br/>"
            f"BIC: {_escape(settings.shop_bank_bic or '—')}<br/>"
            f"Bank: {_escape(settings.shop_bank_name or '—')}<br/>"
            f"Verwendungszweck: {_escape(order.order_number)}"
        )
    elif order.status in {"paid", "fulfilled"}:
        payment_note = "<b>Zahlungsstatus</b><br/>Bereits bezahlt (Stripe / Online-Zahlung)."
    else:
        payment_note = f"<b>Zahlungsstatus</b><br/>Aktueller Status: {_escape(order.status)}"

    story.append(Paragraph(payment_note, body_style))
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Preise inkl. MwSt. Dieses Dokument dient als Rechnung / Zahlungsbeleg für den FuckCo2-Shop der carbonauten GmbH.",
            small_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()
