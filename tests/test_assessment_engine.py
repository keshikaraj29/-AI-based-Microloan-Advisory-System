"""Explicitly synthetic inputs; no fictional data enters research datasets."""
import json
from pathlib import Path

import pytest

import assessment_engine as engine


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setattr(engine, '_context', lambda *args: [])
    for key in ('PP1_DEMO_ANNUAL_RATE','PP1_DEMO_TERM_MONTHS','PP1_DEMO_MIN_TERM_MONTHS','PP1_DEMO_MAX_TERM_MONTHS','PP1_DEMO_MAX_DEBT_RATIO'):
        monkeypatch.delenv(key, raising=False)
    return {'name':'Synthetic Test','description':'Loan of INR 10000 to open a milk business in Bengaluru.',
            'monthly_income':'10000','existing_monthly_debt':'0'}


def test_milk_example_never_invents_revenue_cost_quantity_or_growth(base):
    base['description']='I need a loan to open milk business in bengaluru of around 10000 rupees'
    result=engine.assess_application(base)
    assert result['status']=='needs_information'
    assert result['loan_terms']['principal']==10000
    assert result['category']['sector']=='dairy'
    assert result['entities']['location']=='Bengaluru'
    for key in ('monthly_business_revenue','monthly_business_costs','annual_revenue','annual_operating_surplus','annual_cash_after_debt_service'):
        assert result['financials'][key] is None
    for key in ('area','quantity','unit_price'):
        assert result['entities'][key] is None
    assert result['repayment_assessment']['confidence_score'] is None
    assert result['repayment_assessment']['can_repay'] is None


def test_only_complete_explicit_business_pair_can_be_annualized(base):
    base['monthly_business_revenue']='5000'
    incomplete=engine.assess_application(base)
    assert incomplete['financials']['annual_revenue'] is None
    assert incomplete['financials']['annual_operating_surplus'] is None
    base['monthly_business_costs']='2000'
    result=engine.assess_application(base)
    assert result['status']=='ready_for_review'
    assert result['financials']['annual_revenue']==60000
    assert result['financials']['annual_operating_surplus']==36000
    assert result['financials']['annual_cash_after_debt_service']==round(36000-result['loan_terms']['total_repayment'],2)


@pytest.mark.parametrize('purpose',list(engine.PURPOSES))
def test_all_source_purposes_remain_recognized(base,purpose):
    base.update(purpose=purpose,monthly_business_revenue=5000,monthly_business_costs=2000)
    result=engine.assess_application(base)
    assert result['category']['purpose']==purpose
    assert result['category']['raw']==purpose
    assert result['category']['source']=='user_entered'


def test_unrecognized_explicit_category_is_preserved_and_requires_clarification(base):
    base['purpose']='unclassified special project'
    result=engine.assess_application(base)
    assert result['category']['raw']=='unclassified special project'
    assert result['category']['purpose']=='unknown'
    assert result['status']=='needs_information'


def test_unknown_narrative_does_not_default_to_farm_or_dairy(base):
    base['description']='Loan of INR 10000 for an unspecified purpose.'
    result=engine.assess_application(base)
    assert result['category']['purpose']=='unknown'
    assert result['status']=='needs_information'


def test_loan_amount_has_no_default_and_explicit_field_takes_precedence(base):
    base['description']='Open a milk business in Bengaluru.'
    result=engine.assess_application(base)
    assert result['loan_terms']['principal'] is None
    assert result['loan_terms']['schedule']==[]
    base.update(loan_amount=15000,description='I need a loan of INR 10000 for a dairy business.')
    result=engine.assess_application(base)
    assert result['loan_terms']['principal']==15000
    assert result['input_provenance'][0]['source']=='user_entered'


@pytest.mark.parametrize('change',[{'loan_amount':'NaN'},{'loan_amount':0},{'loan_amount':-1},
    {'monthly_income':'inf'},{'existing_monthly_debt':-5},{'monthly_business_costs':-5},
    {'currency':'USD'},{'description':'Loan of 0 rupees for milk business'},
    {'description':'Loan of -1000 rupees for milk business'},
    {'description':'I need USD 1000 for milk business'}])
def test_invalid_or_foreign_ambiguous_values_are_rejected(base,change):
    base.update(change)
    with pytest.raises(ValueError):
        engine.assess_application(base)


def test_total_debt_burden_and_rule_trace_raise_concern(base):
    base.update(existing_monthly_debt=4000,monthly_business_revenue=5000,monthly_business_costs=1000)
    result=engine.assess_application(base)
    assert result['status']=='affordability_concern'
    trace=next(t for t in result['rule_trace'] if t['id']=='debt_ratio')
    assert trace['status']=='concern'
    assert trace['observed']==pytest.approx((4000+result['loan_terms']['emi'])/10000)
    assert trace['threshold']==.4


