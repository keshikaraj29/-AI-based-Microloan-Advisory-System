# A Reproducible NLP and Clustering Prototype for Exploring Loan Outcomes and Microenterprise Finance

**Project topic:** PI-15, Analyzing the Impact of Micro-Loans on Poverty Alleviation Using NLP and Clustering  
**Document status:** working research draft for author and supervisor review, 16 September 2026  
**Authors and affiliations:** not supplied; actual authors must complete these before submission  
**Submission status:** not submitted; no acknowledgment or acceptance is claimed

## Abstract

Microfinance research requires both financial records and an understanding of borrowers' circumstances. We extend a Phase 1 loan-advisory application into a reproducible exploratory analysis system using supplied loan, agricultural-price, farm and dairy data. The system preserves source boundaries, imports structured records into indexed storage, prepares clustering and narrative analysis outside interactive requests, and presents outcome summaries alongside data limitations. A 12,000-loan reservoir sample contains 7,029 resolved outcomes, of which 79.8976% are fully paid. A two-cluster model achieves silhouette 0.30539; narrative analysis covers 600 descriptions. The application provides input-traceable demo-policy assessments, account-owned records and manually recorded repayment schedules. Revenue and surplus are calculated only from explicitly supplied monthly sales and costs. The research workflow reports observed loan-status cohorts, groups and themes. A local evidence assistant, bounded pagination and deferred work reduce unnecessary interactive processing. The accepted-loan dataset demonstrates methods on a different population from the intended Indian microfinance use case; no linked household welfare before and after lending was supplied. Consequently, this work contributes an analytical prototype and documented evaluation workflow rather than an estimate of microloans' causal effect on poverty. The next research phase requires representative microfinance records, independent text labels and a justified welfare-impact design.

**Keywords:** microfinance; exploratory analysis; borrower narratives; KMeans; topic modeling; reproducibility; financial inclusion

## 1. Introduction

The motivating problem is to understand why loan outcomes and business sustainability differ across borrowers, loan structures and regional contexts. A numeric record can describe a loan's amount or term but may not capture a borrower's explanation of seasonal demand, equipment needs or business constraints. Text analysis can complement structured attributes when the text and financial observations genuinely refer to the same record.

The social motivation must be distinguished from an empirical impact claim. Microcredit studies using randomized designs can estimate effects under their study conditions. In a synthesis of six such evaluations, Banerjee, Karlan and Zinman reported limited average effects rather than broad transformation. An observational application cannot infer the same causal quantities from sentiment, repayment status or projected profit alone. [1]

The supplied Phase 1 project already offered an application form, business-text extraction, loan calculations, optional NLP and downloadable reports. Our audit found three research gaps: no integration of the supplied accepted-loan archive, historical feature rows constructed from the current applicant, and correlations combining arbitrary cluster IDs with incompatible economic proxies. It also found repeated data parsing/model fitting in the interactive submission path and no chat/database layer.

### Research questions

1. Can the supplied structured records and available text be integrated with explicit provenance, missingness and source boundaries?
2. What descriptive borrower groups, themes and loan-outcome associations can be observed under documented feature and cohort definitions?
3. Can these analyses be served through an accessible application with bounded database work and measured interactive performance?
4. Which additional evidence is required before interpreting these associations as useful microfinance or poverty-impact findings?

### Contributions

- A reproducible import and analysis workflow that separates observed loan outcomes from separate business context and user declarations.
- A portfolio interface linking clustering, narrative coverage and outcome summaries to their data definitions.
- A retained and revised Phase 1 application workflow, plus fast local evidence retrieval, indexed storage, connection reuse and deferred loading.
- A review package containing source-to-topic coverage, defined validation, risk tracking, an SDG evaluation proposal and explicit external research gaps.

These are implementation and methodological contributions. Novelty relative to a broader research literature and effectiveness in a real institution remain to be evaluated.

## 2. Related work and methodological basis

TF-IDF represents documents using terms weighted by document frequency, providing a transparent baseline for keyword analysis. The project's corpus analysis uses the scikit-learn vectorizer rather than claiming a language-understanding model. [2] KMeans assigns records to groups around centroids in the chosen feature space. A fixed random seed and explicit initialization settings support repeatability; the resulting groups depend on scaling, selected features and the chosen number of clusters. [3]

