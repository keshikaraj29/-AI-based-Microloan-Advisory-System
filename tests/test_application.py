"""Regression cases use invented demo applicants, never real borrower identities."""
import io
import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as application
import new


@pytest.fixture(scope='module')
def isolated_database(tmp_path_factory):
    import os, sqlite3
    from data_store import get_store
    path=tmp_path_factory.mktemp('integration')/'pp1.sqlite3'
    original=os.environ.get('PP1_DATABASE')
    source=__import__('pathlib').Path(application.BASE)/'data'/'pp1.sqlite3'
    with sqlite3.connect(source) as src, sqlite3.connect(path) as dst:
        src.backup(dst)
    os.environ['PP1_DATABASE']=str(path)
    get_store.cache_clear()
    yield path
    if original is None: os.environ.pop('PP1_DATABASE',None)
    else: os.environ['PP1_DATABASE']=original
    get_store.cache_clear()


@pytest.fixture
def client(isolated_database):
    application.app.config.update(TESTING=True)
    return application.app.test_client()


def token(client):
    client.get('/apply')
    with client.session_transaction() as sess:
        return sess['csrf']


def register(client):
    import uuid
    return client.post('/register',data={'csrf_token':token(client),'username':'test.'+uuid.uuid4().hex[:12],'password':'testing-only-pass-123'})


def sample_form(client):
    with client.session_transaction() as sess:
        signed_in='user_id' in sess
    if not signed_in: register(client)
    return {'csrf_token':token(client),'name':'Synthetic Applicant','monthly_income':'25000',
            'years_business':'5','existing_loan':'No','language':'English',
            'description':'I need a loan of INR 50000 for wheat farming on 2 acres in Pune district.'}


def submit_example(client,**changes):
    form=sample_form(client);form.update(changes)
    response=client.post('/submit',data=form)
    assert response.status_code==302 and '/assessment' in response.location
    identifier=response.location.split('/')[-2]
    return identifier,client.get(response.location)


@pytest.mark.parametrize('text, expected', [
    ('loan of INR 50,000 for 2 acres', 50000),
    ('loan of 1.5 lakh rupees', 150000),
    ('मुझे ५०००० रुपये का ऋण चाहिए', 50000),
    ('2 acres growing wheat', 0),
    ('loan 2 lakh for milk', 200000),
    ('I sell milk for INR 60 per liter', 0),
])
def test_money_extraction(text, expected):
    assert new.detect_loan_amount(text) == expected


def test_hectare_conversion():
    assert new.detect_area('2 hectares') == pytest.approx(4.9421076294)


def test_unit_price_distinguishes_frequency():
    assert new.detect_unit_price('I produce 100 per day') == 0
    assert new.detect_unit_price('I sell at INR 60 per liter') == 60


@pytest.mark.parametrize('description', ['loan INR -50000 for wheat', 'loan 0 for wheat', 'loan INR 50000 for -2 acres', 'loan INR 50000 for ' + '9'*320 + ' acres'])
def test_invalid_extracted_numbers(client, description):
    form = sample_form(client)
    form['description'] = description
    response = client.post('/submit', data=form, follow_redirects=True)
    assert response.status_code in (200,400)
    assert b'Illustration:' not in response.data


def test_sentiment_negation_and_product_boundaries():
    assert application.weighted_sentiment_analysis('not profitable')['score'] < 0
    assert new.detect_product('a milkweed nursery') == (None, None)


@pytest.mark.parametrize('rate', [0, .12, .36])
def test_amortization_reconciles(rate):
    schedule, emi, interest = new.generate_repayment_schedule(50000, rate, 12)
    assert schedule.iloc[-1].Balance == 0
    assert schedule.Principal.sum() == pytest.approx(50000, abs=.01)
    assert schedule.Interest.sum() == pytest.approx(interest, abs=.01)
    assert schedule.EMI.sum() == pytest.approx(50000 + interest, abs=.01)
    assert (schedule.Balance >= 0).all()


@pytest.mark.parametrize('income', ['nan', 'inf', '-1', '0', 'hello'])
def test_non_finite_income_rejected(income):
    assert not application.validate_income(income)


def test_pages_and_invalid_api(client):
    for path in ['/', '/apply', '/research']:
        assert client.get(path).status_code == 200
    assert client.get('/api/research/borrowers?page_size=100000').status_code == 400
    assert client.get('/api/research/borrowers?page=bad').status_code == 400
    assert client.post('/api/chat', json={'message': 'hello'}).status_code == 400
    headers = {'X-CSRF-Token': token(client)}
    for payload in [[], None, {}, {'message': ''}, {'message': 'a'*1001}]:
        assert client.post('/api/chat', json=payload, headers=headers).status_code == 400


