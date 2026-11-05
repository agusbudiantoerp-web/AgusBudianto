"""Telegram interface. Set TELEGRAM_BOT_TOKEN in environment; polling for local testing."""
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from engine import analyze_equity, calculate_dcf
from reports import make_excel_report, make_pdf_report
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("AI Equity Research Bot siap.\nGunakan /analyze ANTM atau /analyze AAPL.\nData Yahoo Finance; bukan rekomendasi investasi.")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /analyze ANTM")
        return
    symbol = context.args[0]
    status = await update.message.reply_text(f"Sedang menganalisis {symbol.upper()}...")
    try:
        data = analyze_equity(symbol)
        dcf = calculate_dcf(data)
        lines = [
            f"{data['company']} ({data['ticker']})",
            f"Harga terakhir: {data['price']:,.2f} {data['currency']}",
            f"Perubahan harian: {data['change_pct']:.2f}%" if data.get("change_pct") is not None else "Perubahan harian: N/A",
            f"Return periode: {data['period_return_pct']:.2f}%" if data.get("period_return_pct") is not None else "Return periode: N/A",
            f"Tren: {data['trend']}",
            f"RSI 14: {data['rsi14']:.1f}" if data.get("rsi14") is not None else "RSI 14: N/A",
            f"Volatilitas tahunan: {data['annualized_volatility_pct']:.2f}%" if data.get("annualized_volatility_pct") is not None else "Volatilitas: N/A",
            f"DCF EV indikatif: {dcf['enterprise_value']:,.2f}" if dcf.get("available") else "DCF: " + dcf.get("reason", "N/A"),
            "Catatan: data pihak ketiga; bukan rekomendasi investasi."
        ]
        await status.edit_text("\n".join(lines))
        await update.message.reply_document(document=make_excel_report(data, dcf), filename=f"{data['ticker'].replace('.', '_')}_research.xlsx", caption="Excel research report")
        await update.message.reply_document(document=make_pdf_report(data, dcf), filename=f"{data['ticker'].replace('.', '_')}_research.pdf", caption="PDF research report")
    except Exception as exc:
        await status.edit_text(f"Gagal menganalisis {symbol.upper()}: {exc}")

def main():
    if not TOKEN: raise RuntimeError("Set TELEGRAM_BOT_TOKEN environment variable before running the bot.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))
    app.run_polling()
if __name__ == "__main__": main()