The silhouette coefficient compares a record's within-cluster distance with its nearest alternative cluster. Values near zero indicate overlapping groups; the metric is an internal separation measure, not an accuracy score against true borrower labels. [4] Latent Dirichlet Allocation, used by the earlier prototype, represents documents through topic mixtures. [5] The delivered offline analysis uses nonnegative matrix factorization (NMF) of TF-IDF into document/component and component/term weights. Dominant components and high-weight words provide exploratory themes; they are not calibrated semantic probabilities. [6]

The project is motivated by SDG targets that connect poverty and microenterprise development to financial services. This motivation follows the United Nations' targets 1.4, 8.3 and 8.10; it does not mean that using the software achieves an SDG indicator. [7,8]

## 3. Data and provenance

### 3.1 Supplied sources

| Source | Role in this project | Boundary on interpretation |
|---|---|---|
| `accepted_2007_to_2018Q4.csv.gz` supplied in PP1 Data New | Structured accepted-loan attributes, recorded loan status and available descriptions/titles | A distinct US consumer-loan source, with USD fields; not an Indian microfinance field study |
| Agricultural price workbook supplied in PP1 Data and Phase 1 | Historical crop/market-price context | Historical observations, not a live quote or household-welfare measurement |
| `data_season.csv` from Phase 1 | Farm context | Units and field semantics must be validated before extrapolating economics |
| `dairy_dataset.csv` from Phase 1 | Dairy product and transaction context | Transaction ratios are not observed loan repayment or household income changes |
| New application and manual payment ledger | User-stated description, finances, recorded agreement and payments | Owner-entered records, not independently verified bank observations; no measured household welfare effect |

The generated import manifest records files, SHA-256 hashes, row counts and processing choices. The loan importer scanned all 2,260,701 source rows; 2,260,668 had finite positive loan amounts, while 33 failed that eligibility criterion. A uniform reservoir sample of 12,000 eligible rows was selected without replacement using Algorithm R and seed 42. Source-row order is restored after selection. The entire compressed source is retained locally, but the loan database/research cohort is the 12,000-row sample; scanning all records is not the same as analyzing all records.

All 1,048,575 supplied market-workbook data rows were imported, alongside 3,162 farm and 4,326 dairy rows. The market workbook reaches Excel's worksheet row limit, so completeness beyond the supplied file is unverified. The PP1 Data workbook is identical by hash to the workbook in Phase 1 and is counted once.

### 3.2 Unit of analysis and source separation

Loan-level research uses attributes and available text from the same imported loan record. Farm, dairy and market records provide separate contextual summaries; they are not linked to loan borrowers by row number, location name alone or a fabricated key. The database and offline model artifact retain original USD monetary fields. User-facing monetary values are converted to INR using the fixed 95.2311 reference snapshot dated 10 September 2026, published by the Reserve Bank of India and recorded in `config/fx.json`. [9] Already-INR context and application values are not converted twice. Conversion is a reproducible presentation choice, not a live quotation or evidence of Indian borrower representativeness. Text constructed from structured fields, titles and genuine borrower descriptions must be labeled separately.

### 3.3 Data quality

Before interpreting results, inspect the import manifest and research output for missingness, invalid numeric fields, status distribution, narrative coverage and source counts. Missing or unresolved outcomes are distinct from a negative outcome. Missing descriptions must not become fabricated borrower stories. A text-bearing subset may differ systematically from the full imported loan cohort.

## 4. Methodology

### 4.1 Separate serving from data preparation

Source ingestion and portfolio modeling run as preparation steps. An indexed SQLite store serves bounded queries through reusable connections. Persisted research summaries are read by the research interface and local chat. The application evaluates explicit inputs under a configurable demo policy, persists the result and policy snapshot for its signed-in owner, and defers optional content and PDF generation until requested. Historical research tables and private account/application/ledger tables remain distinct. Rebuilds preserve personal records and make a database snapshot.

This separation addresses the baseline's repeated parsing and model fitting. It also makes the dataset version used for a result inspectable. The current chat component retrieves prepared evidence for supported questions; it is not an unrestricted external generative language model.

