# Local operation, accounts and data handling

This guide describes the delivered software as of 16 September 2026. It is an academic application with local accounts and manually entered records. The code does not connect to a bank, transfer money or issue a lender's decision.

## Start and sign in

1. Follow the environment/install commands in the [project README](../README.md).
2. Run `python run.py` and open `http://127.0.0.1:5000`. Waitress binds to localhost and uses eight worker threads.
3. Create your own account. Usernames have 3–100 letters/numbers or `. _ @ + -`; they are stored case-insensitively. Passwords must have 10–200 characters and are stored as Werkzeug password hashes.
4. Sign in to save an application, view its explanation/history, download JSON/PDF, or record payments. Access is checked against the signed-in owner in storage, including direct record URLs and application-aware chat.
5. Log out using the interface. Records persist in SQLite and become available when the same account signs in again. There is no built-in password reset, email verification, administrator dashboard or account deletion flow.

The delivered data has no preconfigured account. Use fictional demonstration profiles for classroom testing. The form discards the submitted date of birth before saving; KYC identifiers, phone, address and gender are not persisted by the submission route. Names, narratives, declared finances and payment references are stored, and a person can still put identifying information inside their narrative.

## Configuration

Set environment variables before launching the server, then restart after changing them.

| Variable | Default | Meaning and accepted range |
|---|---|---|
| `PORT` | `5000` | Local listening port |
| `PP1_DATABASE` | `data/pp1.sqlite3` | Prepared database used by web research and application stores; must exist |
| `PP1_RESEARCH_SUMMARY` | `data/research_summary.json` | Precomputed research JSON used by serving |
| `PP1_DB_POOL_SIZE` | `4` | Research read pool; clamped to 1–16 connections |
| `PP1_FX_CONFIG` | `config/fx.json` | Validated USD-to-INR display-rate metadata file |
| `PP1_DEMO_ANNUAL_RATE` | `.12` | Annual nominal rate as a fraction, from 0 to 1; `.12` means 12% |
| `PP1_DEMO_TERM_MONTHS` | `12` | Default whole-month assessment term when none is supplied |
| `PP1_DEMO_MIN_TERM_MONTHS` | `1` | Minimum permitted requested/default assessment term |
| `PP1_DEMO_MAX_TERM_MONTHS` | `360` | Maximum permitted requested/default assessment term; at most 360 |
| `PP1_DEMO_MAX_DEBT_RATIO` | `.40` | Maximum (existing monthly installments + proposed EMI) / declared monthly income; greater than 0 and at most 1 |
| `SECRET_KEY` | Persisted local random key | Session-signing secret; production requires at least 32 characters |
| `PP1_ENV` | Local mode | Exact value `production` enforces the secret requirement and secure cookies |

Policy term settings must satisfy `1 <= minimum <= default <= maximum <= 360`. Requested terms must be whole numbers inside those bounds. The policy comes from the operator, not a model fitted to the supplied loans. The policy snapshot, selected term, term source and rule trace are saved with every assessment. Changing settings affects future assessments; it does not recalculate old records.

For example, to use a six-month default while retaining permitted user terms:

```bash
export PP1_DEMO_TERM_MONTHS=6
export PP1_DEMO_ANNUAL_RATE=0.12
export PP1_DEMO_MAX_DEBT_RATIO=0.40
python run.py
```

When `SECRET_KEY` is absent in local mode, `instance/secret_key` is created once with restrictive permissions and reused across restarts. Protect it with the database and never publish it. Production mode requires an operator-supplied secret and HTTPS because the browser will only send the secure session cookie over HTTPS. Setting this variable does not configure TLS or expose the localhost server.

### Currency snapshot

