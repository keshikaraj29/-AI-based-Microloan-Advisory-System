"""Atlas intent regressions; no network calls or fictional outcomes."""
import pytest
from atlas_service import answer

@pytest.mark.parametrize('question,source',[
    ('Why was revenue generated?','Assessment provenance'),
    ('Explain how narrative topics were generated','NLP methodology'),
    ('What is the repayment rate in the data?','Observed research outcomes'),
    ('How are borrower clusters generated?','Prepared clustering methodology'),
    ('How do I record repayment?','Recorded repayment ledger'),
    ('What intrest rate would I get?','Repayment calculation and demo policy'),
    ('Browse the dairy dataset','Supplied business data catalog'),
])
def test_specific_question_routes_to_relevant_evidence(question,source):
    response=answer(question)
    assert response['source']==source and response['reply'] and response['actions']
