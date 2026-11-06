"""Tests for ifta_mileage_doctor. Runnable with unittest or pytest."""

import json
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ifta_mileage_doctor import (
    InputError,
    build_return,
    check_reasons,
    load_fuel,
    load_rates,
    load_trips,
    main,
)

ROOT = Path(__file__).resolve().parent.parent


def sample_return():
    trips = json.loads((ROOT / "examples" / "trips.json").read_text())
    fuel = json.loads((ROOT / "examples" / "fuel.json").read_text())
    rates = json.loads((ROOT / "examples" / "rates.json").read_text())
    return build_return(load_trips(json.dumps(trips)),
                        load_fuel(json.dumps(fuel)),
                        load_rates(json.dumps(rates)),
                        quarter="2026-Q3")


class TestSampleReturn(unittest.TestCase):
    def test_fleet_mpg_and_totals(self):
        result = sample_return()
        self.assertEqual(result["fleet_mpg"], Decimal("8.00"))
        self.assertEqual(result["total_miles"], Decimal("4800"))
        self.assertEqual(result["total_gallons"], Decimal("600"))
        self.assertEqual(result["total_taxable_gallons"], Decimal("600.00"))
        self.assertEqual(result["total_net_gallons"], Decimal("0.00"))

    def test_taxable_gallons_per_state(self):
        result = sample_return()
        taxable = {s: e["taxable_gallons"] for s, e in result["states"].items()}
        self.assertEqual(taxable, {
            "AZ": Decimal("75.00"),
            "NM": Decimal("75.00"),
            "OK": Decimal("150.00"),
            "TX": Decimal("300.00"),
        })

    def test_net_gallons_per_state(self):
        result = sample_return()
        net = {s: e["net_gallons"] for s, e in result["states"].items()}
        self.assertEqual(net, {
            "AZ": Decimal("-15.00"),
            "NM": Decimal("15.00"),
            "OK": Decimal("-20.00"),
            "TX": Decimal("20.00"),
        })

    def test_tax_due_per_state(self):
        result = sample_return()
        tax = {s: e["tax_due"] for s, e in result["states"].items()}
        self.assertEqual(tax, {
            "AZ": Decimal("-3.90"),
            "NM": Decimal("3.15"),
            "OK": Decimal("-3.80"),
            "TX": Decimal("4.00"),
        })

    def test_grand_total_is_credit(self):
        result = sample_return()
        self.assertEqual(result["grand_total_tax"], Decimal("-0.55"))
        self.assertEqual(result["missing_rates"], [])
        self.assertEqual(result["unaccounted_fuel_states"], [])


class TestMpgMath(unittest.TestCase):
    def test_non_exact_mpg_uses_unrounded_mpg(self):
        result = build_return(
            load_trips(json.dumps([{"state": "TX", "miles": 2400},
                                   {"state": "OK", "miles": 1200},
                                   {"state": "NM", "miles": 600},
                                   {"state": "AZ", "miles": 800}])),
            load_fuel(json.dumps([{"state": "TX", "gallons": 300},
                                  {"state": "OK", "gallons": 150},
                                  {"state": "NM", "gallons": 50},
                                  {"state": "AZ", "gallons": 100}])),
            load_rates(json.dumps({"TX": "0.20", "OK": "0.19",
                                   "NM": "0.21", "AZ": "0.26"})))
        self.assertEqual(result["fleet_mpg"], Decimal("8.33"))
        self.assertEqual(result["states"]["TX"]["taxable_gallons"], Decimal("288.00"))
        self.assertEqual(result["total_taxable_gallons"], Decimal("600.00"))

    def test_decimal_cents_math(self):
        result = build_return(
            load_trips(json.dumps([{"state": "TX", "miles": "0.10"},
                                   {"state": "OK", "miles": "0.20"}])),
            load_fuel(json.dumps([{"state": "TX", "gallons": "0.30"}])),
            load_rates(json.dumps({"TX": "0.20", "OK": "0.20"})))
        self.assertEqual(result["total_miles"], Decimal("0.30"))

    def test_duplicate_state_entries_are_summed(self):
        result = build_return(
            load_trips(json.dumps([{"state": "TX", "miles": 1000},
                                   {"state": "TX", "miles": 500}])),
            load_fuel(json.dumps([{"state": "TX", "gallons": 100},
                                  {"state": "tx", "gallons": 50}])),
            load_rates(json.dumps({"TX": "0.20"})))
        self.assertEqual(result["states"]["TX"]["miles"], Decimal("1500"))
        self.assertEqual(result["states"]["TX"]["tax_paid_gallons"], Decimal("150"))

    def test_lowercase_state_codes_normalized(self):
        result = build_return(
            load_trips(json.dumps([{"state": "tx", "miles": 800}])),
            load_fuel(json.dumps([{"state": "tx", "gallons": 100}])),
            load_rates(json.dumps({"tx": "0.20"})))
        self.assertIn("TX", result["states"])
        self.assertEqual(result["states"]["TX"]["tax_due"], Decimal("0.00"))

    def test_object_wrappers(self):
        result = build_return(
            load_trips(json.dumps({"trips": [{"state": "TX", "miles": 800}]})),
            load_fuel(json.dumps({"fuel": [{"state": "TX", "gallons": 100}]})),
            load_rates(json.dumps({"rates": [{"state": "TX", "rate": "0.20"}]})))
        self.assertEqual(result["fleet_mpg"], Decimal("8.00"))

    def test_rates_list_form(self):
        rates = load_rates(json.dumps([{"state": "TX", "rate": 0.2}]))
        self.assertEqual(rates, {"TX": Decimal("0.2")})


