# Recovery report — 16 September 2026

The project workspace was accidentally deleted and the Trash emptied. The Downloads project contained the original Phase 1 files. The two supplied data folders and all three original ZIP archives survived.

## Restored

- Recovered the latest source edits from this task's recorded patch/write history. Recovered assets from surviving originals and the task's attachments.
- Restored owned accounts/applications, database-compatible application JSON, configurable demonstration policy, manual payment logs and atomic CSV import, INR presentation, category-specific research and Atlas explanations.
- Restored transparent narrative sentiment, bright colors, animated navigation pills, accessible tab switching, browser-history handling, lazy loading, pooling and indexes.
- Restored the five-page PDF builder, synthetic example, topic/rubric reference images, research-paper draft, planning, SDG, methodology and viva material.
- Rebuilt the database: 12,000 sampled loans from 2,260,668 valid source records; 1,048,575 market records; 3,162 farm records; 4,326 dairy records. The sample, 600 eligible narratives, 79.8976% resolved-loan repayment and silhouette 0.30539 match the earlier results.
- The source loan CSV was recompressed for the retained archive, so its compressed-byte hash differs. The source records, sampling seed and analytical results are unchanged.

## Data that could not be recovered

The deleted private SQLite database and its deleted backup were not present in any surviving supplied archive. Previous registered accounts, saved applications and payment entries are not recreated. The rebuilt database starts with no private records. Existing Phase 1 report files are preserved. Users can register again and enter new applications; no invented account or payment records have been inserted.

## Verification

- Full suite: **159 tests and 12 subtests passed**, 15.53 seconds.
- All 11 templates parse; three JavaScript files pass syntax checks.
- SQLite integrity check: `ok`; no foreign-key violations.
- Regenerated sample PDF: all five pages rendered and visually checked; missing income/costs remain missing, with no fabricated INR 63,000 growth.
- Request benchmarks regenerated in `performance_results.json`.
- Restored Downloads copy started using its own `.venv` at localhost port 5057. Home, research, apply/sign-in, health, same-category summary, dairy explorer, served CSS/JS/image assets and Atlas chat returned HTTP 200. Browser interaction tooling was unavailable during recovery; the earlier animation/browser checks are preserved as historical evidence, not a new visual pass.

## Starting and backing up

Double-click `Start Microloan Atlas.command` in the Downloads project to serve at `http://127.0.0.1:5057`. Keep the terminal open. This folder has an independent `.venv` environment; copied environments are not portable to another computer.

The separate recovery ZIP includes source, prepared data, retained raw loan archive, documentation and tests. It excludes virtual environments, runtime secrets, caches and temporary browser-test records. Install dependencies from `requirements.txt` after extracting on another machine. Back up future private records with SQLite's backup API while the server is stopped or using a consistent live backup; copying an active database without its WAL can lose changes.
