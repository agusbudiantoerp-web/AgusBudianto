import unittest
from io import BytesIO
import pandas as pd
from engine import normalize_ticker, calculate_dcf, dcf_sensitivity, _statement_value, is_financial_institution
from reports import make_excel_report, make_pdf_report
from security import parse_allowed_chat_ids, is_authorized_chat

class EngineTests(unittest.TestCase):
    def test_idx_ticker_suffix(self): self.assertEqual(normalize_ticker("antm"), "ANTM.JK")
    def test_explicit_suffix_kept(self): self.assertEqual(normalize_ticker("ANTM.JK"), "ANTM.JK")
    def test_non_idx_exchange_rejected_in_v1(self):
        with self.assertRaises(ValueError): normalize_ticker("AAPL.US")
    def test_empty_ticker_rejected(self):
        with self.assertRaises(ValueError): normalize_ticker("")
    def test_dcf_unavailable_without_fcf(self): self.assertFalse(calculate_dcf({"ratios":{"Free cash flow":None}})["available"])
    def test_dcf_rejects_invalid_discount_spread(self): self.assertFalse(calculate_dcf({"ratios":{"Free cash flow":100}},wacc=.02,terminal_growth=.03)["available"])
    def test_dcf_rejects_invalid_years(self): self.assertFalse(calculate_dcf({"ratios":{"Free cash flow":100}},years=0)["available"])
    def test_dcf_calculates_positive_fcf(self):
        result=calculate_dcf({"ratios":{"Free cash flow":100}})
        self.assertTrue(result["available"]); self.assertGreater(result["enterprise_value"],0); self.assertIsInstance(result["forecast"],pd.DataFrame)
    def test_dcf_rejects_negative_fcf(self):
        result=calculate_dcf({"ratios":{"Free cash flow":-100}})
        self.assertFalse(result["available"])
    def test_dcf_sensitivity_returns_matrix(self):
        result=dcf_sensitivity({"currency":"IDR","ratios":{"Free cash flow":100}})
        self.assertTrue(result["available"])
        self.assertEqual(result["matrix"].shape, (3, 4))
    def test_dcf_sensitivity_rejects_wacc_below_terminal_growth(self):
        result=dcf_sensitivity({"ratios":{"Free cash flow":100}}, wacc_rates=[0.02], terminal_growth=0.03)
        self.assertFalse(result["available"])
    def test_dcf_disabled_for_bank_ticker(self):
        result=calculate_dcf({"ticker":"BBCA.JK","company":"PT Bank Central Asia Tbk","sector":"Financial Services","ratios":{"Free cash flow":100}})
        self.assertFalse(result["available"]); self.assertIn("bank",result["reason"].lower())
    def test_financial_institution_detection(self):
        self.assertTrue(is_financial_institution({"industry":"Banks - Regional"}))
        self.assertFalse(is_financial_institution({"sector":"Basic Materials","industry":"Gold"}))
    def test_statement_uses_latest_period(self):
        frame=pd.DataFrame([[200,100]],index=["Total Revenue"],columns=[pd.Timestamp("2024-12-31"),pd.Timestamp("2025-12-31")])
        self.assertEqual(_statement_value(frame,["Total Revenue"]),100)
    def test_statement_newest_column_first(self):
        frame=pd.DataFrame([[100,200]],index=["Total Revenue"],columns=[pd.Timestamp("2025-12-31"),pd.Timestamp("2024-12-31")])
        self.assertEqual(_statement_value(frame,["Total Revenue"]),100)
    def test_excel_report(self):
        book=pd.ExcelFile(BytesIO(make_excel_report(sample_data())))
        self.assertIn("Summary",book.sheet_names); self.assertIn("Fundamentals",book.sheet_names); self.assertIn("Price History",book.sheet_names)
    def test_pdf_report(self): self.assertTrue(make_pdf_report(sample_data()).startswith(b"%PDF"))
    def test_allowlist_parses_multiple_ids(self): self.assertEqual(parse_allowed_chat_ids("123, -456"),{123,-456})
    def test_allowlist_rejects_invalid_id(self):
        with self.assertRaises(ValueError): parse_allowed_chat_ids("123,abc")
    def test_empty_allowlist_denies_all(self): self.assertFalse(is_authorized_chat(123,set()))
    def test_only_matching_chat_allowed(self):
        self.assertTrue(is_authorized_chat(123,{123})); self.assertFalse(is_authorized_chat(456,{123})); self.assertFalse(is_authorized_chat(None,{123}))

def sample_data():
    return {"ticker":"ANTM.JK","company":"PT Aneka Tambang & Co.","sector":"Basic Materials","industry":"Metals","currency":"IDR","as_of":"2026-11-05T00:00:00+00:00","price":1500.0,"change_pct":1.2,"period_return_pct":12.0,"trend":"Bullish","rsi14":55.0,"annualized_volatility_pct":30.0,"data_source":"Yahoo Finance via yfinance","disclaimer":"Data may be delayed.","ratios":{"Revenue":1000,"Free cash flow":100},"history":pd.DataFrame([{"Date":"2026-11-04","Open":1490,"High":1510,"Low":1480,"Close":1500,"Volume":100000}])}

if __name__ == "__main__": unittest.main()