Application inputs and displayed monetary outputs are INR. The checked [RBI National Summary Data Page](https://www.rbi.org.in/scripts/BS_NSDPDisplay.aspx) gives **95.2311 rupees per USD for 10 September 2026**. The reproducible snapshot in `config/fx.json` was verified on 16 September 2026. It is not a live transaction quote. Keep source/date/method/scope metadata when intentionally updating it. Raw research amounts and the offline model artifact stay in original source units. Do not multiply already-INR dairy, market or application values by the rate.

## Assessment and evidence rules

- A narrative or explicit INR field can supply the requested amount; explicit fields take precedence. Missing amounts remain missing. Unknown purposes request clarification.
- All 14 supplied loan purposes are supported; dairy and farm are sectors under small business. Matching dataset counts are context, not a trained Indian borrower risk estimate.
- Revenue and operating surplus are available only when **both monthly business revenue and monthly business costs** are explicitly supplied. Annualization assumes the declared monthly amounts repeat for 12 months; it establishes no growth or realized outcome.
- Default debt ratio is 40%. Missing income/obligations remain visible. A known affordability concern takes priority in status, and other missing fields remain listed.
- Optional date-of-birth validation checks adulthood; age, gender, sentiment and card ownership do not set interest or risk scores.
- Historical prices identify product, unit, observation count and exact locality or fallback scope. A Karnataka match must not be described as Bengaluru-specific. An ambiguous dairy source unit must not be assumed to mean liters.
- Reports use native PDF charts and explicit missing-value text. The basic PDF font cannot reproduce every script; unsupported Unicode fields are marked as preserved in the application/JSON instead of showing broken glyphs.

## Record an agreement and payments

An assessment schedule is a demo-policy estimate. To start a ledger, open its saved application and confirm that you are recording a disbursement which already occurred. Enter its actual date and confirm principal, annual rate and term. Enter rate as a percentage in the web form. The recorded agreement may differ from the assessment; both remain available, with their provenance. Recording a missing-amount draft requires an actual principal first.

Agreement terms accept whole months from 1–600, reflecting a recorded agreement rather than the stricter configurable assessment-policy bounds. Once started, date and terms cannot be silently replaced. The initial monthly due dates retain the original day where possible, with end-of-month adjustment.

Record payments individually or upload UTF-8 CSV with exactly these three headers (any column order):

```csv
amount,paid_on,reference
```

There are no real sample payments bundled. Dates use `YYYY-MM-DD`, cannot be in the future or before recorded disbursement, and references have 1–120 characters. The web upload limit is 1,000,000 bytes and the importer allows at most 2,000 payment rows. Amounts use at most two decimal places and normally must be at least INR 1; an exact final remaining balance as low as INR 0.01 is supported.

References are unique within an application. Repeating the same reference/date/amount is idempotent: it does not double count. Reusing a reference with different details fails. CSV imports are atomic: a failed row rolls back that import. Overpayments beyond the recorded schedule are rejected.

The ledger allocates payments to oldest installments, interest before principal. It reports due, partial, overdue and paid states from recorded dates and amounts. Early payments cover the fixed schedule; the software does not invent a prepayment rebate, penalty, fee or interest waiver. No bank settlement is verified. There is no reversal/edit workflow, so verify a manual entry before saving it.

## Backup, rebuild and retention

Research reads use a bounded read-only pool; accounts and records use a separate four-connection read/write pool, WAL journaling and short transactions. These are separate tables in the same database. Research rebuilds create a SQLite snapshot under `data/backups/` and transactionally refresh research tables without deleting account, application, installment or payment tables.

Stop the server before rebuilding. `scripts/prepare_data.py` operates on the project-local `data/pp1.sqlite3` and `data/research_summary.json`; the web path overrides do not redirect that CLI. Restart after rebuilding so cached summaries refresh. Retain the raw archive and manifest for reproduction.

Keep independent backups of the database, `instance/secret_key`, custom FX settings and real household CSV. For a consistent database snapshot, use SQLite's backup API. Example from the project folder, with a new destination name:

```python
import sqlite3
with sqlite3.connect('data/pp1.sqlite3') as source:
    with sqlite3.connect('data/manual_backup.sqlite3') as backup:
        source.backup(backup)
```

Do not copy only the main SQLite file while a process is writing; recent records may still be in its WAL. Verify restoration on a separate copy. The app does not automatically expire or delete records/backups. Downloads are owner-checked; JSON is read from the database and PDF is generated in a temporary folder on demand. Legacy files in `reports/` are not the authoritative current record store.

## HTTP behavior and present deployment limits

Every POST requires the page CSRF token (form field or `X-CSRF-Token` for JSON). Sessions use HTTP-only, SameSite=Lax cookies and a 12-hour lifetime. Responses include CSP, frame restrictions and no-store for non-static pages. Local rate limiting allows 30 combined login/register attempts per IP per 15 minutes, and 100 chat calls per IP per minute. The limiter is in-memory and resets on restart; it is not a distributed abuse-control service.

Public research pages remain accessible without sign-in; personal records and application-aware context require ownership. `/api/chat` accepts a 1–1,000-character message and optionally an owned application ID. General chat is a fixed-scope local evidence/navigation service, not an external LLM. It executes no navigation or payment action on its own.

Current limits are material for a shared deployment: no MFA, password recovery, user-role administration, encrypted database, retention/deletion UI, verified payment feed, payment correction workflow, production monitoring or distributed rate limiting. SQLite write concurrency, serial PDF generation, backup/recovery and real traffic need deployment-specific evaluation. HTTPS termination, access/retention procedures and verified lender rules must be implemented before using real client information as an institutional service. Passing local tests does not establish operational lending readiness.
