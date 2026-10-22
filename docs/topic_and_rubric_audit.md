# Topic and rubric completeness audit

**Review date:** 15–16 September 2026. **Baseline:** user-supplied PP1 Finale. **Requested upgrade:** incorporate both data folders, improve the user interface and chat response path, add indexes, pooling, lazy loading, deferred scripts, and close gaps against topic PI-15.

## Conclusion

Phase 1 implements an individual loan-advisory demonstration with text extraction, financial rules, optional NLP/clustering, charts, and report downloads. It does **not** by itself demonstrate the impact of micro-loans on poverty. Several analytics in that baseline use constructed indicators instead of observed borrower outcomes. The upgrade adds a reproducible portfolio-analysis path, account-owned applications with explicit-input assessments, manually recorded repayment tracking, a validated household baseline/follow-up pipeline and more review evidence. Unsupported business forecasts are removed; missing revenue/cost inputs stay missing. A causal poverty-impact study still requires appropriate longitudinal microfinance data and a defensible comparison design.

## Topic coverage

| Topic requirement | Phase 1 finding | Evidence to inspect in this delivery | What the evidence supports |
|---|---|---|---|
| Combine structured loans and unstructured borrower narratives | Farm/dairy CSVs and user-entered descriptions exist; no accepted-loan archive integration | Import manifest, research analytics, dataset explorer, source-specific counts | Linked text and financial features within each imported record; provenance remains visible |
| Loan structure and borrower characteristics | Fixed risk rules and financial projections in `new.py` and `app.py` | Loan term, amount, rate, income and debt-burden fields in the research pipeline | Observational comparison; not a validated lender score |
| Repayment behavior | Phase 1 uses a formula called repayment confidence and mixes sales/revenue proxies | Historical status cohort definitions; separate owner-scoped agreement/installment/payment ledger and CSV import | Recorded historical status and user-entered payments remain distinct. No automatic bank verification; ongoing loans are not treated as completed repayment |
| Business outcomes and economic improvement | Estimated project profit/ROI; no before/after household data | Explicit monthly revenue/cost annualization only; `impact_outcomes.py`, validated paired-income import and header-only template | No invented quantities, costs or growth. Working future-data pipeline; zero supplied household observations and no achieved poverty exit |
| Clustering borrowers | KMeans exists, but the optional model manufactures numeric rows by scaling the current application | Research feature definitions, candidate cluster metrics and cohort summaries | Exploratory grouping of actual imported rows |
| Sentiment extraction | Keyword scoring and optional TextBlob exist; no labeled evaluation | Sentiment distribution and explicit heuristic labeling | Descriptive tone only; confidence is not measured accuracy |
| Topic modeling | LDA is fitted in request processing | Offline TF-IDF and five-component NMF with persisted topic keywords/assignments | Recurring language patterns in 600 qualifying descriptions; topics need human interpretation |
| Correlate analytics with outcomes | Baseline correlates arbitrary numeric cluster/topic IDs and incompatible proxy units | Named numeric feature correlations and categorical cohort outcome summaries | Within-source associations; correlation is not causation |
| Identify success/risk profiles | Rule-based application labels and unvalidated cluster names | Cluster sizes, observed outcome proportions, selected feature summaries | Descriptive profiles; no automatic approval based on cluster or writing style |
| Explain nonfinancial barriers | Narrative keywords/topics can expose themes | Topic keywords, sentiment and narrative coverage | Hypotheses about barriers; sparse narrative coverage limits conclusions |
| Actionable institutional/policy insight | Individual recommendations; little portfolio evidence | Cohort comparisons, limitations and SDG follow-up plan | Questions for field validation and program design |
| Sustainable livelihoods and poverty alleviation | Stated objective; direct measurements absent | Paper limitations and societal-impact measurement plan | Research motivation and a path to evaluation; achieved social impact remains unverified |

## Phase 1 technical gaps established by source inspection

1. No chat HTTP endpoint, database schema, query indexes, or connection pool was present in the supplied Flask app.
2. The submit path reloads CSV/Excel files, loads the spaCy model separately for preprocessing and entities, and fits TF-IDF, KMeans, and LDA repeatedly. It also builds a PDF before returning the result.
3. `nlp_analytics._numeric_feature_rows` constructs historical financial rows from one applicant rather than reading historical borrower finances.
4. `correlate_analytics_with_outcomes` treats integer category IDs as quantities and combines farm revenue per area, dairy sales ratios, and application confidence. Those correlations lack a consistent interpretation.
5. The corpus de-duplication path can place an already-seen current description somewhere other than the last row, while downstream methods assume the last row belongs to the current application.
6. Optional dependencies are broadly caught; an apparently successful application can have unavailable analytics. Review the returned availability fields instead of assuming every model ran.
7. The Phase 1 download route joins an arbitrary filename to a directory, and validation/error handling needs explicit negative cases. The upgrade includes tests for malformed inputs and owner-checked report access.

