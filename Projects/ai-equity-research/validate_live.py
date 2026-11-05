"""Manual live-data smoke test for selected IDX issuers.

Run from this directory: python validate_live.py
This is a connectivity/data-availability check, not a financial-statement audit.
"""
import json
from engine import analyze_equity, calculate_dcf

TICKERS = ["ANTM", "BBCA", "PTBA"]

for symbol in TICKERS:
    print("\n" + "=" * 68)
    print("LIVE DATA CHECK:", symbol)
    try:
        data = analyze_equity(symbol, period="2y")
        dcf = calculate_dcf(data)
        print(json.dumps({
            "ticker": data["ticker"],
            "company": data["company"],
            "sector": data["sector"],
            "industry": data["industry"],
            "currency": data["currency"],
            "latest_price_date": data["latest_price_date"],
            "latest_price": data["price"],
            "income_statement_period": data["latest_financial_period"],
            "balance_sheet_period": data["latest_balance_period"],
            "cash_flow_period": data["latest_cashflow_period"],
            "revenue_source_value": data["ratios"].get("Revenue"),
            "net_income_source_value": data["ratios"].get("Net income"),
            "operating_cash_flow_source_value": data["ratios"].get("Operating cash flow"),
            "capex_source_value": data["ratios"].get("Capital expenditure"),
            "free_cash_flow_source_value": data["ratios"].get("Free cash flow"),
            "dcf_available": dcf.get("available"),
            "dcf_reason": dcf.get("reason"),
            "data_quality_warnings": data.get("data_quality_warnings", []),
            "data_source": data["data_source"]
        }, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ticker": symbol, "error": str(exc)}, ensure_ascii=False))
