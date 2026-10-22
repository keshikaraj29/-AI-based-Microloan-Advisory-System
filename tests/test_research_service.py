"""Currency, category-scope and source-context browsing regressions."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from currency_tools import (get_fx,convert_source_amount,format_inr,research_summary_inr,
                            research_page_inr,household_summary_inr)
from data_store import get_store
from research_analytics import get_research_summary
from research_service import summary_for_category,context_records


@pytest.fixture
def fixed_rate(tmp_path,monkeypatch):
    path = tmp_path/'fx.json'
    path.write_text(json.dumps({'source_currency':'USD','display_currency':'INR','usd_to_inr':10,
                               'scope':'Synthetic fixed conversion for this unit test.'}))
    monkeypatch.setenv('PP1_FX_CONFIG',str(path))
    return path


def test_currency_conversion_is_idempotent_and_nonmutating(fixed_rate):
    source = {'dataset':{'currency':'USD','sources':[{'currency':'USD'}]},
              'clusters':[{'mean_loan_amount':12.345,'mean_annual_income':100}],
              'methods':{'imputation_medians':{'loan_amount':25},'clip_bounds_1_99_percentile':{'annual_income':[1,2]}}}
    original = deepcopy(source)
    converted = research_summary_inr(source)
    assert source==original
    assert converted['clusters'][0]['mean_loan_amount']==123.45
    assert converted['methods']['imputation_medians']['loan_amount']==250
    assert converted['methods']['clip_bounds_1_99_percentile']['annual_income']==[10,20]
    assert research_summary_inr(converted)==converted
    page = research_page_inr({'items':[{'loan_amount':12,'currency':'USD'},
        {'loan_amount':34,'currency':'INR','source_type':'local_application'}]})
    assert [row['loan_amount'] for row in page['items']]==[120,34]
    assert page['items'][1]['source_type']=='local_application'
    assert research_page_inr(page)==page


def test_formatting_finite_amounts_and_half_up_rounding(fixed_rate):
    assert format_inr(1234567.895)=='₹12,34,567.90'
    assert format_inr('-0.001')=='₹0.00'
    assert convert_source_amount('bad') is None
    assert convert_source_amount('NaN') is None
    assert convert_source_amount('Infinity') is None
    assert format_inr('Infinity')=='Not provided'


def test_invalid_fx_is_service_error(fixed_rate):
    fixed_rate.write_text('{bad-json')
    with pytest.raises(RuntimeError,match='reference-rate'):
        get_fx()


def test_household_currencies_are_kept_separate_and_not_guessed(fixed_rate):
    summary = {'currency_groups':[{'currency':currency,'household_income':{'mean_change':12.3,'paired_n':3}}
                                  for currency in ['USD','INR','EUR']]}
    converted = household_summary_inr(summary)
    assert [r['household_income']['mean_change'] for r in converted['currency_groups']]==[123,12.3,None]
    assert converted['currency_groups'][2]['conversion_status']=='rate_missing'
    assert household_summary_inr(converted)==converted
    assert summary['currency_groups'][0]['household_income']['mean_change']==12.3


def test_category_counts_and_raw_method_amounts_are_correctly_scoped():
    raw = deepcopy(get_research_summary())
    purpose = 'small_business'
    scoped = summary_for_category(purpose)
    with get_store().pool.connection() as conn:
        n,nonempty = conn.execute("SELECT COUNT(*),SUM(LENGTH(TRIM(COALESCE(description,'')))>0) FROM loans WHERE purpose=?",(purpose,)).fetchone()
        mean_amount = conn.execute('SELECT AVG(loan_amount) FROM loans WHERE purpose=? AND cluster_id=?',
                                   (purpose,scoped['clusters'][0]['id'])).fetchone()[0]
    assert scoped['dataset']['records']==n==sum(scoped['status_counts'].values())
    assert scoped['dataset']['nonempty_descriptions']==nonempty
    assert len(scoped['purpose_comparisons'])==1 and scoped['purpose_comparisons'][0]['count']==n
    assert scoped['clusters'][0]['mean_loan_amount']==convert_source_amount(mean_amount)
    assert scoped['dataset']['full_sample_records']==raw['dataset']['records']
    assert get_research_summary()==raw
    display = json.dumps(summary_for_category())
    assert not re.search(r'\$\s*\d|\bUSD\s+\d|\b1 USD\b',display)
    assert scoped['methods']['monetary_display_currency']=='INR'


@pytest.mark.parametrize('source,expected_total',[('farm',3162),('dairy',4326),('market',1048575)])
def test_context_browsing_paginated_safe_fields(source,expected_total):
    first = context_records(source,page=1,per_page=3)
    second = context_records(source,page=2,per_page=3)
    assert first['total']==expected_total
    assert first['currency']=='INR'
    assert len(first['items'])==3
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    allowed = {column['key'] for column in first['columns']}
    assert all(set(row)==allowed for row in first['items'])
    assert all('row_json' not in row for row in first['items'])
    if source=='farm':
        assert not any(column['kind']=='money' for column in first['columns'])
        assert 'price' not in allowed


def test_context_exact_case_insensitive_filters_and_native_currency():
    lower = context_records('dairy',product='milk',location='tamil nadu')
    upper = context_records('dairy',product='MILK',location='TAMIL NADU')
    assert lower['items']==upper['items'] and lower['total']>0
    with get_store().pool.connection() as conn:
        expected = conn.execute("SELECT COUNT(*) FROM dairy_records WHERE product='Milk' AND location='Tamil Nadu'").fetchone()[0]
        raw = json.loads(conn.execute('SELECT row_json FROM dairy_records WHERE id=?',(lower['items'][0]['id'],)).fetchone()[0])
    assert lower['total']==expected
    assert lower['items'][0]['revenue']==float(raw['Approx. Total Revenue(INR)'])
    assert context_records('dairy',product='mil')['total']==0
    assert context_records('dairy',product="Milk' OR 1=1 --")['total']==0
    market = context_records('market',product='wheat',location='auraiya')
    assert market['total']>0
    assert all(r['commodity']=='Wheat' and (r['district']=='Auraiya' or r['market']=='Auraiya') for r in market['items'])
    with get_store().pool.connection() as conn:
        raw_price = conn.execute('SELECT modal_price FROM market_prices WHERE id=?',(market['items'][0]['id'],)).fetchone()[0]
    assert market['items'][0]['modal_price']==raw_price


@pytest.mark.parametrize('kwargs',[{'source':'loans'},{'page':0},{'per_page':101},{'page':'bad'}])
def test_context_invalid_paging_and_source_rejected(kwargs):
    with pytest.raises(ValueError):
        context_records(**kwargs)