### 4.2 Structured clustering

KMeans uses loan amount, annual income, interest rate, debt-to-income ratio and term in months. Missing values are median-imputed, each feature is clipped at its 1st/99th sample percentiles, amount/income receive `log1p`, and all features are standardized. There are ten missing debt-to-income values; the other four features are complete in this sample. Models use seed 42 and ten initializations. Candidate counts 2–6 are compared by silhouette on the same 2,000-row random evaluation subset; Davies–Bouldin values provide a second descriptive metric on the full model cohort.

Loan status, repayment, recoveries, sentiment and post-origination outcomes do not form the clusters. Outcome summaries are calculated afterward. The selected group count maximizes silhouette; the metric is not an independent predictive validation. Group labels are identifiers and do not establish creditworthiness.

The study is exploratory: internal separation on a sample does not prove that group membership is stable in later years or a different region. A future evaluation should compare multiple seeds, temporal samples, feature ablations and alternative clustering methods.

### 4.3 Narrative analysis

The corpus includes 600 cleaned borrower descriptions of at least 20 characters. HTML, standard source boilerplate and links/email strings are removed. TF-IDF uses unigrams/bigrams, `min_df=3`, `max_df=0.90`, at most 2,000 features and sublinear term frequency, with English/domain stopwords. The resulting vocabulary has 872 terms. Five-component NMF uses `nndsvda` initialization, seed 42 and at most 500 iterations. Documents receive their largest-weight component; zero vectors remain unassigned.

Sentiment uses fixed positive/negative word sets and a three-token negation window. Score is positive minus negative matches divided by all matches; values above 0.1 are positive and below −0.1 negative, with the rest neutral. This describes lexical tone rather than a probability. The fast application view uses tokenization and term frequency and is labeled separately from the corpus TF-IDF/NMF model.

No independent human sentiment labels were supplied. We therefore do not report held-out accuracy, macro-F1 or a validated relationship between writing tone and credit risk. Appropriate next evaluation would use two independent annotators, a domain-specific guide, agreement measurement and an adjudicated test set that is not used to tune the heuristic.

### 4.4 Outcomes and association analysis

The resolved cohort comprises Fully Paid and Charged Off statuses, including equivalent legacy policy-status labels. All other statuses, including current, grace-period, late and default, are excluded from this defined terminal-outcome denominator. The fully paid proportion is Fully Paid / (Fully Paid + Charged Off). It is not an on-time-installment rate.

Meaningful numerical predictors can be compared with a binary resolved outcome using appropriate correlation summaries. Cluster/topic IDs are categorical, so their numeric identifiers are not treated as continuous measures. Group outcome tables support comparisons without an arbitrary ordering. These associations are affected by borrower selection, loan vintage, observation window and missingness; they cannot show that a particular term or interest rate caused a better outcome.

### 4.5 Application assessment and recorded repayment

The assessment preserves explicitly entered versus narrative-extracted inputs. It covers every purpose in the supplied loan data, with farm/dairy sectors under small business, and requests clarification for unknown categories. It uses no assumed quantities, yields, unit prices, operating costs or revenue. Only when both monthly business sales and costs are explicitly supplied does it calculate annual revenue as 12 times sales and annual operating surplus as 12 times their difference. This annualization assumes a repeated monthly amount; it estimates no income growth or realized outcome. Loan principal remains financing rather than an operating expense.

A configurable academic policy uses a default nominal annual interest rate of 12%, a 12-month default term and a 40% total monthly debt/income ceiling. A supplied whole-month term is honored within configured bounds (default 1–360). These are disclosed operator settings, not empirically calibrated lender rules. `policy_config.py` validates them; the saved assessment retains its policy snapshot and input provenance. The engine returns Ready for review, Needs information or Affordability concern with individual rule explanations. Age, gender, card ownership, sentiment and historical source-cohort repayment do not produce a risk score or set the applicant's interest rate.

The milk-business narrative requesting INR 10,000 in Bengaluru identifies a purpose, amount and location but does not establish sales, expenses or growth. Its business financial results therefore remain unavailable until entered. A matching dairy price remains context with an explicit source unit, observation count and locality scope; a state-level fallback is not described as a city-specific quote.

