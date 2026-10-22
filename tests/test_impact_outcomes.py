"""Synthetic fixtures only; these tests do not supply real impact observations."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

import impact_outcomes as impact


class HouseholdOutcomesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic_households.csv"

    def write(self, rows):
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=impact.FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return self.path

    def row(self, **changes):
        row = dict.fromkeys(impact.FIELDS, "")
        row.update(borrower_id="SYNTHETIC-001", baseline_date="2024-01-01",
                   followup_date="2025-01-01", currency="INR", income_period="monthly",
                   household_size_baseline=4, household_size_followup=5,
                   household_income_baseline=1000, household_income_followup=1500,
                   business_income_baseline=-50, business_income_followup=100,
                   installments_due=12, installments_paid_on_time=10)
        row.update(changes)
        return row

    def test_header_only_template_returns_needs_data_and_no_impact(self):
        result = impact.analyze_outcomes(impact.TEMPLATE_PATH)
        self.assertEqual(result["status"], "needs_data")
        self.assertFalse(result["available"])
        self.assertEqual(result["currency_groups"], [])
        self.assertEqual(result["data_quality"]["rows_read"], 0)
        json.dumps(result, allow_nan=False)

    def test_absent_data_returns_needs_data(self):
        self.assertEqual(impact.analyze_outcomes(self.path)["status"], "needs_data")

    def test_paired_change_per_capita_repayment_and_annual_normalization(self):
        rows = [self.row(), self.row(borrower_id="SYNTHETIC-002", income_period="annual",
                                   household_income_baseline=12000, household_income_followup=18000,
                                   business_income_baseline=-600, business_income_followup=1200)]
        result = impact.analyze_outcomes(self.write(rows))
        group = result["currency_groups"][0]
        self.assertEqual(group["household_income"]["mean_change"], 500)
        self.assertEqual(group["household_income"]["mean_individual_percent_change"], 50)
        self.assertEqual(group["per_capita_household_income"]["mean_change"], 50)
        self.assertEqual(group["business_income"]["mean_change"], 150)
        self.assertEqual(group["business_income"]["percent_change_n"], 0)
        self.assertEqual(group["repayment"]["on_time_ratio"], round(20 / 24, 4))
        self.assertEqual(group["followup_days"]["median"], 366)

    def test_currency_boundaries_and_missing_pairs_are_explicit(self):
        rows = [self.row(), self.row(borrower_id="SYNTHETIC-002", currency="USD",
                                   household_income_followup="", household_size_followup="",
                                   business_income_baseline="", installments_due="", installments_paid_on_time="")]
        result = impact.analyze_outcomes(self.write(rows))
        self.assertEqual(len(result["currency_groups"]), 2)
        self.assertEqual(result["data_quality"]["incomplete_household_pairs"], 1)
        usd = result["currency_groups"][1]
        self.assertEqual(usd["household_income"]["paired_n"], 0)
        self.assertIsNone(usd["repayment"]["on_time_ratio"])
        self.assertEqual(usd["business_income"]["paired_n"], 0)

    def test_invalid_values_and_dates_withhold_results(self):
        for changes in ({"household_income_baseline": "NaN"}, {"household_income_followup": "inf"},
                        {"followup_date": "2023-12-31"}, {"baseline_date": "2024-02-30"},
                        {"followup_date": "2999-01-01"},
                        {"household_size_baseline": 0}, {"household_size_followup": 1.5},
                        {"installments_paid_on_time": 13}, {"installments_due": ""},
                        {"currency": "inr"}, {"income_period": "daily"}, {"borrower_id": ""}):
            with self.subTest(changes=changes):
                result = impact.analyze_outcomes(self.write([self.row(**changes)]))
                self.assertEqual(result["status"], "validation_error")
                self.assertEqual(result["currency_groups"], [])
                self.assertEqual(result["data_quality"]["invalid_rows"], 1)

    def test_duplicate_borrower_ids_fail_import_without_overwriting_existing_data(self):
        destination = Path(self.temp.name) / "stored.csv"
        destination.write_text("existing-valid-file", encoding="utf-8")
        self.write([self.row(), self.row()])
        with self.assertRaises(ValueError):
            impact.import_outcomes(self.path, destination)
        self.assertEqual(destination.read_text(encoding="utf-8"), "existing-valid-file")
        self.assertEqual(impact.analyze_outcomes(self.path)["currency_groups"], [])

    def test_import_normalizes_annual_values_and_reproduces_results(self):
        destination = Path(self.temp.name) / "stored.csv"
        self.write([self.row(income_period="annual", household_income_baseline=12000,
                             household_income_followup=18000)])
        result = impact.import_outcomes(self.path, destination)
        self.assertEqual(result["currency_groups"][0]["household_income"]["mean_change"], 500)
        with destination.open(encoding="utf-8") as handle:
            stored = list(csv.DictReader(handle))[0]
        self.assertEqual(stored["income_period"], "monthly")
        self.assertEqual(float(stored["household_income_baseline"]), 1000)

    def test_zero_baseline_has_no_undefined_percent_and_zero_due_has_no_rate(self):
        result = impact.analyze_outcomes(self.write([self.row(household_income_baseline=0,
                                                              installments_due=0, installments_paid_on_time=0)]))
        group = result["currency_groups"][0]
        self.assertEqual(group["household_income"]["mean_change"], 1500)
        self.assertIsNone(group["household_income"]["mean_individual_percent_change"])
        self.assertIsNone(group["repayment"]["on_time_ratio"])
        json.dumps(result, allow_nan=False)

    def test_incorrect_schema_rejected(self):
        self.path.write_text("borrower_id,income\nSYNTHETIC-001,100\n", encoding="utf-8")
        self.assertEqual(impact.analyze_outcomes(self.path)["status"], "validation_error")


if __name__ == "__main__":
    unittest.main()
