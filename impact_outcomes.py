"""Validated paired household outcomes for a future permissioned field dataset.

The shipped template contains no observations. This module never derives
household welfare from a loan status, language sentiment or generated data.
Run ``python impact_outcomes.py --help`` for local import/analysis commands.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date

import json
import math
from pathlib import Path
import statistics
import tempfile

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "household_outcomes.csv"
TEMPLATE_PATH = BASE_DIR / "data" / "templates" / "household_outcomes.csv"
MAX_ROWS = 100_000
MAX_FILE_BYTES = 32 * 1024 * 1024
FIELDS = (
    "borrower_id", "baseline_date", "followup_date", "currency", "income_period",
    "household_size_baseline", "household_size_followup",
    "household_income_baseline", "household_income_followup",
    "business_income_baseline", "business_income_followup",
    "installments_due", "installments_paid_on_time",
)
NUMBER_FIELDS = FIELDS[5:]
LIMITATIONS = [
    "Paired changes are descriptive; no untreated comparison group or causal effect is estimated.",
    "Income is self-reported or source-provided net income. Measurement quality, seasonality, inflation and attrition require separate evaluation.",
    "Monthly and annual inputs are normalized to monthly amounts; currencies are analyzed separately without conversion or inflation adjustment.",
    "Per-capita income uses the household size at each observation. Household composition changes can affect it.",
    "A paid-on-time installment ratio is an observed repayment measure, not a poverty measure. No poverty threshold or poverty-exit claim is inferred.",
    "Only borrowers present in the file are counted. Whole-file sample attrition requires a separate baseline recruitment register.",
]


def _number(value, field):
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number or blank") from exc
    if not math.isfinite(result) or abs(result) > 1e12:
        raise ValueError(f"{field} must be finite with absolute value at most 1e12")
    if field.startswith("household_size"):
        if not result.is_integer() or not 1 <= result <= 100:
            raise ValueError(f"{field} must be a whole number from 1 to 100 or blank")
        return int(result)
    if field.startswith("installments_"):
        if not result.is_integer() or not 0 <= result <= 100_000:
            raise ValueError(f"{field} must be a nonnegative whole count at most 100000")
        return int(result)
    # Net household/business income can legitimately be negative.
    return result


def _read(path):
    """Return validated rows and errors. Never emit personal row identifiers."""
    path = Path(path)
    result = {"rows": [], "errors": [], "total_rows": 0, "invalid_rows": 0}
    if not path.is_file():
        return result
    if path.stat().st_size > MAX_FILE_BYTES:
        result["errors"].append({"row": None, "message": "CSV exceeds the 32 MiB limit"})
        return result
    seen = set()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS) or len(reader.fieldnames) != len(FIELDS):
                result["errors"].append({"row": 1, "message": "CSV headers must match the supplied household_outcomes template exactly"})
                return result
            for row in reader:
                result["total_rows"] += 1
                row_number = reader.line_num
                if result["total_rows"] > MAX_ROWS:
                    result["errors"].append({"row": row_number, "message": f"CSV exceeds the {MAX_ROWS} row limit"})
                    break
                try:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("Row has a different number of values from the header")
                    item = {key: str(value).strip() for key, value in row.items()}
                    borrower = item["borrower_id"]
                    if not borrower or len(borrower) > 128:
                        raise ValueError("borrower_id is required and must contain at most 128 characters")
                    if borrower in seen:
                        raise ValueError("Duplicate borrower_id; use one explicit baseline/follow-up pair per borrower")
                    seen.add(borrower)
                    try:
                        baseline = date.fromisoformat(item["baseline_date"])
                        followup = date.fromisoformat(item["followup_date"])
                    except ValueError as exc:
                        raise ValueError("baseline_date and followup_date must be valid YYYY-MM-DD dates") from exc
                    if baseline.isoformat() != item["baseline_date"] or followup.isoformat() != item["followup_date"]:
                        raise ValueError("Dates must use YYYY-MM-DD format")
                    if followup <= baseline:
                        raise ValueError("followup_date must be later than baseline_date")
                    if followup > date.today():
                        raise ValueError("followup_date cannot be in the future for observed outcomes")
                    currency = item["currency"]
                    if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
                        raise ValueError("currency must be an explicit uppercase three-letter currency code")
                    if item["income_period"] not in {"monthly", "annual"}:
                        raise ValueError("income_period must be monthly or annual")
                    for field in NUMBER_FIELDS:
                        item[field] = _number(item[field], field)
                    due, paid = item["installments_due"], item["installments_paid_on_time"]
                    if (due is None) != (paid is None):
                        raise ValueError("Supply both installment counts, or leave both blank")
                    if due is not None and paid > due:
                        raise ValueError("installments_paid_on_time cannot exceed installments_due")
                    item["followup_days"] = (followup - baseline).days
                    if item["income_period"] == "annual":
                        for field in NUMBER_FIELDS:
                            if "income_" in field and item[field] is not None:
                                item[field] /= 12
                    item["income_period"] = "monthly"
                    result["rows"].append(item)
                except ValueError as exc:
                    result["invalid_rows"] += 1
                    if len(result["errors"]) < 100:
                        result["errors"].append({"row": row_number, "message": str(exc)})
    except (OSError, UnicodeError, csv.Error) as exc:
        result["errors"].append({"row": None, "message": f"Unable to parse CSV ({type(exc).__name__})"})
    return result


def _rounded(value):
    return round(float(value), 4) if value is not None else None


def _paired_summary(pairs):
    if not pairs:
        return {"paired_n": 0, "mean_baseline": None, "mean_followup": None,
                "mean_change": None, "median_change": None,
                "increased_n": 0, "unchanged_n": 0, "decreased_n": 0,
                "mean_individual_percent_change": None, "percent_change_n": 0}
    changes = [after - before for before, after in pairs]
    percentages = [100 * (after - before) / before for before, after in pairs if before > 0]
    return {
        "paired_n": len(pairs),
        "mean_baseline": _rounded(statistics.mean(before for before, _ in pairs)),
        "mean_followup": _rounded(statistics.mean(after for _, after in pairs)),
        "mean_change": _rounded(statistics.mean(changes)),
        "median_change": _rounded(statistics.median(changes)),
        "increased_n": sum(value > 1e-9 for value in changes),
        "unchanged_n": sum(abs(value) <= 1e-9 for value in changes),
        "decreased_n": sum(value < -1e-9 for value in changes),
        "mean_individual_percent_change": _rounded(statistics.mean(percentages)) if percentages else None,
        "percent_change_n": len(percentages),
    }


def _summarize_currency(rows, currency):
    household, per_capita, business = [], [], []
    repayment = []
    for row in rows:
        before, after = row["household_income_baseline"], row["household_income_followup"]
        if before is not None and after is not None:
            household.append((before, after))
            size_before, size_after = row["household_size_baseline"], row["household_size_followup"]
            if size_before is not None and size_after is not None:
                per_capita.append((before / size_before, after / size_after))
        before_business, after_business = row["business_income_baseline"], row["business_income_followup"]
        if before_business is not None and after_business is not None:
            business.append((before_business, after_business))
        if row["installments_due"] is not None and row["installments_due"] > 0:
            repayment.append((row["installments_due"], row["installments_paid_on_time"]))
    due = sum(item[0] for item in repayment)
    paid = sum(item[1] for item in repayment)
    return {
        "currency": currency, "income_unit": f"{currency} per month", "record_count": len(rows),
        "household_income": _paired_summary(household),
        "per_capita_household_income": _paired_summary(per_capita),
        "business_income": _paired_summary(business),
        "repayment": {"borrowers_with_due_installments": len(repayment),
                      "installments_due": due, "installments_paid_on_time": paid,
                      "on_time_ratio": _rounded(paid / due) if due else None,
                      "definition": "Sum paid on time / sum due during each recorded baseline-to-follow-up window; weighted by installments, not by borrower."},
        "followup_days": {"minimum": min(row["followup_days"] for row in rows),
                          "median": statistics.median(row["followup_days"] for row in rows),
                          "maximum": max(row["followup_days"] for row in rows)},
    }


def analyze_outcomes(path=None):
    """Return safe aggregate paired changes, or needs_data/validation_error.

    Invalid files produce no numerical group results. Valid missing cells are
    reported explicitly; each measure uses its own complete-pair denominator.
    The function reads local CSV only and never writes or publishes anything.
    """
    path = Path(path) if path is not None else DEFAULT_DATA_PATH
    loaded = _read(path)
    rows = loaded["rows"]
    quality = {
        "rows_read": loaded["total_rows"], "valid_rows": len(rows),
        "invalid_rows": loaded["invalid_rows"],
        "missing_values": {field: sum(row[field] is None for row in rows) for field in NUMBER_FIELDS},
        "complete_household_pairs": sum(row["household_income_baseline"] is not None and row["household_income_followup"] is not None for row in rows),
        "incomplete_household_pairs": sum(row["household_income_baseline"] is None or row["household_income_followup"] is None for row in rows),
    }
    status = "validation_error" if loaded["errors"] else "ready" if rows else "needs_data"
    result = {
        "status": status, "available": status == "ready",
        "source": path.name, "template": "data/templates/household_outcomes.csv",
        "method": "Descriptive matched baseline/follow-up analysis; one row per borrower",
        "data_quality": quality, "errors": loaded["errors"],
        "currency_groups": [], "limitations": list(LIMITATIONS),
    }
    if status == "ready":
        result["currency_groups"] = [
            _summarize_currency([row for row in rows if row["currency"] == currency], currency)
            for currency in sorted({row["currency"] for row in rows})
        ]
        result["message"] = "Validated records are loaded. Check each measure's complete-pair denominator; any calculated change is descriptive and does not establish that lending caused it."
    elif status == "needs_data":
        result["message"] = "No household observations supplied. Fill the header-only template with permissioned linked baseline/follow-up records, then run the local import command. No impact result has been invented."
    else:
        result["message"] = "Fix the listed CSV validation errors and re-import. Numerical outcomes are withheld for an invalid file."
    return result


def import_outcomes(source_path, destination_path=None):
    """Validate and atomically save normalized rows; never accept a partial file."""
    source_path = Path(source_path)
    if not source_path.is_file():
        raise ValueError("Source CSV does not exist")
    loaded = _read(source_path)
    if loaded["errors"]:
        raise ValueError("CSV validation failed: " + "; ".join(error["message"] for error in loaded["errors"][:5]))
    if not loaded["rows"]:
        raise ValueError("Source CSV contains no household observations")
    destination = Path(destination_path) if destination_path is not None else DEFAULT_DATA_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".csv", dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(loaded["rows"])
        temporary.replace(destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return analyze_outcomes(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Read household CSV and print aggregate results")
    analyze.add_argument("path", nargs="?", type=Path, default=DEFAULT_DATA_PATH)
    ingest = subparsers.add_parser("import", help="Validate and save a permissioned household CSV")
    ingest.add_argument("path", type=Path)
    ingest.add_argument("--destination", type=Path, default=DEFAULT_DATA_PATH)
    args = parser.parse_args()
    try:
        result = import_outcomes(args.path, args.destination) if args.command == "import" else analyze_outcomes(args.path)
    except ValueError as exc:
        parser.exit(2, f"Import failed: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 1 if result["status"] == "validation_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
