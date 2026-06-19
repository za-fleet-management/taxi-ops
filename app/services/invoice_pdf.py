from datetime import date
from io import BytesIO

from fpdf import FPDF


class InvoicePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 64, 175)
        self.cell(0, 10, "TaxiOps", align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, 20, 200, 20)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_invoice_pdf(
    org_name: str,
    org_region: str,
    vat_number: str | None,
    invoice_number: str,
    amount_cents: int,
    payment_date: date,
    reference: str,
    period_start: date | None,
    period_end: date | None,
) -> bytes:
    pdf = InvoicePDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, org_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    if org_region:
        pdf.cell(0, 6, org_region, new_x="LMARGIN", new_y="NEXT")
    if vat_number:
        pdf.cell(0, 6, f"VAT: {vat_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, f"Invoice: {invoice_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Date: {payment_date}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, "Billing Period:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    period_str = f"{period_start} to {period_end}" if period_start and period_end else "—"
    pdf.cell(0, 6, period_str, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Payment Reference: {reference}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Subscription Fee", new_x="LMARGIN", new_y="NEXT")

    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    amount_rand = amount_cents / 100
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(140, 7, "Subscription Payment")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, f"R {amount_rand:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    if vat_number:
        vat_amount = amount_rand * 0.15
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(140, 7, "VAT (15%)")
        pdf.cell(0, 7, f"R {vat_amount:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(140, 10, "Total")
    pdf.cell(0, 10, f"R {amount_rand:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Thank you for your payment.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "This invoice was generated automatically by TaxiOps.", new_x="LMARGIN", new_y="NEXT")

    return pdf.output()