class TestCheckLogic(unittest.TestCase):
    def test_missing_rate_is_check_failure(self):
        rates = json.loads((ROOT / "examples" / "rates-missing.json").read_text())
        trips = json.loads((ROOT / "examples" / "trips.json").read_text())
        fuel = json.loads((ROOT / "examples" / "fuel.json").read_text())
        result = build_return(load_trips(json.dumps(trips)),
                              load_fuel(json.dumps(fuel)),
                              load_rates(json.dumps(rates)))
        self.assertEqual(result["missing_rates"], ["AZ"])
        self.assertIsNone(result["states"]["AZ"]["tax_due"])
        self.assertIsNone(result["grand_total_tax"])
        reasons = check_reasons(result)
        self.assertEqual(len(reasons), 1)
        self.assertIn("AZ", reasons[0])

    def test_unaccounted_fuel_state_is_check_failure(self):
        trips = json.loads((ROOT / "examples" / "trips.json").read_text())
        fuel = json.loads((ROOT / "examples" / "fuel-unaccounted.json").read_text())
        rates = json.loads((ROOT / "examples" / "rates.json").read_text())
        rates["WY"] = "0.24"
        result = build_return(load_trips(json.dumps(trips)),
                              load_fuel(json.dumps(fuel)),
                              load_rates(json.dumps(rates)))
        self.assertEqual(result["unaccounted_fuel_states"], ["WY"])
        self.assertEqual(result["states"]["WY"]["net_gallons"], Decimal("-40.00"))
        reasons = check_reasons(result)
        self.assertEqual(len(reasons), 1)
        self.assertIn("WY", reasons[0])

    def test_unaccounted_fuel_state_without_rate_has_no_tax_due(self):
        trips = json.loads((ROOT / "examples" / "trips.json").read_text())
        fuel = json.loads((ROOT / "examples" / "fuel-unaccounted.json").read_text())
        rates = json.loads((ROOT / "examples" / "rates.json").read_text())
        result = build_return(load_trips(json.dumps(trips)),
                              load_fuel(json.dumps(fuel)),
                              load_rates(json.dumps(rates)))
        self.assertIsNone(result["states"]["WY"]["tax_due"])
        self.assertIsNone(result["grand_total_tax"])

    def test_clean_return_has_no_check_reasons(self):
        self.assertEqual(check_reasons(sample_return()), [])


