"""Compatibility facade for the Phase 1 application.

Corpus NLP, clustering and observed-outcome analysis live in research_analytics.py.
Original exploratory code is retained under legacy/ for historical comparison.
"""
from fast_services import narrative_analytics


def run_optional_analytics(description, entities=None, borrower_data=None,
                           farm_df=None, dairy_df=None, outcome_data=None):
    return narrative_analytics(description)
