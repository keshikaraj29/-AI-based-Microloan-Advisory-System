"""Offline research generation and inexpensive web-facing query functions.

Only build_summary imports scientific libraries. Web requests read a small
precomputed JSON report and query indexed, deidentified sample rows.
All monetary LendingClub variables are USD; AGMARKNET prices are INR/quintal.
"""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import html
import json
import math
import os
import re
import sqlite3

from data_store import BASE_DIR, get_store

SUMMARY_PATH = BASE_DIR / 'data' / 'research_summary.json'


@lru_cache(maxsize=4)
def _read_summary(path, modified):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_research_summary():
    """Read summary; its file modification time invalidates the process cache."""
    path = Path(os.environ.get('PP1_RESEARCH_SUMMARY', SUMMARY_PATH))
    try:
        return _read_summary(str(path), path.stat().st_mtime_ns)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError('Prepared research data is unavailable; run scripts/prepare_data.py.') from exc


def query_loans(page=1, per_page=20, purpose=None, state=None, cluster=None,
                category=None, page_size=None):
    """Return a bounded page. Filters use bound parameters; raw narratives and
    original borrower IDs are deliberately excluded from the web response.
    ``category`` aliases purpose and ``page_size`` aliases per_page for the UI.
    """
    page, per_page = max(1, int(page)), min(100, max(1, int(page_size or per_page)))
    where, params = [], []
    for field, value in (('purpose', purpose or category), ('state', state), ('cluster_id', cluster)):
        if value is not None and str(value) != '':
            where.append(f'{field}=?')
            params.append(int(value) if field == 'cluster_id' else str(value))
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    with get_store().pool.connection() as conn:
        total = conn.execute('SELECT COUNT(*) FROM loans' + clause, params).fetchone()[0]
        rows = conn.execute('''SELECT id AS borrower_id, purpose AS category,
            state, loan_amount, term_months, interest_rate,
            loan_status AS repayment_status, sentiment_label AS sentiment,
            cluster_id, cluster_label, issue_date FROM loans''' + clause
            + ' ORDER BY id LIMIT ? OFFSET ?', params + [per_page, (page - 1) * per_page]).fetchall()
    items = [dict(row, currency='USD', income_change_pct=None) for row in rows]
    return {'items': items, 'page': page, 'page_size': per_page, 'per_page': per_page,
            'total': total, 'pages': math.ceil(total / per_page)}


def clean_narrative(text):
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(text or '')))
    text = re.sub(r'Borrower added on \d+/\d+/\d+\s*>?', ' ', text, flags=re.I)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|https?://\S+', ' ', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


POSITIVE = {'improve','improved','growth','growing','stable','success','successful',
            'profit','profitable','opportunity','expand','expansion','save','savings',
            'better','good','excellent','reliable','comfortable','secure'}
NEGATIVE = {'hardship','struggle','struggling','difficult','difficulty','loss','losses',
            'unemployed','unemployment','emergency','debt','bills','burden','late',
            'risk','risky','illness','medical','problem','problems','expensive'}


def narrative_sentiment(text):
    """Transparent exploratory valence heuristic, NOT a validated risk model.

    Negates a matched word after not/no/never within the preceding 3 tokens.
    Score is (positive matches - negative matches) / all matched words.
    """
    tokens = re.findall(r'[a-z]+', clean_narrative(text).lower())
    values = []
    for i, word in enumerate(tokens):
        value = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
        if value:
            if {'not', 'no', 'never'} & set(tokens[max(0, i-3):i]):
                value *= -1
            values.append(value)
    score = sum(values)/len(values) if values else 0.0
    label = 'positive' if score > 0.1 else 'negative' if score < -0.1 else 'neutral'
    return round(score, 4), label


