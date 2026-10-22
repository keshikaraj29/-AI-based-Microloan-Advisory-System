"""Request-time services. No spreadsheet loading, network calls or model fitting."""
from collections import Counter
from functools import lru_cache
import math
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def local_context():
    """Small contextual CSVs are read once per process, never modified in requests."""
    farm = pd.read_csv(BASE / "data_season.csv")
    dairy = pd.read_csv(BASE / "dairy_dataset.csv")
    locations = set(farm.Location.dropna().astype(str)) | set(dairy.Location.dropna().astype(str))
    return farm, dairy, locations


@lru_cache(maxsize=1)
def locations():
    from data_store import get_store
    values = set(local_context()[2])
    values.update(get_store().market_locations())
    return sorted(values, key=lambda x: (-len(x), x))


def project_business(entities, borrower):
    """Compatibility adapter: no assumed quantities, yields, costs or revenue.

    Active applications use assessment_engine.assess_application directly.
    Callers retaining this older tuple interface receive None for unavailable
    values and must not reinterpret those missing values as zero.
    """
    from assessment_engine import assess_application
    data = dict(borrower)
    if data.get('loan_amount') in (None, '') and entities.get('loan_amount'):
        data['loan_amount'] = entities['loan_amount']
    result = assess_application(data)
    financials = result['financials']
    revenue = financials['annual_revenue']
    surplus = financials['annual_operating_surplus']
    principal = result['loan_terms']['principal']
    ratio = surplus / principal if surplus is not None and principal else None
    return revenue, surplus, ratio, dict(result['projection'], market=None)


def narrative_analytics(description):
    """A bounded single-document NLP view; corpus models live in Research."""
    tokens = re.findall(r'[^\W\d_]+', description.lower(), re.UNICODE)
    stop = {'the', 'and', 'for', 'with', 'have', 'want', 'need', 'loan', 'from', 'this', 'that', 'in', 'to', 'of', 'a', 'i', 'my', 'is', 'on'}
    counts = Counter(t for t in tokens if len(t) > 2 and t not in stop)
    deferred = {'available': False, 'error': 'See Research for precomputed analysis of the supplied loan corpus. This application has no observed repayment outcome.'}
    return {
        'spacy_preprocessing': {'available': True, 'tokens': tokens, 'tokens_without_stopwords': list(counts), 'lemmas': [], 'pos_tags': [], 'method': 'Unicode tokenization; no POS/lemmatization model'},
        'spacy_entities': {}, 'tfidf_analysis': {'available': True, 'method': 'Term frequency', 'top_keywords': [{'keyword': k, 'score': v} for k, v in counts.most_common(10)]},
        'cluster_analysis': dict(deferred), 'topic_analysis': dict(deferred),
        'correlation_analysis': dict(deferred), 'advanced_sentiment': {'available': False, 'error': 'Rule-based sentiment is shown above. It is not calibrated against human labels and does not establish creditworthiness.'}
    }


def chat_reply(message):
    """Compatibility tuple using the current INR-aware Atlas guidance."""
    from atlas_service import answer
    result = answer(message)
    return result['reply'], result['source']


def chat_answer(message):
    """Historical alias for callers using the legacy tuple interface."""
    return chat_reply(message)
