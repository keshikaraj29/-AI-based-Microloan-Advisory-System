# Revision 3 validation report

Validated 16 September 2026 on macOS / Python 3.14.2. The project was tested in an isolated copy of the prepared database. Synthetic accounts, applications and payments were not written to the delivered research database.

## Sentiment and interface update

New and previously saved applications now expose narrative sentiment, polarity and matched keywords using the same fixed English lexicon and negation rules as the research corpus. The exact dairy request is Neutral (0), with the lack of emotional keywords explained. Existing saved assessment JSON and financial calculations are not rewritten; sentiment is derived when those records are read. New assessments persist the annotation. No loan rate or review decision uses sentiment.

The interface now uses brighter blue, violet and teal accents, sliding navigation pills, and short tab-panel transitions. Keyboard navigation, rapid selection changes, browser Back and reduced-motion code paths were reviewed. Main navigation and tab indicators were checked in the actual browser; existing saved assessments display the sentiment card.

## Automated validation

**159 tests passed, plus 12 subtests.** The current full run completed in 15.53 seconds. The machine-readable result is [test_results.xml](test_results.xml).

```bash
python -m pytest tests -q --junitxml=docs/test_results.xml
```

Coverage includes:

- The exact requested milk-business narrative extracts INR 10,000, identifies dairy/small business and Bengaluru, and leaves income, sales, costs, profit and growth unknown unless explicitly provided.
- All source loan purposes are recognized. Unknown purposes require clarification. Applicant-selected terms drive the schedule; there is no fallback principal, quantity, yield, price or business margin.
- EMI reconciles principal and interest, including zero interest and final-installment rounding. Annual cash calculations use scheduled payments during the first year.
- Password authentication, account isolation, persistent application JSON, canonical research-compatible fields, private JSON/PDF downloads, CSRF validation and safe redirects.
- Confirmed agreement terms are separate from the original assessment. Payment tracking covers month-end dates, overdue and partial installments, unique references, concurrent submissions, final paisa settlement, backdated allocation and atomic CSV validation.
- Research category counts match SQL. INR conversion is repeat-safe, native INR values remain unchanged, and source records are preserved. Business explorers paginate and filter exact source values; unverified farm price units are withheld.
- Bounded database pools and query-plan indexes; WAL-aware backups and account/payment preservation during research preparation; concurrent importer locking.
- Atlas intent routing, including the word “generated”, research repayment-rate questions, applicant explanations and malformed request handling.
- Invalid form entries retain typed values. Invalid operator configuration and malformed redirect targets produce controlled responses.
- PDF generation, text checks, schedule totals and missing-input explanations.

## Browser checks

Verified on the actual local Flask/Waitress preview using a separate test database:

1. Register an account and submit the exact milk-business example with no financial assumptions.
2. Review Overview and Cash flow panels: missing amounts are “Not provided”; no INR 63,000 forecast appears.
3. Open the application explanation in a new browser tab. Confirm small-business corpus context and the explicitly labeled Karnataka dairy fallback.
4. Open same-category research: 135 small-business records and 14 eligible narratives. Source-population and global-model limitations remain explicit.
5. Switch research tabs using click and arrow keys; only the selected panel is displayed. Hash links persist the selected panel. Assessment, explanation and tracking use the same tab mechanism.
6. Browse dairy Milk records, filter Karnataka to 26 records, and paginate to the second page. Dataset amounts are in INR, with source units displayed.
7. Record a synthetic actual agreement at 10% on INR 10,000. Record one INR 879.16 payment and import two more via CSV. Ledger total paid becomes INR 2,637.48; outstanding becomes INR 7,912.41 under the recorded fixed schedule.
8. Ask Atlas about interest: it distinguishes the recorded 10% agreement from the original 12% demo estimate and supplies relevant navigation links.
9. Inspect browser error logs: no console warnings/errors were observed in these workflows.

Desktop rendering was checked at 1280 × 720. The sentiment update was also checked at effective widths of 390 and 519 pixels with no document overflow. At 519 pixels, the research tabs selected one panel and the navigation pill aligned with the active tab. Keyboard Arrow/Home/End navigation, research-category restoration through browser Back, and main-navigation restoration were verified. Temporary viewport overrides were cleared afterwards.

## PDF visual validation

The five-page [milk-business example](examples/milk_business_assessment.pdf) was rendered and inspected page by page. It has readable missing-input notices, a repayment-composition chart, principal-balance chart, source context, input provenance and a complete reconciled schedule. It is clearly labeled as a synthetic demonstration. The source example does not supply income, debt, sales or operating costs.

## Performance

[performance_results.json](performance_results.json) records the reproducible Flask-client benchmark. Forty warm requests were measured per research/chat endpoint, and ten per authenticated application submission.

| Endpoint/workflow | Warm median | Warm p95 |
|---|---:|---:|
| Research summary | 0.463 ms | 0.523 ms |
| Borrower page | 0.297 ms | 0.358 ms |
| Atlas dataset guidance | 0.401 ms | 0.505 ms |
| Atlas cluster guidance | 0.393 ms | 0.427 ms |
| Save application | 2.416 ms | 3.139 ms |

These are local, in-process timings, not browser/network latency. The first application call in the rebuilt environment took about 10.19 seconds, including initial scientific-library imports and font-cache preparation. Warm requests use the cached runtime. Chat uses local guidance and precomputed research; no cloud LLM is called. No before/after speed-up percentage is claimed because Phase 1 had no chat endpoint. PDF/OCR time is excluded from these numbers.

## Delivered data integrity

- Loan research sample: 12,000 records from 2,260,668 valid source rows.
- Market prices: 1,048,575 records; farm: 3,162; dairy: 4,326.
- Delivered users, applications and payments: zero synthetic records.
- SQLite quick check: `ok`; foreign-key violations: none; WAL checkpoint completed.
- Recovery on 16 September rebuilt the research data from the surviving supplied files. The source corpus counts and research metrics match the earlier run. Deleted private account/application data was not reconstructed; see [recovery_report.md](recovery_report.md).

## Practical limits

This is an academic application with production safeguards, not a validated bank underwriting service. Payments reflect manual entries, not verified bank settlements. Rates and review criteria use the configurable demo policy authorized by the user. Actual lender offers, representative borrower outcomes, external paper submission and production security/deployment review remain external requirements. The optional OCR executable must be installed separately. See [operations_and_auth.md](operations_and_auth.md).

Stop and restart the server around offline research preparation so the database and precomputed summary remain on the same version. Research rebuilds preserve the application tables and create a database backup.

## Recovery verification

After the accidental deletion, the restored source passed the complete 159-test suite plus 12 subtests in 15.53 seconds. All 11 Jinja templates parsed. The five-page sample PDF was regenerated and every page visually inspected. The data rebuild passed SQLite integrity checks. The earlier browser checks above remain historical evidence; live checks of the restored website are recorded in the recovery report.