Signed-in users can save assessments, revisit explanations and download reports. A separate ledger starts only after the user confirms recording an actual disbursement and its agreement terms. Payments are entered manually or imported atomically from CSV, with application-scoped idempotent references and integer-paise accounting. Payments allocate oldest installment first, interest before principal. The system does not move funds, verify bank settlement or invent a prepayment rebate. These records remain distinct from the historical research cohort, and recording them supplies no household welfare outcome.

A separate `impact_outcomes.py` module accepts validated borrower-linked baseline/follow-up household income, household size, optional business income and installment counts. It normalizes annual inputs to monthly amounts, keeps currencies separate, and reports paired household/per-capita/business changes, missingness and observed installment punctuality. Its header-only template contains zero real observations. This implements the measurement pipeline while leaving actual impact results unavailable until genuine data is collected.

### 4.6 Evaluation protocol

The delivered validation artifacts record the exact checks and measured timings for the build. Functional checks cover valid and malformed inputs, core pages/API behavior, bounded data pagination and reports. Data checks examine ingestion and summary consistency. Research checks examine reproducible outputs and legitimate outcome denominators. Performance measurements identify the machine, repetitions and warm/cold state where available.

The baseline has no chat API, so a chat percentage-speedup comparison would be invalid. Report the new endpoint's measured latency and explain the avoided work. Tests demonstrate behavior for evaluated cases, not absence of every possible error.

## 5. Results

### 5.1 Data and observed outcomes

These results come from `data/source_manifest.json` and `data/research_summary.json`, generated at 2026-09-15 18:47:15 UTC (16 September in India).

| Measure | Result | Interpretation |
|---|---:|---|
| Eligible source loan records | 2,260,668 | Full source scanned; 33 invalid-amount rows excluded |
| Analyzed loan sample | 12,000 | Uniform reservoir sample, seed 42 |
| Resolved loan outcomes | 7,029 | 4,971 other-status observations excluded from this denominator |
| Fully paid among resolved | 79.8976% | 5,616 fully paid / 7,029 resolved, including legacy labels |
| Clean descriptions meeting the 20-character threshold | 600 (5.00% of sample) | All 600 belong to resolved historical loans |
| Sample nonempty descriptions before threshold | 628 | Description length/cleaning limits coverage |
| Imported market / farm / dairy rows | 1,048,575 / 3,162 / 4,326 | Separate business context, not linked household outcomes |
| Real paired household observations supplied | 0 | Income-change and poverty-impact results remain unavailable |

Only 135 sample loans have the `small_business` purpose (81 resolved, 71.6049% fully paid). Most of the analyzed portfolio is consumer lending; its use as a demonstration must not be presented as empirical evidence on small Indian enterprises.

### 5.2 Clustering results

| Candidate k | Silhouette | Davies–Bouldin |
|---:|---:|---:|
| 2 | 0.30539 | 1.37988 |
| 3 | 0.24773 | 1.41837 |
| 4 | 0.23750 | 1.37400 |
| 5 | 0.22497 | 1.47891 |
| 6 | 0.21298 | 1.46455 |

The selected model has two groups because it maximizes the prespecified silhouette criterion. The Davies–Bouldin value is slightly lower for four groups, demonstrating that different metrics need not choose the same count. The selected silhouette shows some separation with substantial room for overlap; it is not proof of true risk categories.

| Group | All rows | Resolved rows | Fully paid / resolved | Mean loan (INR, converted) | Mean rate | Mean term |
|---|---:|---:|---:|---:|---:|---:|
| Segment 1 | 3,533 | 1,697 | 65.5274% | 2,004,107.91 | 16.2527% | 59.41 months |
| Segment 2 | 8,467 | 5,332 | 84.4711% | 1,218,442.95 | 11.7751% | 36.01 months |

Mean loan amounts above use the pinned presentation rate, with original values retained in the model artifact. The model was fitted in original source units; the display conversion does not change its assignments. The dominant distinction includes loan term/amount/rate. It is not evidence that changing a borrower's term would change repayment by the observed difference. The cluster inputs and outcome selection share borrower/vintage context, and unresolved records differ by group.

