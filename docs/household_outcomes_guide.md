# Household outcome data: import and analysis

A working pipeline accepts real, linked baseline/follow-up outcomes. No such observations were supplied. The [CSV template](../data/templates/household_outcomes.csv) contains only headers, and the default result is `needs_data` with no invented impact numbers.

## Data schema

Use one row per consenting borrower and a pseudonymous ID. Keep the mapping to real identities outside the public project. All headers must match the template. Unknown numerical measurements are blank; zero means an observed zero.

| Column | Accepted values / meaning |
|---|---|
| `borrower_id` | Required unique pseudonymous identifier, at most 128 characters; one explicit pair per borrower |
| `baseline_date` | Required calendar date, `YYYY-MM-DD` |
| `followup_date` | Required `YYYY-MM-DD`, later than baseline and not in the future |
| `currency` | Explicit uppercase three-letter currency code, e.g. `INR`; confirm the code in source documentation |
| `income_period` | `monthly` or `annual`, applying to all four income fields |
| `household_size_baseline` | Integer 1–100, or blank |
| `household_size_followup` | Integer 1–100, or blank |
| `household_income_baseline` | Finite net household income in the stated currency/period, or blank |
| `household_income_followup` | Same measurement definition as baseline, or blank |
| `business_income_baseline` | Optional finite net livelihood/business income, or blank |
| `business_income_followup` | Same-definition follow-up business income, or blank |
| `installments_due` | Optional nonnegative integer count due within the baseline-to-follow-up window |
| `installments_paid_on_time` | Count of those installments paid by their due date, at most due count. Supply both installment counts or neither |

Income means net income after relevant costs, measured consistently; it may be negative. Annual amounts are divided by 12. Currency groups stay separate, with no exchange-rate or inflation adjustment. Document recall periods, seasonality and measurement methods before interpretation.

## Commands

From the project directory, using the project Python environment:

```bash
python impact_outcomes.py import /absolute/path/to/permissioned_households.csv
python impact_outcomes.py analyze
```

Import validates the complete CSV before atomically saving monthly-normalized rows to `data/household_outcomes.csv`. Any validation error prevents replacement of an existing file. Limits are 32 MiB and 100,000 rows. To inspect without importing:

```bash
python impact_outcomes.py analyze /absolute/path/to/permissioned_households.csv
```

The read-only interface is `impact_outcomes.analyze_outcomes(path=None)`. It returns status `needs_data`, `validation_error`, or `ready`, plus aggregate results, missingness, row errors and limitations. Invalid files receive no partial numerical summaries. Borrower identifiers are omitted from the analytical result.

## Measures and denominators

- **Paired household change:** follow-up minus baseline net income, on complete income pairs.
- **Per-capita change:** follow-up income/follow-up size minus baseline income/baseline size; all four values required.
- **Business-income change:** follow-up minus baseline, on complete business-income pairs.
- **Percentage change:** individual percentage changes averaged only where baseline income is positive. `percent_change_n` reports that denominator; zero/negative baselines remain in absolute-change summaries.
- **On-time ratio:** total paid-on-time installments / total due installments over recorded windows. Zero-due records do not enter that ratio. Borrower and installment counts are shown.
- **Follow-up interval:** minimum, median and maximum elapsed days for each currency group.

Each measure may use a different sample size. Missingness covers included rows; whole-person attrition requires a separate baseline recruitment register. Changes are descriptive. The module does not estimate causality, a poverty threshold, poverty exit, inflation-adjusted welfare, business survival or employment creation.

## Validation

Nine tests in `tests/test_impact_outcomes.py` passed with warnings treated as errors. Temporary synthetic fixtures verify conversions, paired/per-capita arithmetic, missingness, separate currencies, repayment ratios, invalid values/dates, duplicate IDs, import atomicity and the empty template. Synthetic test values are not research observations.