def build_summary(db_path, manifest):
    """Fit corpus models offline, persist segment assignments, return evidence.

    K-means never uses loan status, repayments, recoveries, narrative sentiment,
    geographic location, or any post-origination feature to form clusters.
    Post-outcome comparisons describe associations and are not predictions.
    """
    import numpy as np
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
    from sklearn.metrics import silhouette_score, davies_bouldin_score
    from sklearn.preprocessing import StandardScaler

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query('SELECT * FROM loans ORDER BY id', conn)
    features = ['loan_amount', 'annual_income', 'interest_rate', 'dti', 'term_months']
    X = df[features].copy()
    missingness = {col: int(X[col].isna().sum()) for col in features}
    clip_bounds = {}
    medians = {}
    for col in features:
        medians[col] = float(X[col].median())
        X[col] = X[col].fillna(medians[col])
        lo, hi = X[col].quantile([0.01, 0.99])
        clip_bounds[col] = [float(lo), float(hi)]
        X[col] = X[col].clip(lo, hi)
    X['loan_amount'] = np.log1p(X['loan_amount'])
    X['annual_income'] = np.log1p(X['annual_income'])
    matrix = StandardScaler().fit_transform(X)
    experiments, best = [], None
    for k in range(2, 7):
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = model.fit_predict(matrix)
        sil = float(silhouette_score(matrix, labels, sample_size=min(2000, len(df)), random_state=42))
        db = float(davies_bouldin_score(matrix, labels))
        experiments.append({'k':k,'silhouette_score':round(sil,5),'davies_bouldin_score':round(db,5)})
        if best is None or sil > best[0]:
            best = (sil, labels, db, k)
    df['cluster_id'] = best[1]
    df['cluster_label'] = df['cluster_id'].map(lambda x: f'Segment {x + 1}')
    resolved = df['loan_status'].isin(['Fully Paid','Charged Off',
        'Does not meet the credit policy. Status:Fully Paid',
        'Does not meet the credit policy. Status:Charged Off'])
    df['repaid'] = np.where(resolved, df['loan_status'].str.endswith('Fully Paid').astype(float), np.nan)
    narratives = df['description'].fillna('').map(clean_narrative)
    has_narrative = narratives.str.len() >= 20
    df['sentiment_score'] = np.nan
    df['sentiment_label'] = 'unavailable'
    for idx in df.index[has_narrative]:
        score,label = narrative_sentiment(narratives[idx])
        df.loc[idx,['sentiment_score','sentiment_label']] = [score,label]
    df['topic_id'] = -1
    topics = []
    vocabulary_size = 0
    if has_narrative.sum() >= 10:
        stop = list(ENGLISH_STOP_WORDS | {'borrower','added','loan','loans','br','would','will','im',
                                        'ive','want','need','thank','thanks','lending','club','money'})
        vectorizer = TfidfVectorizer(stop_words=stop, max_features=2000, min_df=3,
                                     max_df=.90, ngram_range=(1,2), sublinear_tf=True)
        tfidf = vectorizer.fit_transform(narratives[has_narrative])
        vocabulary = vectorizer.get_feature_names_out()
        vocabulary_size = len(vocabulary)
        k = min(5, tfidf.shape[0]-1, tfidf.shape[1]-1)
        model = NMF(n_components=k, init='nndsvda', random_state=42, max_iter=500)
        weights = model.fit_transform(tfidf)
        topic_ids = weights.argmax(axis=1)
        # Documents with no in-vocabulary terms have no defensible topic.
        topic_ids[np.asarray(tfidf.sum(axis=1)).ravel() == 0] = -1
        df.loc[has_narrative,'topic_id'] = topic_ids
        for i, component in enumerate(model.components_):
            keywords = [str(vocabulary[j]) for j in component.argsort()[-8:][::-1]]
            sub = df[df.topic_id == i]
            topics.append({'id':i,'label':' / '.join(keywords[:3]),'keywords':keywords,
                           'count':int(len(sub)), 'resolved_count':int(sub.repaid.notna().sum()),
                           'repayment_rate':_number(sub.repaid.mean())})
    conn.executemany('UPDATE loans SET cluster_id=?,cluster_label=?,sentiment_score=?,sentiment_label=?,topic_id=? WHERE id=?',
                     [(int(r.cluster_id),r.cluster_label,_number(r.sentiment_score),r.sentiment_label,
                       int(r.topic_id),int(r.id)) for r in df.itertuples()])
    conn.execute('CREATE INDEX IF NOT EXISTS idx_loans_cluster ON loans(cluster_id,id)')
    conn.commit()

    clusters = []
    for cluster_id, sub in df.groupby('cluster_id'):
        clusters.append({'id':int(cluster_id),'label':f'Segment {int(cluster_id)+1}',
            'count':len(sub),'resolved_count':int(sub.repaid.notna().sum()),
            'repayment_rate':_number(sub.repaid.mean()),'income_change_pct':None,
            'mean_loan_amount':_number(sub.loan_amount.mean()),
            'mean_interest_rate':_number(sub.interest_rate.mean()),
            'mean_annual_income':_number(sub.annual_income.mean()),
            'mean_dti':_number(sub.dti.mean()),'mean_term_months':_number(sub.term_months.mean())})
    correlations = []
    for feature in features + ['sentiment_score']:
        pair = df[[feature,'repaid']].dropna()
        value = pair.corr().iloc[0,1] if len(pair)>2 and pair[feature].nunique()>1 else None
        correlations.append({'feature':feature,'outcome':'fully_paid_among_resolved',
                             'correlation':_number(value),'n':len(pair)})
    comparisons = []
    for term,sub in df.groupby('term_months'):
        comparisons.append({'term_months':int(term),'count':len(sub),
            'resolved_count':int(sub.repaid.notna().sum()),'repayment_rate':_number(sub.repaid.mean()),
            'mean_interest_rate':_number(sub.interest_rate.mean()),'mean_loan_amount':_number(sub.loan_amount.mean())})
    purposes = []
    for purpose,sub in df.groupby('purpose'):
        purposes.append({'purpose':purpose,'count':len(sub),'resolved_count':int(sub.repaid.notna().sum()),
                         'repayment_rate':_number(sub.repaid.mean())})
    regions = []
    for state,sub in df.groupby('state'):
        regions.append({'state':state,'count':len(sub),'resolved_count':int(sub.repaid.notna().sum()),
                        'repayment_rate':_number(sub.repaid.mean())})
    sentiment_groups = []
    for label,sub in df[has_narrative].groupby('sentiment_label'):
        sentiment_groups.append({'label':label,'count':len(sub),
              'resolved_count':int(sub.repaid.notna().sum()),'repayment_rate':_number(sub.repaid.mean())})
    counts = {t:conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
              for t in ['loans','market_prices','farm_records','dairy_records']}
    conn.close()
    paid_rate = _number(df.repaid.mean())
    summary = {
      'schema_version':1, 'generated_at':manifest['generated_at'],
      'dataset':{'records':len(df),'source_records':manifest['loans']['valid_rows'],
        'narratives':int(has_narrative.sum()),'nonempty_descriptions':int(narratives.str.len().gt(0).sum()),
        'source_narratives':manifest['loans']['nonempty_descriptions'],
        'sources':manifest['sources'],'table_counts':counts,'currency':'USD',
        'scope':'Historical US LendingClub consumer lending benchmark; not a developing-region microfinance impact dataset.'},
      'metrics':{'repayment_rate':paid_rate,'resolved_count':int(resolved.sum()),
        'unresolved_count':int((~resolved).sum()),'avg_income_change_pct':None,
        'silhouette_score':round(best[0],5),'davies_bouldin_score':round(best[2],5),
        'cluster_count':best[3]},
      'clusters':clusters,'topics':topics,'correlations':correlations,
      'loan_structures':comparisons,'purpose_comparisons':purposes,'regions':regions,
      'sentiment':sentiment_groups,'status_counts':dict(Counter(df.loan_status)),
      'filters':{'purposes':sorted(df.purpose.unique().tolist()),'states':sorted(df.state.unique().tolist())},
      'insights':[
        f'{len(df):,} loans were sampled uniformly from {manifest["loans"]["valid_rows"]:,} valid historical records with seed 42.',
        f'{int(resolved.sum()):,} sampled loans have a resolved status; {paid_rate:.1%} of these are fully paid. Active loans are excluded from this denominator.',
        f'{int(has_narrative.sum()):,} sampled loans have descriptions of at least 20 characters for exploratory topic and sentiment analysis.',
        'Compare term, purpose and segment outcomes as historical associations, controlling for confounding in any future study.',
        'Use the separate Indian market-price evidence for agricultural context. Do not transfer US consumer-loan thresholds to Indian borrowers.'
      ],
      'limitations':[
        'The supplied lending archive contains US consumer loans in USD. It does not establish microloan impacts in developing regions.',
        'Household poverty, income before/after lending, employment creation, business revenue changes and a control group are absent. Poverty reduction and causal effects cannot be estimated.',
        'Annual income is a baseline applicant attribute, not an economic improvement outcome. Repayment is a loan performance proxy, not a poverty measure.',
        'Borrower narratives are sparse, self-selected and historical; narrative sentiment uses an unvalidated transparent lexicon. No labeled sentiment accuracy is claimed.',
        'Clusters describe pre-origination financial attributes. Outcome comparisons use a historical snapshot, with censoring and selection bias; no credit approval or causal model is validated.',
        'The market workbook contains 1,048,575 data rows at the Excel sheet limit. Coverage outside the supplied workbook cannot be verified.',
        'The seasonal and dairy files provide business context, not borrower-linked loan outcomes. Their blank descriptions are not replaced with synthetic narratives.'
      ],
      'methods':{'sampling':manifest['loans']['sampling'], 'cluster_features':features,
        'cluster_feature_missing_counts':missingness,'imputation_medians':medians,'clip_bounds_1_99_percentile':clip_bounds,
        'scaling':'Median imputation, 1st/99th percentile clipping, log1p amount/income, StandardScaler.',
        'cluster_selection':'Highest silhouette on a fixed random sample of up to 2,000 rows; candidate k=2..6; no outcome variables in features.',
        'cluster_experiments':experiments,'random_seed':42,
        'repayment_definition':'Fully Paid / (Fully Paid + Charged Off), including equivalent legacy policy-status labels. All other statuses excluded.',
        'correlation':'Pairwise complete-case Pearson correlation with binary fully-paid status among resolved loans. Descriptive association; no causal or significance claim.',
        'topics':'TF-IDF (unigrams/bigrams, min_df=3, max_df=0.90, max_features=2000), 5-component NMF, top 8 terms. Dominant component assignment; zero-vectors unassigned.',
        'topic_vocabulary_size':vocabulary_size,
        'sentiment':'Fixed positive/negative lexicon with 3-token negation window. Score=(positive-negative)/matched words; >0.1 positive, <-0.1 negative, otherwise neutral.',
        'source_join':'Loan structures, narratives, clusters and repayment joined within each sampled source record. Market/farm/dairy data remain separate regional business context.',
        'business_outcomes':'Not available as observed longitudinal borrower-level outcomes.'}
    }
    return summary


def _number(value):
    if value is None:
        return None
    value = float(value)
    return round(value, 6) if math.isfinite(value) else None
