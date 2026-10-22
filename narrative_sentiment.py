"""Explainable wording analysis; never an input to lending or affordability.

Uses the same fixed English lexicon, three-token negation window and thresholds
as the prepared research corpus. It requires no network request or model load.
"""
from __future__ import annotations

import re

from research_analytics import NEGATIVE, POSITIVE, clean_narrative

METHOD_VERSION = 'lexicon-negation-v1'
LIMITATIONS = ('This is an exploratory English keyword method, not a validated emotional '
              'assessment. It can miss context, sarcasm and other languages. Sentiment '
              'does not affect loan eligibility, interest, repayment estimates or financial calculations.')


def analyze_narrative(text):
    """Return polarity and its lexical evidence without invented confidence."""
    cleaned = clean_narrative(text)
    tokens = re.findall(r'[a-z]+', cleaned.lower())
    matches = []
    for index, word in enumerate(tokens):
        value = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
        if not value:
            continue
        negated = bool({'not', 'no', 'never'} & set(tokens[max(0, index-3):index]))
        if negated:
            value *= -1
        matches.append({'term': word, 'valence': 'positive' if value > 0 else 'negative',
                        'negated': negated})
    positive = sum(item['valence'] == 'positive' for item in matches)
    negative = len(matches) - positive
    score = (positive-negative)/len(matches) if matches else 0.0
    label = 'positive' if score > 0.1 else 'negative' if score < -0.1 else 'neutral'
    score = round(score, 4)
    if not cleaned:
        label, score = 'unavailable', None
        explanation = 'Add a business narrative to analyze its wording.'
    elif not matches:
        explanation = ('Neutral: no positive or negative words from the supported English lexicon '
                       'were found. This is a descriptive request without enough emotional wording '
                       'for this method to identify a positive or negative tone; it is not evidence '
                       'of the borrower\'s feelings or business prospects.')
    else:
        explanation = (f'{label.capitalize()}: {positive} positive and {negative} negative '
                       f'keyword matches after checking for “not”, “no” or “never” in the '
                       f'preceding three words. Polarity = ({positive} − {negative}) / '
                       f'{len(matches)} = {score:g}. Scores above 0.1 are positive; '
                       'below −0.1 are negative; the remaining scores are neutral.')
    return {'label': label, 'score': score, 'explanation': explanation,
            'method': 'English keyword sentiment with negation',
            'method_version': METHOD_VERSION, 'source': 'application_narrative',
            'matched_terms': matches, 'match_count': len(matches),
            'positive_matches': positive, 'negative_matches': negative,
            'limitations': LIMITATIONS}


def enrich_assessment(result, borrower_data=None):
    """Add current wording analysis to a copy; preserve all financial evidence.

    Older saved records omitted sentiment. Compute it on retrieval rather than
    rewriting an application snapshot or rerunning today's lending policy.
    """
    result = dict(result)
    narrative = result.get('business_description')
    if not str(narrative or '').strip():
        narrative = (borrower_data or {}).get('description', '')
    result['sentiment'] = analyze_narrative(narrative)
    return result