class TestValidation(unittest.TestCase):
    def test_negative_miles_rejected(self):
        with self.assertRaises(InputError):
            load_trips(json.dumps([{"state": "TX", "miles": -50}]))

    def test_negative_gallons_rejected(self):
        with self.assertRaises(InputError):
            load_fuel(json.dumps([{"state": "TX", "gallons": "-1"}]))

    def test_negative_rate_rejected(self):
        with self.assertRaises(InputError):
            load_rates(json.dumps({"TX": -0.2}))

    def test_bad_state_code_rejected(self):
        with self.assertRaises(InputError):
            load_trips(json.dumps([{"state": "TEXAS", "miles": 100}]))

    def test_missing_miles_field(self):
        with self.assertRaises(InputError):
            load_trips(json.dumps([{"state": "TX"}]))

    def test_missing_gallons_field(self):
        with self.assertRaises(InputError):
            load_fuel(json.dumps([{"state": "TX"}]))

    def test_invalid_json(self):
        with self.assertRaises(InputError):
            load_trips("{not json")

    def test_wrong_top_level(self):
        with self.assertRaises(InputError):
            load_trips(json.dumps({"nope": []}))

    def test_zero_total_miles_rejected(self):
        with self.assertRaises(InputError):
            build_return({}, {"TX": Decimal("100")}, {"TX": Decimal("0.20")})

    def test_zero_total_gallons_rejected(self):
        with self.assertRaises(InputError):
            build_return({"TX": Decimal("100")}, {}, {"TX": Decimal("0.20")})


class TestCli(unittest.TestCase):
    def run_cli(self, *args, stdin_data=None):
        cmd = [sys.executable, "ifta_mileage_doctor.py", *args]
        return subprocess.run(cmd, cwd=ROOT, input=stdin_data, text=True,
                              capture_output=True, check=False)

    def base_args(self):
        return ["examples/trips.json", "--fuel", "examples/fuel.json",
                "--rates", "examples/rates.json"]

    def test_text_output_contains_totals(self):
        result = self.run_cli(*self.base_args(), "--quarter", "2026-Q3")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Fleet MPG: 8.00", result.stdout)
        self.assertIn("Grand total tax due: -0.55", result.stdout)
        self.assertIn("TX", result.stdout)
        self.assertIn("2026-Q3", result.stdout)

    def test_json_output_shape(self):
        result = self.run_cli(*self.base_args(), "--quarter", "2026-Q3", "--json")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["fleet_mpg"], "8.00")
        self.assertEqual(data["grand_total_tax"], "-0.55")
        self.assertEqual(data["states"]["TX"]["tax_due"], "4.00")
        self.assertEqual(data["states"]["AZ"]["net_gallons"], "-15.00")

    def test_check_passes_on_clean_sample(self):
        result = self.run_cli(*self.base_args(), "--check")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CHECK PASSED", result.stdout)

    def test_check_fails_on_missing_rate(self):
        result = self.run_cli("examples/trips.json", "--fuel", "examples/fuel.json",
                              "--rates", "examples/rates-missing.json", "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CHECK FAILED", result.stdout)
        self.assertIn("AZ", result.stdout)

    def test_check_fails_on_unaccounted_fuel(self):
        result = self.run_cli("examples/trips.json", "--fuel",
                              "examples/fuel-unaccounted.json",
                              "--rates", "examples/rates.json", "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CHECK FAILED", result.stdout)
        self.assertIn("WY", result.stdout)

    def test_state_filter(self):
        result = self.run_cli(*self.base_args(), "--state", "TX")
        self.assertEqual(result.returncode, 0)
        self.assertIn("TX", result.stdout)
        self.assertNotIn("OK", result.stdout)
        self.assertIn("4.00", result.stdout)
        self.assertIn("Fleet MPG: 8.00 (fleet-wide: 4800.00 miles / 600.00 gallons)",
                      result.stdout)

    def test_stdin_trips(self):
        trips = (ROOT / "examples" / "trips.json").read_text()
        result = self.run_cli("-", "--fuel", "examples/fuel.json",
                              "--rates", "examples/rates.json", stdin_data=trips)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Fleet MPG: 8.00", result.stdout)

    def test_module_run(self):
        result = subprocess.run(
            [sys.executable, "-m", "ifta_mileage_doctor", *self.base_args()],
            cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Fleet MPG: 8.00", result.stdout)

    def test_invalid_file_exits_2(self):
        result = self.run_cli("examples/invalid.json", "--fuel", "examples/fuel.json",
                              "--rates", "examples/rates.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_missing_file_exits_2(self):
        result = self.run_cli("examples/nope.json", "--fuel", "examples/fuel.json",
                              "--rates", "examples/rates.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_missing_rates_flag_exits_2(self):
        result = self.run_cli("examples/trips.json", "--fuel", "examples/fuel.json")
        self.assertEqual(result.returncode, 2)

    def test_bad_state_filter_exits_2(self):
        result = self.run_cli(*self.base_args(), "--state", "TEXAS")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