### 5.3 Structure, text and association results

The 36-month cohort has 8,551 rows (5,384 resolved) and an 84.1939% fully paid proportion among resolved loans. The 60-month cohort has 3,449 rows (1,645 resolved) and a 65.8359% fully paid proportion. Longer duration changes the opportunity to observe completed outcomes; the difference does not establish a causal benefit from shortening loans.

Among resolved records, Pearson correlations with binary fully-paid status are −0.268828 for interest rate (n=7,029), −0.193944 for term (n=7,029), −0.078157 for loan amount (n=7,029), −0.090042 for debt-to-income ratio (n=7,026), and +0.053972 for annual income (n=7,029). These are unadjusted descriptive associations, with pairwise-complete denominators and no significance claim.

NMF themes are dominated by credit cards, consolidation, payments and borrowing costs. Component sizes are 80, 118, 48, 291 and 63 descriptions. This reflects the consumer-loan context and does not establish farm-specific business barriers. Lexicon sentiment labels 236 descriptions negative, 261 neutral and 103 positive. Sentiment's correlation with the binary repayment outcome is +0.023452 (n=600), providing little linear separation in this subset and no predictive validation.

All 600 qualifying narratives have resolved outcomes, whereas 4,971 of the broader sample do not. The text-bearing cohort therefore differs from the full sample; its apparently stronger fully-paid proportions cannot be generalized without examining vintage and narrative-availability selection.

### 5.4 Software and future-outcome validation

The JUnit record in `docs/test_results.xml` records zero failures, errors and skipped cases for the delivered test run. The nine dedicated household-outcome tests use temporary synthetic fixtures, including empty data, paired/per-capita changes, annual conversion, currency separation, missingness, invalid inputs and import atomicity. The shipped household CSV remains header-only.

The authoritative measured workload, host/runtime, timestamp, first-call latency and warm median/p95 values are in `docs/performance_results.json` and interpreted in `docs/validation_report.md`. The updated workload includes authenticated, persisted application submission. Submission returns a redirect to the saved assessment; it is not a failure response. A first submission can include lazy module imports, while warm submissions reuse imported code and prepared context. These results must not be compared to an obsolete anonymous, nonpersisted submission workload as if only speed had changed.

Measurements use the Flask test client and exclude process startup, browser rendering, HTTP transport, OCR and on-demand PDF generation. They support conclusions about checked local request handling, not end-user latency or multiuser production capacity. Phase 1 had no chat endpoint, so no baseline chat-speedup percentage is reported. For manuscript submission, archive the exact benchmark artifact alongside the tested code rather than copy stale timings from a different build.

### 5.5 Interpretation framework

- **Data integration:** imported source counts demonstrate working ingestion; they do not establish representativeness or permission to redistribute the data.
- **Cluster quality:** silhouette and group sizes describe the selected sample/feature space; overlapping groups are a result to report, not hide.
- **Loan outcomes:** rate differences across cohorts are descriptive. They can motivate investigation of loan design and borrower context, but confounding remains.
- **NLP:** keywords and topic mixtures provide themes; limited descriptions constrain claims about nonfinancial factors. Sentiment has no supplied ground-truth benchmark.
- **Application performance:** measured local timings characterize the checked workload; concurrency and production hardware require separate evaluation.
- **Economic improvement:** no linked pre/post household metric was supplied. Annualized user-declared surplus is arithmetic from current inputs, not evidence that a loan raised income.

## 6. Discussion

The main engineering improvement is the separation of repeatable portfolio analysis from interactive workflows. Source-specific evidence becomes visible without reprocessing large inputs for each question. The method also corrects an important conceptual error in the baseline: fabricated historical borrower rows and mixed-unit proxies are not legitimate substitutes for actual loan data.

An institution could use descriptive groups to ask whether certain product structures, application themes or borrower circumstances deserve further investigation. For example, a group with a different observed outcome proportion might justify studying affordability or follow-up support. It would be premature to convert that group directly into a loan-approval rule, especially when the observed lending population differs from the intended beneficiaries.