def test_chat_fast_local_help(client):
    response = client.post('/api/chat', json={'message': 'Can this prove poverty impact?'}, headers={'X-CSRF-Token': token(client)})
    assert response.status_code == 200
    assert 'cannot prove' in response.json['reply']
    assert response.json['source']


def test_invalid_dob_returns_actionable_form(client):
    form = sample_form(client)
    form['dob'] = '2999-01-01'
    response = client.post('/submit', data=form, follow_redirects=True)
    assert response.status_code == 400
    assert b'valid adult date of birth' in response.data


def test_unreadable_ocr_is_validation_error(client):
    form = sample_form(client)
    form['description_image'] = (io.BytesIO(b'not a real image'), 'bad.png')
    response = client.post('/submit', data=form, follow_redirects=True)
    assert response.status_code == 400
    assert b'not a readable image' in response.data


def test_owned_persistent_application_and_private_lazy_download(client):
    identifier,response=submit_example(client,description='I need a loan to open milk business in bengaluru of around 10000 rupees')
    assert response.status_code==200
    data=client.get(f'/download/applicant_{identifier}.json')
    assert data.status_code==200
    record=data.json
    assert record['loan_amount']==10000 and record['currency']=='INR'
    assert record['category']=='small_business'
    assert record['source_type']=='local_application'
    assert record['repayment_status']=='Not tracked'
    assert record['cluster_id'] is None
    assert 'id_number' not in record
    assert client.get(f'/applications/{identifier}/explanation').status_code==200
    assert client.get(f'/apply?from={identifier}').status_code==200
    assert client.get('/applications').status_code==200
    result=client.get(f'/download/bank_{identifier}.pdf')
    assert result.status_code==200 and result.data.startswith(b'%PDF')
    from pypdf import PdfReader
    pdf=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(result.data)).pages)
    assert '63,000' not in pdf and 'USD' not in pdf
    stranger=application.app.test_client();register(stranger)
    for path in [f'/applications/{identifier}',f'/download/applicant_{identifier}.json',f'/download/bank_{identifier}.pdf',f'/applications/{identifier}/explanation',f'/apply?from={identifier}']:
        assert stranger.get(path).status_code==404
    assert stranger.get('/api/research/borrowers?source=applications').json['total']==0
    assert client.get('/download/../app.py').status_code==404


def test_repayment_manual_and_atomic_csv_workflow(client):
    identifier,_=submit_example(client,loan_amount='1200',loan_purpose='car')
    csrf=token(client)
    start=f'/applications/{identifier}/start'
    client.post(start,data={'csrf_token':csrf,'confirm_recording':'yes','start_date':'2026-01-31','actual_principal':'1500','annual_rate_percent':'0','term_months':'3'})
    response=client.get(f'/applications/{identifier}')
    assert response.status_code==200 and b'1,500' in response.data
    assert client.post(f'/applications/{identifier}/payments',data={'csrf_token':csrf,'amount':'300','paid_on':'2026-02-01','reference':'payment1'}).status_code==302
    csv=b'amount,paid_on,reference\n200,2026-03-01,payment2\n'
    assert client.post(f'/applications/{identifier}/payments/import',data={'csrf_token':csrf,'payment_csv':(io.BytesIO(csv),'payments.csv')}).status_code==302
    record=client.get(f'/download/applicant_{identifier}.json').json
    assert record['agreement_terms']['principal']==1500
    assert record['loan_amount']==1200 # Preserve the original application estimate.
    from application_store import get_application
    with client.session_transaction() as sess: owner=sess['user_id']
    ledger=get_application(owner,identifier)['ledger']
    assert ledger['total_paid']==500 and ledger['outstanding']==1000
    assert client.get(f'/applications/{identifier}').status_code==200


def test_same_category_research_and_atlas_owned_context(client):
    identifier,_=submit_example(client,loan_purpose='medical',description='INR 10000 for medical treatment')
    context=client.get(f'/api/research/context?application_id={identifier}')
    assert context.status_code==200 and context.json['category']['purpose']=='medical'
    assert client.get('/api/research/borrowers?source=applications&purpose=medical').json['total']==1
    assert client.get('/api/research/borrowers?source=applications&purpose=car').json['total']==0
    scoped=client.get('/api/research/summary?purpose=medical')
    assert scoped.status_code==200 and scoped.json['scope']['purpose']=='medical'
    rows=client.get('/api/research/borrowers?purpose=medical').json['items']
    assert rows and all(r['category']=='medical' and r['currency']=='INR' for r in rows)
    headers={'X-CSRF-Token':token(client)}
    for question in ['why rejection?','what intrest rate?','explain clusters','how to repay?','what datasets?']:
        chat=client.post('/api/chat',json={'message':question,'application_id':identifier},headers=headers)
        assert chat.status_code==200 and chat.json['actions'] and chat.json['reply']
    explanation=client.get(f'/applications/{identifier}/explanation').data
    assert b'target="_blank"' in explanation


