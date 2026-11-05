"""Telegram bot protected by a fail-closed chat-ID allowlist."""
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from engine import analyze_equity, calculate_dcf
from reports import make_excel_report, make_pdf_report
from security import is_authorized_chat, parse_allowed_chat_ids

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def allowed(update: Update) -> bool:
    chat = update.effective_chat
    if chat is None or not is_authorized_chat(chat.id):
        if update.effective_message:
            await update.effective_message.reply_text("Akses belum diizinkan. Hubungi administrator bot.")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await allowed(update):
        await update.effective_message.reply_text("AI Equity Research Bot siap untuk saham BEI. Gunakan /analyze ANTM. Data pihak ketiga; bukan rekomendasi investasi.")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await allowed(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Format: /analyze ANTM")
        return
    symbol = context.args[0]
    status = await update.effective_message.reply_text("Sedang menganalisis " + symbol.upper() + "...")
    try:
        data = analyze_equity(symbol)
        dcf = calculate_dcf(data)
        change = "N/A" if data.get("change_pct") is None else "{:.2f}%".format(data["change_pct"])
        ret = "N/A" if data.get("period_return_pct") is None else "{:.2f}%".format(data["period_return_pct"])
        rsi = "N/A" if data.get("rsi14") is None else "{:.1f}".format(data["rsi14"])
        vol = "N/A" if data.get("annualized_volatility_pct") is None else "{:.2f}%".format(data["annualized_volatility_pct"])
        dcf_text = "{:,.2f}".format(dcf["enterprise_value"]) if dcf.get("available") else dcf.get("reason", "N/A")
        lines = [data["company"] + " (" + data["ticker"] + ")", "Harga: {:,.2f} {}".format(data["price"], data["currency"]), "Perubahan harian: " + change, "Return periode: " + ret, "Tren: " + data["trend"], "RSI 14: " + rsi, "Volatilitas tahunan: " + vol, "DCF EV indikatif: " + dcf_text, "Data pihak ketiga; bukan rekomendasi investasi."]
        await status.edit_text("\n".join(lines))
        await update.effective_message.reply_document(document=make_excel_report(data, dcf), filename=data["ticker"].replace(".", "_") + "_research.xlsx")
        await update.effective_message.reply_document(document=make_pdf_report(data, dcf), filename=data["ticker"].replace(".", "_") + "_research.pdf")
    except Exception:
        logging.exception("Analysis failed for %s", symbol)
        await status.edit_text("Analisis gagal. Periksa ticker atau coba kembali nanti.")

def main():
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN.")
    if not os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip():
        raise RuntimeError("Set TELEGRAM_ALLOWED_CHAT_IDS. Bot menolak berjalan tanpa allowlist.")
    parse_allowed_chat_ids()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))
    app.run_polling()

if __name__ == "__main__":
    main()