The current system illustrates a research workflow, not an impact identification strategy. Claims about sustainable livelihoods require consistent welfare measures and follow-up; claims about causation require a comparison design and defensible assumptions. A low-latency interface improves access to analysis but cannot repair a mismatch between data and the research question.

## 7. Limitations and future work

1. **Population mismatch:** the supplied accepted-loan data cannot establish microfinance outcomes in the intended Indian beneficiary population.
2. **Missing causal evidence:** no household welfare baseline/follow-up linked to loans or comparison group is supplied.
3. **Narrative availability:** title/description coverage may be selective; generated text must remain distinguishable from borrower language.
4. **Model evaluation:** clustering is descriptive and internally evaluated; sentiment has no independent label benchmark, and topic coherence has not been validated by domain experts.
5. **Temporal and selection bias:** accepted loans exclude rejected applicants; loan vintage and unresolved statuses affect outcome comparisons.
6. **Operational scope:** local account/owner checks and manually recorded payments do not establish bank integration, production identity controls or settlement verification. Local tests and benchmark results do not establish production capacity, institutional approval or field usability.
7. **Documentation gaps:** the original team schedule, contribution records and external submission/acceptance evidence were not supplied.

Next work should obtain permissioned microfinance data, prespecify an outcome and observation window, create an independent text benchmark, test clustering stability, evaluate real user comprehension, and revise claims to match evidence. A separate impact study should use an appropriate design rather than infer welfare from repayment or language.

## 8. Conclusion

The project extends a Phase 1 advisory application with data ingestion, exploratory NLP/clustering, source-aware outcome analysis, a revised interface and a faster prepared-evidence serving path. The deliverable strengthens implementation and review evidence. It also makes the remaining research gap explicit: the supplied records do not establish a causal reduction in poverty. The system is a foundation for a more representative, independently evaluated study.

## References

1. Banerjee, A., Karlan, D., and Zinman, J. (2015). Six Randomized Evaluations of Microcredit: Introduction and Further Steps. *American Economic Journal: Applied Economics*, 7(1), 1–21. [Publisher article, DOI 10.1257/app.20140287](https://www.aeaweb.org/articles?id=10.1257/app.20140287).
2. scikit-learn developers. *TfidfVectorizer*. [Official documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html). Accessed 15 September 2026; installed version is recorded with the delivered environment.
3. scikit-learn developers. *KMeans*. [Official documentation](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html). Accessed 15 September 2026.
4. scikit-learn developers. *silhouette_score*. [Official documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html). Accessed 15 September 2026.
5. Blei, D. M., Ng, A. Y., and Jordan, M. I. (2003). Latent Dirichlet Allocation. *Journal of Machine Learning Research*, 3, 993–1022. [Journal article](https://www.jmlr.org/papers/v3/blei03a.html).
6. scikit-learn developers. *NMF*. [Official documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.NMF.html). Accessed 16 September 2026.
7. United Nations Department of Economic and Social Affairs. *Goal 1*. [Official targets and indicators](https://sdgs.un.org/goals/goal1). Accessed 15 September 2026.
8. United Nations Department of Economic and Social Affairs. *Goal 8*. [Official targets and indicators](https://sdgs.un.org/goals/goal8). Accessed 15 September 2026.

9. Reserve Bank of India. *National Summary Data Page*, exchange-rate observation for 10 September 2026. [Official page](https://www.rbi.org.in/scripts/BS_NSDPDisplay.aspx). Verified 16 September 2026; pinned metadata in `config/fx.json`.

## Reproducibility and declarations

Use the project README to recreate the database, regenerate analysis and run validation. Preserve the supplied-file manifest and the measured artifacts from the submitted version. Dataset provenance and redistribution permissions require author review because source licenses were not included in the user request. Actual authors must complete funding, conflicts, ethics, data-availability and assistance declarations according to their institution and chosen venue.

### Recovery reproducibility note

The data pipeline was rerun after accidental deletion on 16 September 2026. `data/source_manifest.json` records the new build timestamp and retained compressed-source hash. Counts, the deterministic sample and reported research metrics match the original analysis above. The compressed archive was recreated from the surviving source CSV; a changed compressed-byte hash is expected.