def test_unreported_obligations_are_missing_not_zero(base):
    base.pop('existing_monthly_debt')
    assert engine.assess_application(base)['financials']['existing_monthly_debt'] is None
    base['existing_loan']='No'
    result=engine.assess_application(base)
    assert result['financials']['existing_monthly_debt']==0
    trace=next(p for p in result['input_provenance'] if p['field']=='existing_monthly_debt')
    assert trace['source']=='user_declaration_no_existing_loan'


def test_protected_fields_card_ownership_and_sentiment_do_not_set_terms(base):
    base.update(monthly_business_revenue=5000,monthly_business_costs=2000)
    a=engine.assess_application(base)
    b=engine.assess_application(dict(base,age=80,gender='Other',credit_card='Yes',sentiment='negative',dob='1946-01-01'))
    assert a['loan_terms']==b['loan_terms']
    assert a['status']==b['status']
    assert a['rule_trace']==b['rule_trace']


def test_analyzed_positive_and_negative_wording_never_changes_financial_decision(base):
    base.update(loan_amount=10000,loan_purpose='small_business',business_category='dairy',
                monthly_business_revenue=5000,monthly_business_costs=2000)
    positive=engine.assess_application(dict(base,description='A stable profitable dairy business.'))
    negative=engine.assess_application(dict(base,description='A struggling dairy business with losses.'))
    assert positive['sentiment']['label']=='positive'
    assert negative['sentiment']['label']=='negative'
    for field in ('loan_terms','policy_snapshot','financials','status','rule_trace','repayment_assessment'):
        assert positive[field]==negative[field]


def test_exact_dairy_story_has_visible_neutral_analysis(base):
    base['description']='I need to borrow 10,000 rupees for my dairy business'
    result=engine.assess_application(base)
    assert result['sentiment']['label']=='neutral'
    assert result['sentiment']['score']==0
    assert result['sentiment']['matched_terms']==[]
    assert result['financials']['annual_revenue'] is None


def test_configurable_zero_interest_policy_and_schedule_reconcile(base,monkeypatch):
    monkeypatch.setenv('PP1_DEMO_ANNUAL_RATE','0')
    monkeypatch.setenv('PP1_DEMO_TERM_MONTHS','3')
    result=engine.assess_application(base)
    terms=result['loan_terms']
    assert terms['total_interest']==0
    assert terms['total_repayment']==10000
    assert terms['schedule'][-1]['Balance']==0
    assert terms['schedule'][-1]['EMI']==3333.34
    json.dumps(result,allow_nan=False)


def test_requested_term_changes_schedule_and_is_recorded_in_provenance(base):
    base['term_months']='24'
    result=engine.assess_application(base)
    assert result['loan_terms']['term_months']==24
    assert len(result['loan_terms']['schedule'])==24
    assert result['loan_terms']['emi'] < 888.49
    assert result['policy_snapshot']['default_term_months']==12
    assert result['policy_snapshot']['term_source']=='user_entered'
    provenance=next(x for x in result['input_provenance'] if x['field']=='term_months')
    assert provenance['value']==24 and provenance['source']=='user_entered'


@pytest.mark.parametrize('term',[0,-1,361,'12.5','NaN',True])
def test_invalid_requested_terms_are_rejected(base,term):
    base['term_months']=term
    with pytest.raises(ValueError):
        engine.assess_application(base)


def test_configured_term_bounds_are_enforced(base,monkeypatch):
    monkeypatch.setenv('PP1_DEMO_MIN_TERM_MONTHS','6')
    monkeypatch.setenv('PP1_DEMO_MAX_TERM_MONTHS','36')
    base['term_months']=48
    with pytest.raises(ValueError,match='6 to 36'):
        engine.assess_application(base)


def test_legacy_cashflow_adapter_does_not_invent_missing_values(base):
    from fast_services import project_business
    revenue,surplus,ratio,projection=project_business({'loan_amount':10000,'category':'Dairy'},base)
    assert revenue is None and surplus is None and ratio is None
    assert projection['assumptions']==[]


def test_pdf_contains_missing_evidence_and_no_invented_growth(base,tmp_path):
    from report_builder import create_assessment_pdf
    from pypdf import PdfReader
    result=engine.assess_application(base)
    path=create_assessment_pdf(result,tmp_path/'synthetic_assessment.pdf')
    reader=PdfReader(path)
    text='\n'.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages)>=4
    assert 'More information needed' in text
    assert 'Not provided' in text
    assert '10,000.00' in text
    assert 'Scheduled installments' in text
    assert '63,000' not in text
    assert 'RECOMMENDED FOR APPROVAL' not in text
