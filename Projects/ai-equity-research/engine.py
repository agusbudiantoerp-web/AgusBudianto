"""Shared market research engine. Yahoo Finance data; not investment advice."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import math
import numpy as np
import pandas as pd
import yfinance as yf

def normalize_ticker(symbol: str) -> str:
    s = (symbol or "").strip().upper().replace(" ", "")
    if not s: raise ValueError("Masukkan kode saham.")
    if "." not in s and s.isalnum(): s += ".JK"
    return s

def _number(value: Any):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError): return None

def _statement_value(frame: pd.DataFrame, candidates: list[str]):
    if frame is None or frame.empty: return None
    for candidate in candidates:
        for label in frame.index:
            if str(label).lower() == candidate.lower():
                row = frame.loc[label]
                if isinstance(row, pd.Series):
                    for value in row.values:
                        n = _number(value)
                        if n is not None: return n
                else: return _number(row)
    return None

def _safe_info(ticker):
    try: return ticker.get_info() or {}
    except Exception:
        try: return ticker.info or {}
        except Exception: return {}

def _safe_statement(ticker, name):
    try:
        value = getattr(ticker, name)
        return value if isinstance(value, pd.DataFrame) else pd.DataFrame()
    except Exception: return pd.DataFrame()

def analyze_equity(symbol: str, period: str = "5y") -> dict:
    ticker_symbol = normalize_ticker(symbol)
    ticker = yf.Ticker(ticker_symbol)
    info = _safe_info(ticker)
    hist = ticker.history(period=period, auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"Tidak ada data harga untuk {ticker_symbol}. Periksa ticker atau coba lagi nanti.")
    financials = _safe_statement(ticker, "financials")
    balance = _safe_statement(ticker, "balance_sheet")
    cashflow = _safe_statement(ticker, "cashflow")
    close = hist["Close"].dropna()
    returns = close.pct_change().dropna()
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else latest
    change_pct = ((latest / previous) - 1) * 100 if previous else None
    sma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    sma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
    sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
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
        free_cash_flow = operating_cash_flow + capex
    ratios = {
        "Revenue": revenue, "Net income": net_income, "Operating income": operating_income,
        "EBITDA": ebitda, "Market capitalization": _number(info.get("marketCap")),
        "Trailing P/E": _number(info.get("trailingPE")), "Price to book": _number(info.get("priceToBook")),
        "ROE (%)": (_number(info.get("returnOnEquity")) or 0) * 100 if info.get("returnOnEquity") is not None else None,
        "Debt to equity": _number(info.get("debtToEquity")),
        "Dividend yield (%)": (_number(info.get("dividendYield")) or 0) * 100 if info.get("dividendYield") is not None else None,
        "Operating cash flow": operating_cash_flow, "Capital expenditure": capex,
        "Free cash flow": free_cash_flow, "Total debt": total_debt, "Cash and equivalents": cash,
    }
    trend = ("Bullish (SMA20 > SMA50)" if sma20 > sma50 else "Bearish (SMA20 < SMA50)") if sma20 is not None and sma50 is not None else "Insufficient history"
    rsi_signal = "Unavailable" if rsi is None else ("Potentially overbought" if rsi >= 70 else ("Potentially oversold" if rsi <= 30 else "Neutral range"))
    history = hist.reset_index()
    history["Date"] = history["Date"].astype(str)
    return {
        "ticker": ticker_symbol, "company": info.get("longName") or info.get("shortName") or ticker_symbol,
        "sector": info.get("sector") or "Not disclosed", "industry": info.get("industry") or "Not disclosed",
        "currency": info.get("currency") or "Unknown", "as_of": datetime.now(timezone.utc).isoformat(),
        "price": latest, "previous_close": previous, "change_pct": change_pct,
        "period_return_pct": total_return, "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "rsi14": rsi, "annualized_volatility_pct": volatility, "trend": trend, "rsi_signal": rsi_signal,
        "ratios": ratios, "history": history[["Date", "Open", "High", "Low", "Close", "Volume"]],
        "data_source": "Yahoo Finance via yfinance",
        "disclaimer": "Data may be delayed, incomplete, restated, or unavailable. Not investment advice."
    }

def calculate_dcf(data: dict, years: int = 5, growth: float = 0.05, wacc: float = 0.12, terminal_growth: float = 0.025) -> dict:
    fcf = data["ratios"].get("Free cash flow")
    if fcf is None: return {"available": False, "reason": "Free cash flow tidak tersedia dari sumber data."}
    if wacc <= terminal_growth: return {"available": False, "reason": "WACC harus lebih tinggi daripada terminal growth."}
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
            "warning": "Estimasi sederhana berbasis FCF agregat yang tersedia; bukan valuasi lengkap per saham. Periksa satuan, mata uang, periode, dan kualitas data."}

def build_research_summary(data: dict) -> list[str]:
    return [
        f"Perubahan harga harian: {data['change_pct']:.2f}%." if data.get("change_pct") is not None else "Perubahan harga harian tidak tersedia.",
        f"Return periode data: {data['period_return_pct']:.2f}%." if data.get("period_return_pct") is not None else "Return periode tidak tersedia.",
        f"Tren moving average: {data['trend']}.",
        f"RSI 14: {data['rsi14']:.1f} ({data['rsi_signal']})." if data.get("rsi14") is not None else "RSI tidak tersedia.",
        f"Volatilitas tahunan historis: {data['annualized_volatility_pct']:.2f}%." if data.get("annualized_volatility_pct") is not None else "Volatilitas tidak tersedia."
    ]
