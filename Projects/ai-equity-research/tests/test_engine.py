import unittest
from io import BytesIO
import pandas as pd
from engine import normalize_ticker, calculate_dcf, _statement_value
from reports import make_excel_report, make_pdf_report


class EngineTests(unittest.TestCase):
    def test_idx_ticker_suffix(self):
        self.assertEqual(normalize_ticker("antm"), "ANTM.JK")

    def test_explicit_suffix_kept(self):
        self.assertEqual(normalize_ticker("ANTM.JK"), "ANTM.JK")

    def test_non_idx_exchange_rejected_in_v1(self):
        with self.assertRaises(ValueError):
            normalize_ticker("AAPL.US")

    def test_empty_ticker_rejected(self):
        with self.assertRaises(ValueError):
            normalize_ticker("")

    def test_dcf_unavailable_without_fcf(self):
        result = calculate_dcf({"ratios": {"Free cash flow": None}})
        self.assertFalse(result["available"])

    def test_dcf_rejects_invalid_discount_spread(self):
        result = calculate_dcf({"ratios": {"Free cash flow": 100}}, wacc=0.02, terminal_growth=0.03)
        self.assertFalse(result["available"])

    def test_dcf_rejects_invalid_years(self):
        result = calculate_dcf({"ratios": {"Free cash flow": 100}}, years=0)
        self.assertFalse(result["available"])

    def test_dcf_calculates_positive_fcf(self):
        result = calculate_dcf({"ratios": {"Free cash flow": 100}}, years=5, growth=0.05, wacc=0.12, terminal_growth=0.025)
        self.assertTrue(result["available"])
        self.assertGreater(result["enterprise_value"], 0)
        self.assertIsInstance(result["forecast"], pd.DataFrame)

    def test_statement_uses_latest_period_not_first_column(self):
        frame = pd.DataFrame([[200, 100]], index=["Total Revenue"],
                             columns=[pd.Timestamp("2024-12-31"), pd.Timestamp("2025-12-31")])
        self.assertEqual(_statement_value(frame, ["Total Revenue"]), 100)

    def test_statement_uses_newest_period_value(self):
        frame = pd.DataFrame([[100, 200]], index=["Total Revenue"],
                             columns=[pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")])
        self.assertEqual(_statement_value(frame, ["Total Revenue"]), 100)

    def test_excel_report_generates_valid_xlsx(self):
        data = sample_data()
        payload = make_excel_report(data)
        workbook = pd.ExcelFile(BytesIO(payload))
        self.assertIn("Summary", workbook.sheet_names)
        self.assertIn("Fundamentals", workbook.sheet_names)
        self.assertIn("Price History", workbook.sheet_names)

    def test_pdf_report_generates_pdf(self):
        data = sample_data()
        payload = make_pdf_report(data)
        self.assertTrue(payload.startswith(b"%PDF"))


def sample_data():
    return {
        "ticker": "ANTM.JK", "company": "PT Aneka Tambang & Co.", "sector": "Basic Materials",
        "industry": "Metals", "currency": "IDR", "as_of": "2026-11-05T00:00:00+00:00",
        "price": 1500.0, "change_pct": 1.2, "period_return_pct": 12.0,
        "trend": "Bullish", "rsi14": 55.0, "annualized_volatility_pct": 30.0,
        "data_source": "Yahoo Finance via yfinance", "disclaimer": "Data may be delayed.",
        "ratios": {"Revenue": 1000, "Free cash flow": 100},
        "history": pd.DataFrame([{"Date": "2026-11-04", "Open": 1490, "High": 1510,
                                  "Low": 1480, "Close": 1500, "Volume": 100000}])
    }


if __name__ == "__main__":
    unittest.main()