def test_unknown_category_still_explorable_without_crash(client):
    identifier,_=submit_example(client,description='I need 10000 rupees for an unspecified purpose')
    for message in ['what datasets?','explain clusters']:
        assert client.post('/api/chat',json={'message':message,'application_id':identifier},headers={'X-CSRF-Token':token(client)}).status_code==200
    assert client.get(f'/research?application_id={identifier}').status_code==200


def test_currency_conversion_and_secure_response_headers(client):
    from research_analytics import query_loans
    from currency_tools import convert_source_amount
    original=query_loans(per_page=1)['items'][0]
    response=client.get('/api/research/borrowers?page_size=1')
    row=response.json['items'][0]
    assert row['loan_amount']==convert_source_amount(original['loan_amount'])
    assert row['currency']=='INR'
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    assert response.headers['Cache-Control']=='no-store'
    assert client.get('/api/research/borrowers?source=applications').status_code==401
    assert client.get('/api/research/summary?purpose=invalid').status_code==400


def test_research_actual_prepared_data(client):
    assert client.get('/api/health').status_code == 200
    result = client.get('/api/research/summary')
    assert result.status_code == 200 and isinstance(result.json, dict)
    page1 = client.get('/api/research/borrowers?page=1&page_size=2')
    page2 = client.get('/api/research/borrowers?page=2&page_size=2')
    assert page1.status_code == page2.status_code == 200
    assert page1.json != page2.json


def test_application_uses_supplied_market_data(client):
    identifier,response=submit_example(client,description='I need a loan of INR 50000 for wheat farming on 2 acres in Tonk district.')
    assert response.status_code==200
    context=client.get(f'/api/research/context?application_id={identifier}').json['application_context']
    assert any('AGMARKNET' in str(entry) and '1579' in str(entry) for entry in context)


def test_parallel_read_requests():
    def read(_):
        with application.app.test_client() as c:
            return c.get('/api/research/borrowers?page_size=5').status_code
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(read, range(24))) == [200]*24


def test_business_context_api_is_bounded_and_uses_source_units(client):
    for source in ('dairy','farm','market'):
        result=client.get('/api/research/business',query_string={'source':source,'page_size':2})
        assert result.status_code==200
        assert len(result.json['items'])==2 and result.json['columns']
        assert result.json['currency']=='INR' and result.json['note']
    assert client.get('/api/research/business?source=invalid').status_code==400
    assert client.get('/api/research/business?page_size=1000').status_code==400
    milk=client.get('/api/research/business?source=dairy&product=Milk&location=Karnataka').json
    assert milk['total']==26
    assert all(r['product']=='Milk' and r['location']=='Karnataka' for r in milk['items'])


def test_malformed_next_does_not_crash(client):
    assert client.get('/login?next=//[').status_code==200
    with application.app.test_request_context('/'):
        assert application.safe_next('//[')=='/applications'
        assert application.safe_next('https://example.com')=='/applications'


def test_validation_preserves_entered_application(client):
    form=sample_form(client);form['loan_amount']='-2'
    response=client.post('/submit',data=form)
    assert response.status_code==400
    assert b'Synthetic Applicant' in response.data and form['description'].encode() in response.data


def test_error_page_works_when_fx_config_unavailable(client,monkeypatch):
    def unavailable(): raise RuntimeError('Invalid exchange configuration')
    monkeypatch.setattr(application,'get_fx',unavailable)
    with application.app.test_request_context('/research'):
        assert application.service_error(RuntimeError('unavailable'))[1]==503


def test_narrative_sentiment_is_available_in_assessment_json_and_atlas(client):
    identifier,response=submit_example(client,description='I need to borrow 10,000 rupees for my dairy business',loan_purpose='dairy')
    assert response.status_code==200
    assert b'Neutral' in response.data
    assert b'user_entered</p>' not in response.data
    canonical=client.get(f'/download/applicant_{identifier}.json').json
    assert canonical['sentiment']=='neutral'
    chat=client.post('/api/chat',json={'message':'What is my narrative sentiment?','application_id':identifier},headers={'X-CSRF-Token':token(client)})
    assert chat.status_code==200
    assert 'Neutral' in chat.json['reply']
    assert 'no positive or negative words' in chat.json['reply']
    assert any(a['url'].endswith('#application-narrative') for a in chat.json['actions'])


def test_invalid_operator_policy_returns_service_error(client,monkeypatch):
    monkeypatch.setenv('PP1_DEMO_ANNUAL_RATE','invalid')
    response=client.post('/api/chat',json={'message':'What interest rate?'},headers={'X-CSRF-Token':token(client)})
    assert response.status_code==503 and response.json['error']


def test_chat_rejects_non_string_application_id(client):
    response=client.post('/api/chat',json={'message':'Explain it','application_id':{'bad':'shape'}},headers={'X-CSRF-Token':token(client)})
    assert response.status_code==400
