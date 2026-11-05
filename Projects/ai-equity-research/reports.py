"""Excel and PDF report builders."""
from io import BytesIO
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def make_excel_report(data: dict, dcf: dict | None = None) -> bytes:
    out = BytesIO()
    ratios = pd.DataFrame([{"Metric": k, "Value": v} for k, v in data["ratios"].items()])
    snapshot = pd.DataFrame([{"Ticker": data["ticker"], "Company": data["company"],
        "Sector": data["sector"], "Industry": data["industry"], "Currency": data["currency"],
        "As of UTC": data["as_of"], "Latest price date": data.get("latest_price_date"),
        "Latest financial period": data.get("latest_financial_period"), "Latest price": data["price"],
        "Daily change %": data["change_pct"], "Period return %": data["period_return_pct"],
        "Trend": data["trend"], "RSI 14": data["rsi14"],
        "Annualized volatility %": data["annualized_volatility_pct"], "Data source": data["data_source"],
        "Data quality note": data.get("data_quality_note")}])
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        snapshot.to_excel(writer, sheet_name="Summary", index=False)
        ratios.to_excel(writer, sheet_name="Fundamentals", index=False)
        data["history"].to_excel(writer, sheet_name="Price History", index=False)
        if dcf and dcf.get("available"):
            dcf["forecast"].to_excel(writer, sheet_name="DCF Forecast", index=False)
            dcf_rows = [{"Metric": "Enterprise value", "Value": dcf["enterprise_value"]},
                {"Metric": "PV forecast", "Value": dcf["pv_forecast"]},
                {"Metric": "PV terminal value", "Value": dcf["pv_terminal_value"]}]
            dcf_rows += [{"Metric": k, "Value": v} for k, v in dcf["assumptions"].items()]
            pd.DataFrame(dcf_rows).to_excel(writer, sheet_name="DCF Valuation", index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                letter = col[0].column_letter
                max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
                ws.column_dimensions[letter].width = min(max(max_len + 2, 12), 42)
    return out.getvalue()


def make_pdf_report(data: dict, dcf: dict | None = None) -> bytes:
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=38, leftMargin=38, topMargin=38, bottomMargin=38)
    styles = getSampleStyleSheet()
    company = escape(str(data["company"]))
    ticker = escape(str(data["ticker"]))
    sector = escape(str(data["sector"]))
    industry = escape(str(data["industry"]))
    currency = escape(str(data["currency"]))
    story = [Paragraph("AI Equity Research Report", styles["Title"]), Spacer(1, 8),
        Paragraph(f"{company} ({ticker})", styles["Heading2"]),
        Paragraph(f"Sector: {sector} | Industry: {industry} | Currency: {currency}", styles["Normal"]),
        Paragraph(f"Generated (UTC): {escape(str(data['as_of']))}", styles["Normal"]), Spacer(1, 14)]
    rows = [["Metric", "Value"], ["Latest price", str(data.get("price"))],
        ["Daily change (%)", str(data.get("change_pct"))], ["Period return (%)", str(data.get("period_return_pct"))],
        ["Trend", str(data.get("trend"))], ["RSI 14", str(data.get("rsi14"))],
        ["Annualized volatility (%)", str(data.get("annualized_volatility_pct"))]]
    table = Table(rows, colWidths=[210, 250])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#163447")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .4, colors.grey),
        ("PADDING", (0,0), (-1,-1), 6)]))
    story += [table, Spacer(1, 14), Paragraph("Fundamental data", styles["Heading2"])]
    fundamental_rows = [["Metric", "Value"]] + [[str(k), "N/A" if v is None else str(v)] for k, v in data["ratios"].items()]
    ft = Table(fundamental_rows, colWidths=[210, 250], repeatRows=1)
    ft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#163447")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.grey),
        ("FONTSIZE",(0,0),(-1,-1),8),("PADDING",(0,0),(-1,-1),4)]))
    story += [ft, Spacer(1, 14)]
    if dcf and dcf.get("available"):
        story += [Paragraph("Illustrative DCF", styles["Heading2"]),
            Paragraph(f"Enterprise value estimate: {dcf['enterprise_value']:,.2f}", styles["Normal"]),
            Paragraph(escape(dcf["warning"]), styles["BodyText"]), Spacer(1, 10)]
    elif dcf:
        story += [Paragraph("DCF unavailable: " + escape(dcf.get("reason", "Insufficient data")), styles["BodyText"]), Spacer(1, 10)]
    story += [Paragraph("Important limitations", styles["Heading2"]),
        Paragraph(escape(str(data["disclaimer"])), styles["BodyText"]),
        Paragraph("This report is generated from third-party market data and automated calculations. Verify source data, accounting periods, units, corporate actions and assumptions independently. It is not a recommendation to buy or sell securities.", styles["BodyText"])]
    doc.build(story)
    return out.getvalue()
