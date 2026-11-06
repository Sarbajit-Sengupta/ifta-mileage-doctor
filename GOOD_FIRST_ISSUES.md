# Good first issues

Seeded issues for new contributors. File each one on GitHub with the
`good first issue` and `help wanted` labels.

## 1. Accept CSV trip and fuel logs

Title: Accept CSV trip and fuel logs in addition to JSON

Description: Many fleets keep trip and fuel logs in spreadsheets
that export CSV, not JSON. Accept a CSV file for trips (columns
`state`, `miles`) and for fuel (columns `state`, `gallons`) when the
file ends in `.csv`, and produce exactly the same return as the
JSON path. The JSON behavior must not change.

Difficulty: easy

Acceptance criteria:

* A CSV trips file and a CSV fuel file with the sample data produce
  the same return totals as the JSON sample.
* A CSV row with a bad state code exits 2 with the entry in the
  error, just like the JSON path.
* An empty CSV (header row only) for trips exits 2, because total
  miles is zero and fleet MPG cannot be computed.
* A test covers the CSV path and the bad state code case.
* The README documents the CSV columns and the `.csv` detection.

## 2. Add a --format csv option for the per-state table

Title: Add --format csv to emit the per-state table as CSV

Description: The text report is for humans, but accountants paste
returns into spreadsheets. Add `--format csv`, which prints the
per-state table as CSV with a header row (state, miles,
taxable_gallons, tax_paid_gallons, net_gallons, rate, tax_due) and
one row per state, plus a total row. The JSON output must not
change, and the default text output must not change.

Difficulty: easy

Acceptance criteria:

* `--format csv` prints a header row and one row per state, in
  state code order, with a total row last.
* A state with a missing rate prints an empty rate and tax due
  field in its CSV row.
* Without `--format csv`, output is unchanged.
* An invalid `--format` value exits 2 with a clear message.
* Tests cover the CSV shape and the unchanged default output.
* The README documents the new flag.

## 3. Warn when taxable gallons do not sum to total fuel

Title: Report a rounding drift warning when taxable gallons drift from total fuel

Description: Taxable gallons are rounded to two decimals per state,
so in an unlucky quarter their sum can differ from total fuel by a
cent or two of gallons. Add a warning line in text output (and a
`warnings` list in JSON output) whenever the sum of per-state
taxable gallons differs from total fuel gallons, naming the drift
amount. Do not change any totals in this issue.

Difficulty: medium

Acceptance criteria:

* A quarter where per-state rounding drifts from total fuel shows
  a warning naming the drift in gallons.
* The sample quarter, where the sum matches exactly, shows no
  warning.
* The JSON output carries the warnings list, empty when there is
  no drift.
* Totals are unchanged by the warning.
* Tests cover the drift case and the no-drift case.
* The README documents the warning.

## 4. Add a per-quarter comparison mode

Title: Add --compare to show this quarter against last quarter

Description: Carriers compare quarters to spot a rate change or a
fuel buying shift. Add `--compare` taking a second set of trips,
fuel, and rates files for the previous quarter (for example
`--compare prev-trips.json --compare-fuel prev-fuel.json
--compare-rates prev-rates.json`), and print a second table after
the return showing, per state, this quarter's tax due, last
quarter's tax due, and the difference, plus a grand total
difference row. The existing return must not change.

Difficulty: medium

Acceptance criteria:

* A comparison against the sample quarter itself shows zero
  differences in every row.
* A comparison with different rates shows the correct per-state
  differences and grand total difference.
* A missing rate in either quarter is reported the same way as in
  the main return, and the comparison does not crash.
* Tests cover the identical-quarter case and a changed-rate case.
* The README documents the new flags.
