# Changes from the supplied Phase 1 baseline

## Preserved

The Flask overview → application → assessment → report flow; original farm/dairy/market source files; local OCR language files and images. An unmodified Phase 1 folder backup accompanies the delivered project. The old exploratory analytics and additional PP1 Data script are retained under `legacy/` for traceability.

## Added and corrected

1. Prepared and indexed all usable supplied market records, imported contextual CSVs and retained the supplied compressed loan archive. Scanned the full loan archive for a deterministic 12,000-record research sample.
2. Added offline corpus clustering/NLP/outcome comparisons with methods, source hashes, denominators and explicit data limitations. Removed synthetic borrower rows and arbitrary numeric cluster-ID correlations from the active web workflow.
3. Added local research and chat APIs, connection pooling, cached results, bounded pagination, deferred/versioned scripts, lazy data/images/chat loading and on-demand PDF generation.
4. Redesigned overview, form, results and research dashboard with responsive layouts, keyboard controls and meaningful loading/error/empty states.
5. Replaced unsupported business forecasts with explicit monthly revenue/cost annualization only. Missing values stay missing; amounts and requested terms have validated provenance. All 14 supplied loan purposes plus farm/dairy context are supported.
6. Added a configurable demo policy with rule traces and Ready for review / Needs information / Affordability concern states. Age, gender, card ownership and sentiment do not set a credit score or interest rate.
7. Added persistent account-owned application history, explanations, canonical JSON and a multi-page PDF with repayment charts and schedules. Added manual agreement/payment recording with integer-paise accounting, idempotent references and atomic CSV imports. No funds move and no bank settlement is assumed.
8. Standardized active monetary displays to INR using the dated RBI conversion in `config/fx.json`, while preserving original research units internally. Actual Indian-source units/locality match scope remain visible.
9. Added a validated real-household-outcome import path; no outcome values were fabricated.
10. Added tests, measured performance, a cited paper draft, completeness audit, plan/Gantt/risks, SDG linkage, viva notes and a submission checklist.

## Important interpretation

The extra archive describes US consumer loans. It supports a working methodological demonstration and observed loan-performance analysis. It does not turn the application into a validated Indian microfinance approval model or establish poverty reduction. The review package makes those remaining research and external-evidence gaps explicit.

## Operational changes

The local session secret persists across restarts. Password-hashed accounts own database records; downloads no longer rely on a temporary browser-session list. Database rebuilds preserve personal tables and make a snapshot. The original interactive `new.py` CLI is retired, and compatibility projection/chat adapters route to the supported services. See [operations and authentication](operations_and_auth.md) for exact policy settings and current deployment limits.
