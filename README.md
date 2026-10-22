# PP1 Finale — Microloan Atlas

**PI-15: Analyzing the Impact of Micro-Loans on Poverty Alleviation Using NLP and Clustering**

The upgraded Phase 1 Flask project combines the supplied data with indexed research, account-owned applications, explainable demo assessments, payment recording and a local evidence assistant. It supports a reproducible academic workflow. No measured poverty reduction or real lender approval is claimed.

## Run locally

Use Python 3.11–3.14. The delivered folder contains the prepared database and research results; no rebuild is needed for normal use.

```bash
cd "/path/to/PP1 Finale"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**, choose **Create account**, then sign in to save applications and access your history. No account or password is bundled. On Windows, activate `.venv` using its `Scripts/activate` command and use `py` if `python3` is unavailable. `PORT` changes the local port. The lock file records the exact validation environment; `requirements.txt` allows cross-platform dependency resolution.

No external chat API key, spaCy model download or CDN is required. OCR additionally needs the Tesseract executable on PATH; English/Hindi language files are supplied. Typed descriptions work without Tesseract. See [operations and authentication](docs/operations_and_auth.md) for settings, backup, imports and deployment limits.

## Try the corrected workflow

1. Register and open **Application**. Use fictional details for a demonstration.
2. Enter: **“I need a loan to open a milk business in Bengaluru of around 10000 rupees.”** Specify a requested term, monthly income and existing monthly installment commitments.
3. Read the rule explanations. This narrative identifies purpose, location and amount, but supplies no business sales or costs. Annual revenue and surplus remain **Not provided**. No quantity, yield, price or income is invented.
4. If both monthly business revenue and monthly business costs are entered, the assessment annualizes those declarations. This is arithmetic from inputs, not a growth prediction.
5. Open **Explanation**, explore the same loan category and business records, download JSON/PDF, and return through **My applications** after signing in again.
6. To demonstrate tracking, use a clearly fictional test record. In real use, record a disbursement only after it occurred, confirm actual agreement terms, then enter payments or import their CSV. Recording never transfers money or verifies bank settlement.

## What is included

| Area | Implementation |
|---|---|
| Sources | Full loan-archive scan, deterministic 12,000-record research sample, all usable supplied market/farm/dairy rows and provenance |
| Storage | Indexed research tables and bounded read pool; separate account/application/payment tables with a bounded write pool and transactions |
| Research | Standardized KMeans, k=2..6 comparison, silhouette/Davies–Bouldin, TF-IDF + NMF themes, heuristic sentiment and defined outcome cohorts |
| Assessment | All 14 source loan purposes, farm/dairy context, source counts/locality scope, explicit input provenance and missing-information states |
| Demo policy | Configurable rate, default/requested term and debt-burden threshold; no automatic approval or demographic/sentiment risk score |
| Personal records | Account-owned history, explanations, canonical JSON, on-demand PDF, confirmed agreement schedule and manual payment ledger |
| Frontend/chat | Responsive pages, deferred/versioned scripts, lazy images/data/chat code, pagination and local evidence/navigation answers |
| Household outcomes | Validated CSV import and paired changes; header-only template until genuine observations are supplied |
| Review package | [Topic/rubric audit](docs/topic_and_rubric_audit.md), [paper draft](docs/research_paper_draft.md), Gantt/risks, SDG linkage and viva/submission material |

## Policy and currency

Defaults are **12% annual interest, 12 months when no term is supplied, and a 40% total-monthly-debt/income ceiling**. Valid user-entered terms are honored. Exact settings/bounds are in [operations](docs/operations_and_auth.md#configuration). Each saved result retains its policy and input provenance.

Statuses are **Ready for review**, **Needs information**, and **Affordability concern**. They explain configured rules and missing inputs; a real lender determines approval and final terms.

Application inputs, displayed research amounts, chat and new reports use INR. Historical foreign-source amounts use **INR 95.2311 per USD, dated 10 September 2026**, published by the [Reserve Bank of India](https://www.rbi.org.in/scripts/BS_NSDPDisplay.aspx). `config/fx.json` records source/date/scope; `PP1_FX_CONFIG` selects another validated file. This is display conversion, not a live quote. Raw sources, database research fields and offline model artifacts retain original units for reproduction. Indian source amounts are not converted twice. Conversion does not make historical US loans representative of Indian borrowers.

## Evidence and its limits

- The source has 2,260,668 valid loan records; the analyzed uniform reservoir is 12,000, seed 42. These are historical US consumer loans. Only 600 sampled descriptions meet the text threshold.
- The market workbook contributes 1,048,575 rows at Excel's row limit; coverage beyond the file is unknown. PP1 Data's identical workbook is counted once. Farm and dairy contribute 3,162 and 4,326 separate context rows.
- Of 7,029 resolved sampled loans, 79.8976% are fully paid. Unresolved loans are excluded. This is not a prediction for an applicant.
- Clustering excludes outcomes and sentiment from its inputs. Cluster IDs are category labels. No held-out sentiment accuracy is established.
- No linked household baseline/follow-up welfare observations or comparison group were supplied. The [household pipeline](docs/household_outcomes_guide.md) shows a missing-data state until genuine measurements are imported.
- User-recorded payments remain account-owned application evidence. They are never inserted into the historical research cohort or treated as verified bank observations.

## Rebuild or add observations

Stop the server before offline preparation, then restart to refresh caches. The importer snapshots an existing database and replaces only research tables, preserving account/application/payment tables. Keep independent backups as described in operations.

```bash
python scripts/prepare_data.py
# If the retained archive is absent:
python scripts/prepare_data.py --loan-source "/path/to/accepted_2007_to_2018Q4.csv.gz"
# Recompute research models from the prepared sample:
python scripts/prepare_data.py --analytics-only
```

A full rebuild streams millions of records and takes several minutes. Source hashes and choices are in `data/source_manifest.json`. Raw files and `legacy/PP1_Data_original.py` are retained for traceability; the old standalone `new.py` CLI is retired.

For household outcomes, fill a copy of `data/templates/household_outcomes.csv`, then run:

```bash
python impact_outcomes.py import "/path/to/completed_outcomes.csv"
python impact_outcomes.py analyze
```

Invalid imports fail before replacing observations. Analysis retains source-currency groups; the web view converts supported amounts to INR and withholds amounts without a configured rate. Paired changes remain descriptive.

## Validation and review

```bash
python -m pytest tests -q
python scripts/benchmark.py
```

[Validation report](docs/validation_report.md), `docs/test_results.xml` and `docs/performance_results.json` record the checked build and workload. Benchmarks measure Flask handling with stated exclusions; they do not guarantee browser latency or production capacity. Phase 1 had no chat endpoint, so no chat speed-up percentage is invented.

The [review package](docs/README.md) identifies remaining external evidence: genuine paper submission/acceptance, original Phase 1 schedule, team contributions, presentation delivery and household data. These are not fabricated or marked complete. Supplied topic/rubric images are in `docs/reference/`.

## Narrative sentiment and interface update

The Your narrative tab shows a sentiment label, polarity, matched keywords and an explanation. A factual request such as “I need to borrow 10,000 rupees for my dairy business” is neutral because it contains no supported positive or negative keywords. This English keyword analysis does not affect loan rates or lending decisions. Existing saved applications receive this annotation when read without recalculating saved loan terms. Navigation uses moving selection pills and brief content transitions, with reduced-motion support, keyboard navigation and browser history.

## Restored local copy

On this Mac, double-click **Start Microloan Atlas.command** in the project folder to start the site at **http://127.0.0.1:5057**. Keep its terminal window open while using the website. The Downloads copy has its own `.venv` environment. For another machine, create a fresh environment using the setup steps above.

The recovery preserved the supplied data and rebuilt the research database. Previously deleted private accounts, applications and payment entries are not recreated from research data. See `docs/recovery_report.md` for recovery scope and checks.
