"""Shared market research engine. Yahoo Finance data; not investment advice."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import math
import re
import numpy as np
import pandas as pd
import yfinance as yf


def normalize_ticker(symbol: str) -> str:
    s = (symbol or "").strip().upper().replace(" ", "")
    if not s:
        raise ValueError("Masukkan kode saham.")
    if s.endswith(".JK"):
        code = s[:-3]
    elif "." in s:
        raise ValueError("V1 saat ini hanya mendukung ticker BEI dengan akhiran .JK.")
    else:
        code = s
    if not re.fullmatch(r"[A-Z0-9]{3,6}", code):
        raise ValueError("Format ticker BEI tidak valid. Contoh: ANTM atau ANTM.JK.")
    return f"{code}.JK"


def _number(value: Any):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def is_financial_institution(data: dict) -> bool:
    """Avoid industrial-company FCF DCF for banks, insurers and financial firms."""
    identity = " ".join(str(data.get(k) or "") for k in ("sector", "industry", "company", "ticker")).lower()
    terms = ("bank", "financial services", "financials", "insurance", "insurer", "capital markets", "credit services")
    return any(term in identity for term in terms)


def _statement_value(frame: pd.DataFrame, candidates: list[str]):
    """Read the newest available period for a matching Yahoo statement row."""
    if frame is None or frame.empty:
        return None
    columns = list(frame.columns)
    try:
        columns = sorted(columns, key=lambda c: pd.Timestamp(c), reverse=True)
    except (TypeError, ValueError):
        pass
    for candidate in candidates:
        matches = [label for label in frame.index if str(label).strip().lower() == candidate.lower()]
        if not matches:
            continue
        row = frame.loc[matches[0]]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        for column in columns:
            if column in row.index:
                n = _number(row[column])
                if n is not None:
                    return n
    return None


def _latest_period(frame: pd.DataFrame):
    if frame is None or frame.empty:
        return None
    try:
        return str(max(frame.columns, key=lambda c: pd.Timestamp(c)))
    except (TypeError, ValueError):
        return str(frame.columns[0])


def _safe_info(ticker):
    try:
        return ticker.get_info() or {}
    except Exception:
        try:
            return ticker.info or {}
        except Exception:
            return {}


def _safe_statement(ticker, name):
    try:
        value = getattr(ticker, name)
        return value if isinstance(value, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def analyze_equity(symbol: str, period: str = "5y") -> dict:
    ticker_symbol = normalize_ticker(symbol)
    ticker = yf.Ticker(ticker_symbol)
    info = _safe_info(ticker)
    hist = ticker.history(period=period, auto_adjust=True)
    if hist is None or hist.empty or "Close" not in hist:
        raise ValueError(f"Tidak ada data harga untuk {ticker_symbol}. Periksa ticker atau coba lagi nanti.")

    financials = _safe_statement(ticker, "financials")
    balance = _safe_statement(ticker, "balance_sheet")
    cashflow = _safe_statement(ticker, "cashflow")
    close = hist["Close"].dropna()
    if close.empty:
        raise ValueError(f"Data harga penutupan {ticker_symbol} tidak tersedia.")

    returns = close.pct_change().dropna()
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else latest
    change_pct = ((latest / previous) - 1) * 100 if previous else None
    sma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    sma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
    sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None

    delta = close.diff()
    # Wilder-style RSI smoothing (the conventional RSI 14 calculation).
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rsi_series = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    rsi_series = rsi_series.mask((loss == 0) & (gain > 0), 100)
    rsi_series = rsi_series.mask((loss == 0) & (gain == 0), 50)
    rsi = _number(rsi_series.iloc[-1]) if not rsi_series.empty else None

    volatility = _number(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else None
    total_return = ((latest / float(close.iloc[0])) - 1) * 100 if len(close) > 1 and close.iloc[0] else None

    revenue = _statement_value(financials, ["Total Revenue", "Operating Revenue"])
    net_income = _statement_value(financials, ["Net Income", "Net Income Common Stockholders"])
    operating_income = _statement_value(financials, ["Operating Income"])
    ebitda = _statement_value(financials, ["EBITDA"])
    total_debt = _statement_value(balance, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
    cash = _statement_value(balance, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    operating_cash_flow = _statement_value(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
    capex = _statement_value(cashflow, ["Capital Expenditure", "Capital Expenditures"])
    free_cash_flow = _statement_value(cashflow, ["Free Cash Flow"])
    if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
        free_cash_flow = operating_cash_flow - abs(capex)

    ratios = {
        "Revenue": revenue, "Net income": net_income, "Operating income": operating_income,
        "EBITDA": ebitda, "Market capitalization": _number(info.get("marketCap")),
        "Trailing P/E": _number(info.get("trailingPE")), "Price to book": _number(info.get("priceToBook")),
        "ROE (%)": _number(info.get("returnOnEquity")) * 100 if _number(info.get("returnOnEquity")) is not None else None,
        "Debt to equity": _number(info.get("debtToEquity")),
        "Dividend yield (%)": _number(info.get("dividendYield")) * 100 if _number(info.get("dividendYield")) is not None else None,
        "Operating cash flow": operating_cash_flow, "Capital expenditure": capex,
        "Free cash flow": free_cash_flow, "Total debt": total_debt, "Cash and equivalents": cash,
    }
    trend = ("Bullish (SMA20 > SMA50)" if sma20 > sma50 else "Bearish (SMA20 < SMA50)") if sma20 is not None and sma50 is not None else "Insufficient history"
    rsi_signal = "Unavailable" if rsi is None else ("Potentially overbought" if rsi >= 70 else ("Potentially oversold" if rsi <= 30 else "Neutral range"))
    history = hist.reset_index()
    date_column = "Date" if "Date" in history.columns else history.columns[0]
    history["Date"] = history[date_column].astype(str)

    warnings = []
    if not info.get("currency"):
        warnings.append("Mata uang emiten tidak tersedia dari metadata.")
    if financials.empty:
        warnings.append("Laporan laba rugi tidak tersedia.")
    if balance.empty:
        warnings.append("Neraca tidak tersedia.")
    if cashflow.empty:
        warnings.append("Laporan arus kas tidak tersedia.")
    if not financials.empty and not balance.empty and _latest_period(financials) != _latest_period(balance):
        warnings.append("Periode laporan laba rugi dan neraca berbeda; jangan bandingkan angka tanpa penyesuaian.")
    if not cashflow.empty and _latest_period(cashflow) != _latest_period(financials):
        warnings.append("Periode arus kas dan laba rugi berbeda; periksa sebelum menghitung valuasi.")
    return {
        "ticker": ticker_symbol, "company": info.get("longName") or info.get("shortName") or ticker_symbol,
        "sector": info.get("sector") or "Not disclosed", "industry": info.get("industry") or "Not disclosed",
        "currency": info.get("currency") or "Unknown", "as_of": datetime.now(timezone.utc).isoformat(),
        "latest_price_date": str(history["Date"].iloc[-1]), "latest_financial_period": _latest_period(financials),
        "latest_balance_period": _latest_period(balance), "latest_cashflow_period": _latest_period(cashflow),
        "price": latest, "previous_close": previous, "change_pct": change_pct,
        "period_return_pct": total_return, "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "rsi14": rsi, "annualized_volatility_pct": volatility, "trend": trend, "rsi_signal": rsi_signal,
        "ratios": ratios, "history": history[["Date", "Open", "High", "Low", "Close", "Volume"]],
        "data_source": "Yahoo Finance via yfinance",
        "data_quality_warnings": warnings,
        "data_quality_note": "Nilai fundamental disajikan sesuai data sumber; satuan dan periode wajib diverifikasi terhadap laporan emiten.",
        "disclaimer": "Data may be delayed, incomplete, restated, or unavailable. Not investment advice."
    }


def calculate_dcf(data: dict, years: int = 5, growth: float = 0.05, wacc: float = 0.12, terminal_growth: float = 0.025) -> dict:
    if is_financial_institution(data):
        return {"available": False, "reason": "DCF berbasis FCF perusahaan non-keuangan tidak digunakan untuk bank/asuransi. Gunakan pendekatan P/B-ROE, residual income, atau dividend discount dengan asumsi khusus sektor."}
    ratios = data.get("ratios", {})
    fcf = _number(ratios.get("Free cash flow"))
    if fcf is None:
        return {"available": False, "reason": "Free cash flow tidak tersedia dari sumber data."}
    if fcf <= 0:
        return {"available": False, "reason": "FCF dasar nol atau negatif. DCF perpetuity standar tidak ditampilkan; lakukan normalisasi arus kas dan analisis skenario."}
    if not isinstance(years, int) or years < 1 or years > 20:
        return {"available": False, "reason": "Periode proyeksi harus 1 sampai 20 tahun."}
    if any(_number(x) is None for x in (growth, wacc, terminal_growth)):
        return {"available": False, "reason": "Asumsi growth, WACC, dan terminal growth harus berupa angka valid."}
    if growth <= -1 or terminal_growth <= -1 or wacc <= -1:
        return {"available": False, "reason": "Asumsi tingkat pertumbuhan dan diskonto tidak boleh <= -100%."}
    if wacc <= terminal_growth:
        return {"available": False, "reason": "WACC harus lebih tinggi daripada terminal growth."}

    forecast, pv_sum = [], 0.0
    for year in range(1, years + 1):
        cash_flow = fcf * ((1 + growth) ** year)
        pv = cash_flow / ((1 + wacc) ** year)
        pv_sum += pv
        forecast.append({"Year": year, "FCF": cash_flow, "Present value": pv})
    terminal_value = forecast[-1]["FCF"] * (1 + terminal_growth) / (wacc - terminal_growth)
    terminal_pv = terminal_value / ((1 + wacc) ** years)
    return {"available": True, "base_fcf": fcf, "forecast": pd.DataFrame(forecast),
            "pv_forecast": pv_sum, "terminal_value": terminal_value, "pv_terminal_value": terminal_pv,
            "enterprise_value": pv_sum + terminal_pv,
            "assumptions": {"years": years, "growth": growth, "wacc": wacc, "terminal_growth": terminal_growth},
            "currency": data.get("currency", "Unknown"),
            "warning": "Estimasi enterprise value sederhana dalam satuan dan mata uang sumber FCF; bukan harga wajar per saham. Periksa satuan, mata uang, periode, net debt, jumlah saham, kualitas FCF, pajak dan kebutuhan modal."}


def build_research_summary(data: dict) -> list[str]:
    return [
        f"Perubahan harga harian: {data['change_pct']:.2f}%." if data.get("change_pct") is not None else "Perubahan harga harian tidak tersedia.",
        f"Return periode data: {data['period_return_pct']:.2f}%." if data.get("period_return_pct") is not None else "Return periode tidak tersedia.",
        f"Tren moving average: {data['trend']}.",
        f"RSI 14: {data['rsi14']:.1f} ({data['rsi_signal']})." if data.get("rsi14") is not None else "RSI tidak tersedia.",
        f"Volatilitas tahunan historis: {data['annualized_volatility_pct']:.2f}%." if data.get("annualized_volatility_pct") is not None else "Volatilitas tidak tersedia."
    ]



def dcf_sensitivity(data: dict, growth_rates=None, wacc_rates=None, years: int = 5, terminal_growth: float = 0.025) -> dict:
    """Return a clearly labeled enterprise-value sensitivity matrix, not per-share value."""
    growth_rates = list(growth_rates if growth_rates is not None else [0.00, 0.05, 0.10])
    wacc_rates = list(wacc_rates if wacc_rates is not None else [0.10, 0.12, 0.14])
    base = _number(data.get("ratios", {}).get("Free cash flow"))
    if is_financial_institution(data):
        return {"available": False, "reason": "Sensitivity DCF FCF tidak digunakan untuk perusahaan keuangan."}
    if base is None or base <= 0:
        return {"available": False, "reason": "Sensitivity DCF memerlukan FCF dasar positif."}
    if not isinstance(years, int) or years < 1 or years > 20:
        return {"available": False, "reason": "Periode proyeksi harus 1 sampai 20 tahun."}
    if not growth_rates or not wacc_rates:
        return {"available": False, "reason": "Daftar skenario growth dan WACC tidak boleh kosong."}
    rows = []
    for growth_rate in growth_rates:
        g = _number(growth_rate)
        if g is None or g <= -1:
            return {"available": False, "reason": "Growth scenario harus lebih besar dari -100%."}
        row = {"FCF growth": g}
        for discount_rate in wacc_rates:
            w = _number(discount_rate)
            if w is None or w <= terminal_growth:
                return {"available": False, "reason": "Setiap WACC harus lebih tinggi daripada terminal growth."}
            pv = sum(base * ((1 + g) ** year) / ((1 + w) ** year) for year in range(1, years + 1))
            terminal_fcf = base * ((1 + g) ** years)
            terminal_value = terminal_fcf * (1 + terminal_growth) / (w - terminal_growth)
            pv_terminal = terminal_value / ((1 + w) ** years)
            row[f"WACC {w:.1%}"] = pv + pv_terminal
        rows.append(row)
    return {"available": True, "matrix": pd.DataFrame(rows), "currency": data.get("currency", "Unknown"),
            "warning": "Seluruh angka adalah enterprise value indikatif dalam unit/mata uang FCF sumber, bukan nilai per saham."}