Additional application checks cover all source purposes, unknown-purpose clarification, term bounds/provenance, missing cashflow, account ownership, INR presentation and payment idempotency. The current assessment returns Ready for review, Needs information or Affordability concern under a configurable demo policy; it never issues a bank approval. Prices report source units and locality scope.

These findings describe the supplied baseline. Inspect the delivered source and validation report for the implemented corrections.

## Delivered evidence map

| Area | Concrete evidence |
|---|---|
| Reproducible ingestion | `scripts/prepare_data.py`, `data/source_manifest.json`; full scan and seed-42 reservoir selection |
| Database and connection reuse | `data_store.py`, `data/pp1.sqlite3`; 12,000 loan rows, 1,048,575 market rows, 3,162 farm rows and 4,326 dairy rows |
| Research models and metrics | `research_analytics.py`, `data/research_summary.json`; k=2, silhouette 0.30539, 600 descriptions, 7,029 resolved outcomes |
| Revised request processing | `atlas_service.py`, `app.py`, `report_builder.py`; local evidence/navigation, prepared analysis, bounded queries and on-demand PDF |
| Owned application lifecycle | `assessment_engine.py`, `policy_config.py`, `application_store.py`; login/owner checks, saved policy and provenance, actual-agreement recording, atomic manual payment CSV |
| INR presentation | `currency_tools.py`, `config/fx.json`; pinned RBI 95.2311 conversion dated 10 September 2026; original research units retained internally |
| Interface | `templates/`, `static/`; integrated application/research pages, deferred scripts and lazy requests |
| Future real household outcomes | `impact_outcomes.py`, `data/templates/household_outcomes.csv`, `tests/test_impact_outcomes.py`; nine passing synthetic tests, zero fabricated field records |
| Research and review materials | This documentation folder; actual source-derived results, plan/risks, SDG links, presentation/viva and submission checklist |

## Rubric evidence and remaining external requirements

| Rubric parameter | Evidence supplied in the upgraded project | Remaining requirement for an excellent rating |
|---|---|---|
| Objective achievement and implementation progress | Topic matrix, integrated application/research workflow, import/analysis artifacts and validation | Reviewer must agree that the Phase 2 milestones match the review scope; direct poverty-impact validation is not established |
| Testing, validation and result analysis | Defined functional tests, data-quality checks, clustering metric, measured response timings and results interpretation | Collect an independent labeled sentiment set and representative deployment/field data before generalizing accuracy or performance |
| Research paper progress and submission | Cited paper draft and submission checklist | Authors and supervisor must finalize the manuscript and submit to an open, appropriate venue; retain genuine acknowledgment/acceptance |
| Planning, progress and risk management | Dependency chart, actual implementation record, risk register and follow-up schedule | Attach the original Phase 1 plan and team effort records to prove historical variance; these were not supplied |
| SDG alignment and societal impact | Specific SDG targets, identified beneficiaries, example use cases and evaluation measures | Validate accessibility, benefit and possible harm with actual participants; no achieved poverty reduction is claimed |
| Presentation and viva voce | Slide-ready outline, demo sequence, reproducibility cues and viva answers | Team must rehearse, supply attributable contributions and answer questions; competence cannot be proved by generated notes alone |

## What would complete the research objective

- Obtain permissioned microfinance records with stable borrower IDs, disbursement dates, installment due/paid history, loan terms, business outcomes, and pre/post household welfare indicators.
- Link narratives to these same borrowers, with consent, missingness analysis, language coverage and a reproducible annotation guide.
- Specify one primary welfare outcome and follow-up window before analysis. A baseline-to-follow-up change alone does not isolate the loan's effect.
- Use an appropriate randomized or carefully justified observational comparison design; retain regional/time controls and state assumptions.
- Evaluate clustering stability and text quality independently. Report uncertainty and subgroup coverage; keep loan decisions under accountable human review.
- Publish only aggregate/anonymized evidence with appropriate source permissions and genuine authorship/submission records.
