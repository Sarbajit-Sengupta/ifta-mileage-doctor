# Changelog

## 1.0.0 - 2026-11-06

Initial release.

* Reads a quarterly trip log (miles by state), a fuel purchase log
  (gallons by state), and a rates file (tax rate per gallon by
  state), all JSON, and builds an IFTA quarterly return.
* Fleet MPG from total miles over total fuel gallons, taxable
  gallons per state from state miles over fleet MPG, net gallons
  after tax-paid fuel, and tax due or credit per state with a grand
  total.
* Decimal math for all miles, gallons, and money, so float errors
  never leak into a return.
* Text and `--json` output, `--check` CI gate (exit 1 on a missing
  rate for a state with miles, or on fuel purchased in a state with
  no miles), `--quarter` label, `--state` filter, and trips from a
  file or stdin.
* Clear exit 2 errors on stderr for missing files, invalid JSON,
  wrong shapes, negative miles, gallons, or rates, bad state codes,
  and zero total miles or fuel.
* Zero dependencies, Python 3.10 or newer.
