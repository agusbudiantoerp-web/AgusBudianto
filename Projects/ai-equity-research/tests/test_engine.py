import unittest
import pandas as pd
from engine import normalize_ticker, calculate_dcf

class EngineTests(unittest.TestCase):
    def test_idx_ticker_suffix(self):
        self.assertEqual(normalize_ticker("antm"), "ANTM.JK")

    def test_explicit_suffix_kept(self):
        self.assertEqual(normalize_ticker("ANTM.JK"), "ANTM.JK")

    def test_empty_ticker_rejected(self):
        with self.assertRaises(ValueError):
            normalize_ticker("")

    def test_dcf_unavailable_without_fcf(self):
        result = calculate_dcf({"ratios": {"Free cash flow": None}})
        self.assertFalse(result["available"])

    def test_dcf_rejects_invalid_discount_spread(self):
        result = calculate_dcf({"ratios": {"Free cash flow": 100}}, wacc=0.02, terminal_growth=0.03)
        self.assertFalse(result["available"])

    def test_dcf_calculates_positive_fcf(self):
        result = calculate_dcf({"ratios": {"Free cash flow": 100}}, years=5, growth=0.05, wacc=0.12, terminal_growth=0.025)
        self.assertTrue(result["available"])
        self.assertGreater(result["enterprise_value"], 0)
        self.assertIsInstance(result["forecast"], pd.DataFrame)

if __name__ == "__main__":
    unittest.main()
