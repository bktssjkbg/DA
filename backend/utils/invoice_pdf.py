"""
Invoice PDF builder for CV. Dewi Aditya Maklon billing.
Uses ReportLab (already in requirements). Returns bytes.
"""
# ruff: noqa: E741
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)


def _fmt_idr(n):
    try:
        v = float(n or 0)
    except (ValueError, TypeError):
        v = 0
    return f"Rp {v:,.0f}".replace(',', '.')


def _fmt_date(d):
    if not d:
        return '-'
    s = str(d)[:10]
    try:
        dt = datetime.strptime(s, '%Y-%m-%d')
        bln = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des']
        return f"{dt.day} {bln[dt.month - 1]} {dt.year}"
    except ValueError:
        return s


def build_invoice_pdf(*, invoice: dict, client: dict, company: dict | None = None) -> bytes:
    """Generate a PDF invoice. Returns bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Invoice {invoice.get('invoice_number')}",
    )

    company = company or {}
    co_name = company.get('company_name') or 'CV. DEWI ADITYA OFFICIAL'
    co_addr = company.get('company_address') or 'Sragen, Jawa Tengah'
    co_tag = company.get('company_tagline') or 'Fashion Brand & Jasa Maklon Garment'

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#0f172a'),
        leading=26, alignment=2,
    )
    ParagraphStyle('h2', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#1f2937'))
    body = ParagraphStyle('body', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#1f2937'))
    body_muted = ParagraphStyle('muted', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#64748b'))
    body_right = ParagraphStyle('right', parent=body, alignment=2)

    elems = []

    # Header
    header_tbl = Table(
        [[
            Paragraph(f"<b>{co_name}</b><br/><font size=8 color='#64748b'>{co_tag}</font><br/><font size=8 color='#64748b'>{co_addr}</font>", body),
            Paragraph("INVOICE", title_style),
        ]],
        colWidths=[110 * mm, 60 * mm],
    )
    header_tbl.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elems.append(header_tbl)
    elems.append(Spacer(1, 6 * mm))
    elems.append(HRFlowable(width='100%', thickness=0.6, color=colors.HexColor('#cbd5e1')))
    elems.append(Spacer(1, 4 * mm))

    # Invoice meta + bill to
    meta_lines = [
        ['No. Invoice', invoice.get('invoice_number') or '-'],
        ['Tgl Terbit', _fmt_date(invoice.get('issue_date'))],
        ['Jatuh Tempo', _fmt_date(invoice.get('due_date'))],
        ['Term', (invoice.get('payment_terms') or 'net_30').replace('_', ' ').upper()],
        ['Status', (invoice.get('status') or '-').upper()],
    ]
    meta_tbl_data = [[Paragraph(f"<font color='#64748b'>{k}</font>", body), Paragraph(f"<b>{v}</b>", body)] for k, v in meta_lines]

    bill_to = (
        f"<b>Tagihan Kepada:</b><br/>"
        f"{client.get('name', '-')}<br/>"
        f"<font size=8 color='#64748b'>"
        f"{client.get('pic_name') or ''}<br/>"
        f"{client.get('pic_phone') or ''}<br/>"
        f"{client.get('pic_email') or ''}<br/>"
        f"{client.get('address') or client.get('city') or ''}"
        f"</font>"
    )

    cust_tbl = Table(
        [[
            Paragraph(bill_to, body),
            Table(meta_tbl_data, colWidths=[28 * mm, 38 * mm]),
        ]],
        colWidths=[100 * mm, 70 * mm],
    )
    cust_tbl.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elems.append(cust_tbl)
    elems.append(Spacer(1, 5 * mm))

    # Lines
    line_header = ['#', 'Deskripsi', 'Qty', 'Harga', 'Subtotal']
    line_rows = [line_header]
    for i, l in enumerate(invoice.get('lines') or [], start=1):
        line_rows.append([
            str(i),
            l.get('description') or '-',
            f"{l.get('qty', 0)} {l.get('unit') or ''}",
            _fmt_idr(l.get('unit_price')),
            _fmt_idr(l.get('line_total')),
        ])
    line_tbl = Table(line_rows, colWidths=[10 * mm, 80 * mm, 22 * mm, 30 * mm, 28 * mm])
    line_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
    ]))
    elems.append(line_tbl)
    elems.append(Spacer(1, 4 * mm))

    # Totals
    totals = [
        ['Subtotal', _fmt_idr(invoice.get('subtotal'))],
    ]
    if (invoice.get('discount_amount') or 0) > 0:
        totals.append(['Diskon', '-' + _fmt_idr(invoice.get('discount_amount'))])
    totals.append([f"PPN ({invoice.get('tax_pct') or 0}%)", _fmt_idr(invoice.get('tax_amount'))])
    totals.append(['<b>Total</b>', '<b>' + _fmt_idr(invoice.get('total_amount')) + '</b>'])
    totals.append(['Sudah Dibayar', _fmt_idr(invoice.get('paid_amount'))])
    totals.append(['<b>Saldo Tagihan</b>', '<b>' + _fmt_idr(invoice.get('balance_amount')) + '</b>'])
    totals_data = [[Paragraph(k, body_right), Paragraph(v, body_right)] for k, v in totals]
    totals_tbl = Table(totals_data, colWidths=[40 * mm, 35 * mm])
    totals_tbl.setStyle(TableStyle([
        ('LINEABOVE', (0, -3), (-1, -3), 0.6, colors.HexColor('#94a3b8')),
        ('LINEABOVE', (0, -1), (-1, -1), 0.6, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))

    spacer_total = Table([['', totals_tbl]], colWidths=[95 * mm, 75 * mm])
    spacer_total.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elems.append(spacer_total)
    elems.append(Spacer(1, 6 * mm))

    # Notes & footer
    if invoice.get('notes'):
        elems.append(Paragraph(f"<b>Catatan:</b> {invoice.get('notes')}", body_muted))
        elems.append(Spacer(1, 3 * mm))

    elems.append(HRFlowable(width='100%', thickness=0.4, color=colors.HexColor('#cbd5e1')))
    elems.append(Spacer(1, 3 * mm))
    elems.append(Paragraph(
        "Pembayaran ditujukan ke rekening yang sudah disepakati. Setelah transfer mohon konfirmasi "
        "ke Finance CV. Dewi Aditya melalui WhatsApp atau email. Terima kasih.",
        body_muted,
    ))

    doc.build(elems)
    return buf.getvalue()
