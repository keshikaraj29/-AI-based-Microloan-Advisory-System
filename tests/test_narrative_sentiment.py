"""Wording polarity is transparent and separate from all lending decisions."""
import copy
import json

import pytest

from narrative_sentiment import analyze_narrative, enrich_assessment
from research_analytics import narrative_sentiment


STORY = 'I need to borrow 10,000 rupees for my dairy business'


def test_exact_dairy_request_has_explained_neutral_tone():
    result = analyze_narrative(STORY)
    assert result['label'] == 'neutral'
    assert result['score'] == 0
    assert result['matched_terms'] == []
    assert 'without enough emotional wording' in result['explanation']
    assert 'English' in result['explanation']
    assert 'does not affect loan eligibility' in result['limitations']
    assert 'confidence' not in result
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('text,label,score', [
    ('stable profitable growth', 'positive', 1),
    ('loss hardship difficult', 'negative', -1),
    ('not stable', 'negative', -1),
    ('not a hardship', 'positive', 1),
    ('never very good opportunity', 'negative', -1),
    ('good but difficult', 'neutral', 0),
    (STORY, 'neutral', 0),
    ('मुझे अपने डेयरी व्यवसाय के लिए ऋण चाहिए', 'neutral', 0),
])
def test_wording_analysis_matches_research_method(text,label,score):
    result = analyze_narrative(text)
    assert result['label'] == label
    assert result['score'] == score
    assert (result['score'], result['label']) == narrative_sentiment(text)
    assert result['match_count'] == result['positive_matches'] + result['negative_matches']


def test_negation_is_explained_per_term_and_cleaning_matches_corpus():
    result = analyze_narrative('<b>not</b> stable, but profitable. https://example.com/struggle')
    assert result['matched_terms'] == [
        {'term':'stable', 'valence':'negative', 'negated':True},
        {'term':'profitable', 'valence':'negative', 'negated':True},
    ]
    assert 'three words' in result['explanation']


def test_missing_narrative_is_distinguished_from_neutral_wording():
    result = analyze_narrative('   ')
    assert result['label'] == 'unavailable'
    assert result['score'] is None
    assert 'Add a business narrative' in result['explanation']


def test_read_enrichment_preserves_financial_snapshot_and_uses_saved_story():
    old = {'business_description': STORY, 'loan_terms': {'annual_rate':.12, 'principal':10000},
           'financials':{'annual_revenue':None}, 'rule_trace':[{'id':'historical', 'status':'missing'}]}
    original = copy.deepcopy(old)
    result = enrich_assessment(old, {'description':'profitable growth'})
    assert result['sentiment']['label'] == 'neutral'
    assert {key:value for key,value in result.items() if key != 'sentiment'} == original
    assert old == original
    fallback = enrich_assessment({'financials':{'annual_revenue':None}}, {'description':'profitable growth'})
    assert fallback['sentiment']['label'] == 'positive'
